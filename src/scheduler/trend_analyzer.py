"""
トレンド分析モジュール

プレイヤーのパフォーマンストレンドを分析
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from ..kpi.lol_kpi_calculator import LoLKPICalculator
from ..kpi.kpi_result import KPIResult
from ..config.lol_config import LoLConfig


@dataclass
class TrendDataPoint:
    """トレンドデータポイント"""
    date: str
    matches_played: int = 0
    average_kda: float = 0.0
    average_cs_per_10min: float = 0.0
    average_gold_per_min: float = 0.0
    average_vision_score_per_min: float = 0.0
    win_rate: float = 0.0
    champion_diversity: int = 0
    total_wins: int = 0
    total_losses: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)


@dataclass
class TrendAnalysisResult:
    """トレンド分析結果"""
    player_id: str
    player_name: str
    analysis_period: str
    trend_data: List[TrendDataPoint]
    
    # 総合指標
    overall_trend: str = "stable"  # improving, declining, stable
    performance_score: float = 0.0
    
    # 詳細分析
    improving_metrics: List[str] = None
    declining_metrics: List[str] = None
    stable_metrics: List[str] = None
    
    # 予測・推奨
    predictions: List[str] = None
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.improving_metrics is None:
            self.improving_metrics = []
        if self.declining_metrics is None:
            self.declining_metrics = []
        if self.stable_metrics is None:
            self.stable_metrics = []
        if self.predictions is None:
            self.predictions = []
        if self.recommendations is None:
            self.recommendations = []
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "analysis_period": self.analysis_period,
            "trend_data": [point.to_dict() for point in self.trend_data],
            "overall_trend": self.overall_trend,
            "performance_score": self.performance_score,
            "improving_metrics": self.improving_metrics,
            "declining_metrics": self.declining_metrics,
            "stable_metrics": self.stable_metrics,
            "predictions": self.predictions,
            "recommendations": self.recommendations
        }


class TrendAnalyzer:
    """トレンド分析クラス"""
    
    def __init__(self, config: LoLConfig, db_path: str = "data/esports.db"):
        self.config = config
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self.kpi_calculator = LoLKPICalculator()
        
        # トレンド分析の閾値設定
        self.TREND_THRESHOLD = 0.1  # 10%以上の変化でトレンドとみなす
        self.STABLE_THRESHOLD = 0.05  # 5%以内の変化は安定とみなす
    
    def analyze_player_trends(self, player_config: Dict[str, str], weeks: int = 4) -> TrendAnalysisResult:
        """プレイヤーのトレンドを分析"""
        player_id = player_config.get("puuid", "")
        player_name = player_config.get("name", "Unknown")
        
        self.logger.info(f"Starting trend analysis for player: {player_name}")
        
        try:
            # 週次データポイントを取得
            trend_data = self._get_weekly_trend_data(player_id, weeks)
            
            if not trend_data:
                self.logger.warning(f"No trend data found for player {player_name}")
                return TrendAnalysisResult(
                    player_id=player_id,
                    player_name=player_name,
                    analysis_period=f"Past {weeks} weeks",
                    trend_data=[]
                )
            
            # トレンド分析実行
            result = TrendAnalysisResult(
                player_id=player_id,
                player_name=player_name,
                analysis_period=f"Past {weeks} weeks",
                trend_data=trend_data
            )
            
            # 各指標のトレンド分析
            self._analyze_metric_trends(result)
            
            # 総合トレンド判定
            self._determine_overall_trend(result)
            
            # パフォーマンススコア計算
            self._calculate_performance_score(result)
            
            # 予測と推奨の生成
            self._generate_predictions_and_recommendations(result)
            
            self.logger.info(f"Trend analysis completed for {player_name}: {result.overall_trend}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing trends for player {player_name}: {e}")
            return TrendAnalysisResult(
                player_id=player_id,
                player_name=player_name,
                analysis_period=f"Past {weeks} weeks",
                trend_data=[]
            )
    
    def _get_weekly_trend_data(self, player_id: str, weeks: int) -> List[TrendDataPoint]:
        """週次トレンドデータを取得"""
        trend_data = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 過去の週データを取得
            for week_offset in range(weeks):
                week_start = datetime.now() - timedelta(weeks=week_offset + 1)
                week_end = week_start + timedelta(days=7)
                
                week_start_str = week_start.strftime("%Y-%m-%d")
                week_end_str = week_end.strftime("%Y-%m-%d")
                
                # その週のマッチを取得
                cursor.execute("""
                    SELECT m.id, m.ts
                    FROM match m
                    JOIN event e ON m.id = e.match_id
                    WHERE e.actor = ? AND m.ts BETWEEN ? AND ?
                    GROUP BY m.id, m.ts
                    ORDER BY m.ts
                """, (player_id, week_start_str, week_end_str))
                
                matches = cursor.fetchall()
                
                if not matches:
                    continue
                
                # 週次データポイントを作成
                data_point = self._calculate_weekly_metrics(cursor, player_id, matches, week_start_str)
                trend_data.append(data_point)
            
            conn.close()
            
            # 日付順でソート（古い順）
            trend_data.sort(key=lambda x: x.date)
            
            return trend_data
            
        except Exception as e:
            self.logger.error(f"Error getting weekly trend data: {e}")
            return []
    
    def _calculate_weekly_metrics(self, cursor: sqlite3.Cursor, player_id: str, 
                                matches: List[tuple], week_start: str) -> TrendDataPoint:
        """週次メトリクスを計算"""
        match_ids = [match[0] for match in matches]
        
        # 基本統計
        data_point = TrendDataPoint(
            date=week_start,
            matches_played=len(match_ids)
        )
        
        if not match_ids:
            return data_point
        
        # KDA計算
        kda_values = []
        cs_values = []
        gold_values = []
        vision_values = []
        wins = 0
        champions = set()
        
        for match_id in match_ids:
            try:
                # マッチデータを取得してKPI計算
                # これは簡略化された実装 - 実際のマッチデータからKPIを計算
                cursor.execute("""
                    SELECT event, meta
                    FROM event
                    WHERE match_id = ? AND actor = ?
                """, (match_id, player_id))
                
                events = cursor.fetchall()
                
                # 簡易的なKDA計算（実際の実装では詳細なマッチデータが必要）
                kills = sum(1 for event in events if event[0] == "CHAMPION_KILL")
                deaths = sum(1 for event in events if event[0] == "CHAMPION_DEATH")
                assists = sum(1 for event in events if event[0] == "CHAMPION_ASSIST")
                
                kda = (kills + assists) / max(deaths, 1)
                kda_values.append(kda)
                
                # その他のメトリクス（模擬データ）
                cs_values.append(150 + (len(events) * 2))  # 簡易CS計算
                gold_values.append(350 + (len(events) * 10))  # 簡易ゴールド計算
                vision_values.append(1.5 + (len(events) * 0.1))  # 簡易ビジョン計算
                
                # 勝率計算（簡易）
                if len(events) > 10:  # 長いマッチは勝利とみなす
                    wins += 1
                
                # チャンピオン多様性（模擬データ）
                champions.add(f"champion_{match_id[-3:]}")
                
            except Exception as e:
                self.logger.error(f"Error processing match {match_id}: {e}")
                continue
        
        # 平均値計算
        if kda_values:
            data_point.average_kda = sum(kda_values) / len(kda_values)
        if cs_values:
            data_point.average_cs_per_10min = sum(cs_values) / len(cs_values)
        if gold_values:
            data_point.average_gold_per_min = sum(gold_values) / len(gold_values)
        if vision_values:
            data_point.average_vision_score_per_min = sum(vision_values) / len(vision_values)
        
        data_point.win_rate = wins / len(match_ids) if match_ids else 0
        data_point.champion_diversity = len(champions)
        data_point.total_wins = wins
        data_point.total_losses = len(match_ids) - wins
        
        return data_point
    
    def _analyze_metric_trends(self, result: TrendAnalysisResult):
        """各指標のトレンドを分析"""
        if len(result.trend_data) < 2:
            return
        
        # 最初と最後のデータポイントを比較
        first_point = result.trend_data[0]
        last_point = result.trend_data[-1]
        
        metrics = [
            ("KDA", first_point.average_kda, last_point.average_kda),
            ("CS/10min", first_point.average_cs_per_10min, last_point.average_cs_per_10min),
            ("Gold/min", first_point.average_gold_per_min, last_point.average_gold_per_min),
            ("Vision Score/min", first_point.average_vision_score_per_min, last_point.average_vision_score_per_min),
            ("Win Rate", first_point.win_rate, last_point.win_rate),
            ("Champion Diversity", first_point.champion_diversity, last_point.champion_diversity)
        ]
        
        for metric_name, first_value, last_value in metrics:
            if first_value == 0:
                continue
                
            change_rate = (last_value - first_value) / first_value
            
            if change_rate > self.TREND_THRESHOLD:
                result.improving_metrics.append(f"{metric_name} (+{change_rate:.1%})")
            elif change_rate < -self.TREND_THRESHOLD:
                result.declining_metrics.append(f"{metric_name} ({change_rate:.1%})")
            else:
                result.stable_metrics.append(f"{metric_name} (stable)")
    
    def _determine_overall_trend(self, result: TrendAnalysisResult):
        """総合トレンドを判定"""
        improving_count = len(result.improving_metrics)
        declining_count = len(result.declining_metrics)
        
        if improving_count > declining_count:
            result.overall_trend = "improving"
        elif declining_count > improving_count:
            result.overall_trend = "declining"
        else:
            result.overall_trend = "stable"
    
    def _calculate_performance_score(self, result: TrendAnalysisResult):
        """パフォーマンススコアを計算"""
        if not result.trend_data:
            result.performance_score = 0.0
            return
        
        # 最新データポイントから基本スコア計算
        latest_data = result.trend_data[-1]
        
        # 重み付けスコア計算
        kda_score = min(latest_data.average_kda * 20, 50)
        cs_score = min(latest_data.average_cs_per_10min / 10, 25)
        win_rate_score = latest_data.win_rate * 20
        diversity_score = min(latest_data.champion_diversity * 2, 5)
        
        base_score = kda_score + cs_score + win_rate_score + diversity_score
        
        # トレンドボーナス
        trend_bonus = 0
        if result.overall_trend == "improving":
            trend_bonus = 10
        elif result.overall_trend == "declining":
            trend_bonus = -10
        
        result.performance_score = round(min(base_score + trend_bonus, 100), 1)
    
    def _generate_predictions_and_recommendations(self, result: TrendAnalysisResult):
        """予測と推奨を生成"""
        if not result.trend_data:
            return
        
        # 予測生成
        if result.overall_trend == "improving":
            result.predictions.append("継続的な改善が期待されます")
            result.predictions.append("次週も同様のパフォーマンス向上が見込めます")
        elif result.overall_trend == "declining":
            result.predictions.append("パフォーマンスの低下傾向があります")
            result.predictions.append("早期の改善策が必要です")
        else:
            result.predictions.append("安定したパフォーマンスを維持しています")
        
        # 推奨生成
        if result.declining_metrics:
            result.recommendations.append("以下の指標の改善に集中してください:")
            for metric in result.declining_metrics:
                result.recommendations.append(f"  - {metric}")
        
        if result.improving_metrics:
            result.recommendations.append("以下の好調な指標を維持してください:")
            for metric in result.improving_metrics:
                result.recommendations.append(f"  - {metric}")
        
        # 最新データから具体的な推奨を追加
        latest_data = result.trend_data[-1]
        if latest_data.average_kda < 2.0:
            result.recommendations.append("KDA改善: デス数を減らし、チームファイトでの立ち回りを見直してください")
        if latest_data.average_cs_per_10min < 70:
            result.recommendations.append("CS改善: ファーミング効率を向上させてください")
        if latest_data.win_rate < 0.5:
            result.recommendations.append("勝率改善: オブジェクト制圧とチームプレイに注力してください")
        if latest_data.champion_diversity < 3:
            result.recommendations.append("チャンピオンプール拡大: 多様なチャンピオンを練習してください")
    
    def analyze_all_players(self, weeks: int = 4) -> List[TrendAnalysisResult]:
        """すべての追跡プレイヤーのトレンドを分析"""
        results = []
        
        for player_config in self.config.scheduler.tracked_players:
            try:
                result = self.analyze_player_trends(player_config, weeks)
                results.append(result)
                
            except Exception as e:
                player_name = player_config.get("name", "Unknown")
                self.logger.error(f"Error analyzing trends for {player_name}: {e}")
        
        return results
    
    def get_summary_report(self, analysis_results: List[TrendAnalysisResult]) -> Dict[str, Any]:
        """サマリーレポートを生成"""
        if not analysis_results:
            return {
                "total_players": 0,
                "improving_players": 0,
                "declining_players": 0,
                "stable_players": 0,
                "average_performance_score": 0.0,
                "top_performers": [],
                "needs_attention": []
            }
        
        total_players = len(analysis_results)
        improving_players = sum(1 for r in analysis_results if r.overall_trend == "improving")
        declining_players = sum(1 for r in analysis_results if r.overall_trend == "declining")
        stable_players = sum(1 for r in analysis_results if r.overall_trend == "stable")
        
        average_score = sum(r.performance_score for r in analysis_results) / total_players
        
        # 上位パフォーマー（スコア上位3名）
        top_performers = sorted(analysis_results, key=lambda x: x.performance_score, reverse=True)[:3]
        
        # 注意が必要なプレイヤー（下位3名または declining）
        needs_attention = [r for r in analysis_results if r.overall_trend == "declining"]
        if len(needs_attention) < 3:
            low_performers = sorted(analysis_results, key=lambda x: x.performance_score)[:3]
            needs_attention.extend(low_performers)
        
        return {
            "total_players": total_players,
            "improving_players": improving_players,
            "declining_players": declining_players,
            "stable_players": stable_players,
            "average_performance_score": round(average_score, 1),
            "top_performers": [{"name": r.player_name, "score": r.performance_score} for r in top_performers],
            "needs_attention": [{"name": r.player_name, "trend": r.overall_trend, "score": r.performance_score} for r in needs_attention[:3]]
        }