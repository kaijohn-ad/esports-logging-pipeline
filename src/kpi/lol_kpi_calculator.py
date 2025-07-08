"""
League of Legends KPI計算モジュール

LoL特有のKPI（キーパフォーマンス指標）を計算する
"""

import logging
from typing import Dict, Any, List
from .lol_kpi_config import LoLKPIConfig
from .kpi_result import KPIResult
from ..canonizer.event import Event


class LoLKPICalculator:
    """LoL特有のKPI計算クラス"""
    
    def __init__(self, config: LoLKPIConfig = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or LoLKPIConfig()
    
    def calculate_basic_kpi(self, match_data: Dict[str, Any], player_id: str) -> KPIResult:
        """基本KPI（KDA、CS/10min、ゴールド効率）を計算"""
        try:
            participant = self._find_participant(match_data, player_id)
            if not participant:
                raise ValueError(f"Player {player_id} not found in match data")
            
            game_duration = self._get_game_duration(match_data)
            if game_duration <= 0:
                raise ValueError("Invalid game duration")
            
            # 基本データ取得
            player_stats = self._extract_player_stats(participant)
            
            # KPI計算
            kda = self._calculate_kda(player_stats["kills"], player_stats["deaths"], player_stats["assists"])
            cs_per_10min = self.calculate_cs_per_10min(
                player_stats["minions_killed"], 
                player_stats["neutral_killed"], 
                game_duration
            )
            gold_per_min = self._calculate_gold_per_min(player_stats["gold_earned"], game_duration)
            damage_per_gold = self.calculate_damage_per_gold(
                player_stats["damage_dealt"], 
                player_stats["gold_earned"]
            )
            
            result = KPIResult(
                player_id=player_id,
                champion=participant.get("championName", ""),
                game_duration=game_duration,
                kda=kda,
                cs_per_10min=cs_per_10min,
                gold_per_min=gold_per_min,
                damage_per_gold=damage_per_gold
            )
            
            self.logger.info(f"Basic KPI calculated for {player_id}: KDA={kda}, CS/10min={cs_per_10min:.1f}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating basic KPI for {player_id}: {e}")
            raise
    
    def calculate_advanced_kpi(self, match_data: Dict[str, Any], player_id: str) -> KPIResult:
        """上級KPI（ビジョンスコア、オブジェクト貢献度）を計算"""
        try:
            basic_kpi = self.calculate_basic_kpi(match_data, player_id)
            participant = self._find_participant(match_data, player_id)
            
            game_duration_min = basic_kpi.game_duration / 60
            
            # ビジョン関連データ
            vision_stats = self._extract_vision_stats(participant)
            
            # 上級KPI計算
            vision_score_per_min = vision_stats["vision_score"] / game_duration_min
            ward_efficiency = (vision_stats["wards_placed"] + vision_stats["wards_killed"]) / game_duration_min
            
            # オブジェクト貢献度
            first_blood = (participant.get("firstBloodKill", False) or 
                          participant.get("firstBloodAssist", False))
            
            # 基本KPIを拡張
            basic_kpi.vision_score_per_min = vision_score_per_min
            basic_kpi.ward_efficiency = ward_efficiency
            basic_kpi.first_blood_contribution = first_blood
            
            # 強み・弱み分析
            basic_kpi.strengths, basic_kpi.weaknesses = self._analyze_strengths_weaknesses(basic_kpi)
            
            # 総合スコア計算
            basic_kpi.overall_score = self._calculate_overall_score(basic_kpi)
            
            self.logger.info(f"Advanced KPI calculated for {player_id}: Overall Score={basic_kpi.overall_score}")
            return basic_kpi
            
        except Exception as e:
            self.logger.error(f"Error calculating advanced KPI for {player_id}: {e}")
            raise
    
    def calculate_cs_per_10min(self, minions_killed: int, neutral_killed: int, game_duration: int) -> float:
        """CS/10min を計算"""
        if game_duration <= 0:
            return 0.0
        
        total_cs = minions_killed + neutral_killed
        minutes = game_duration / 60
        return round((total_cs / minutes) * 10, 2)
    
    def calculate_vision_score_efficiency(self, vision_score: int, wards_placed: int, 
                                        wards_killed: int, game_duration: int) -> float:
        """ビジョンスコア効率を計算"""
        if game_duration <= 0:
            return 0.0
        
        minutes = game_duration / 60
        return round(vision_score / minutes, 2)
    
    def calculate_objective_contribution(self, events: List[Event], player_id: str) -> float:
        """オブジェクト貢献度を計算"""
        contribution_score = 0.0
        
        for event in events:
            if event.actor == player_id:
                if event.event == "objective_destroy":
                    building_type = event.meta.get("buildingType", "")
                    if "TOWER" in building_type:
                        contribution_score += self.config.TOWER_SCORE
                    elif "INHIBITOR" in building_type:
                        contribution_score += self.config.INHIBITOR_SCORE
                    elif "NEXUS" in building_type:
                        contribution_score += self.config.NEXUS_SCORE
                
                elif event.event == "monster_kill":
                    monster_type = event.meta.get("monsterType", "")
                    if monster_type == "DRAGON":
                        contribution_score += self.config.DRAGON_SCORE
                    elif monster_type == "BARON":
                        contribution_score += self.config.BARON_SCORE
                    elif monster_type == "RIFTHERALD":
                        contribution_score += self.config.RIFTHERALD_SCORE
        
        return contribution_score
    
    def calculate_gold_efficiency(self, gold_earned: int, damage_dealt: int, game_duration: int) -> float:
        """ゴールド効率を計算"""
        if game_duration <= 0:
            return 0.0
        
        minutes = game_duration / 60
        return round(gold_earned / minutes, 1)
    
    def calculate_damage_per_gold(self, damage_dealt: int, gold_earned: int) -> float:
        """ダメージ/ゴールド効率を計算"""
        if gold_earned <= 0:
            return 0.0
        
        return round(damage_dealt / gold_earned, 3)
    
    def _extract_player_stats(self, participant: Dict[str, Any]) -> Dict[str, int]:
        """プレイヤーの基本統計情報を抽出"""
        return {
            "kills": participant.get("kills", 0),
            "deaths": participant.get("deaths", 0),
            "assists": participant.get("assists", 0),
            "minions_killed": participant.get("totalMinionsKilled", 0),
            "neutral_killed": participant.get("neutralMinionsKilled", 0),
            "gold_earned": participant.get("goldEarned", 0),
            "damage_dealt": participant.get("totalDamageDealtToChampions", 0)
        }
    
    def _extract_vision_stats(self, participant: Dict[str, Any]) -> Dict[str, int]:
        """プレイヤーのビジョン関連統計を抽出"""
        return {
            "vision_score": participant.get("visionScore", 0),
            "wards_placed": participant.get("wardsPlaced", 0),
            "wards_killed": participant.get("wardsKilled", 0)
        }
    
    def _get_game_duration(self, match_data: Dict[str, Any]) -> int:
        """ゲーム時間を取得"""
        return match_data.get("info", {}).get("gameDuration", 0)
    
    def _calculate_gold_per_min(self, gold_earned: int, game_duration: int) -> float:
        """分あたりゴールド獲得量を計算"""
        if game_duration <= 0:
            return 0.0
        
        minutes = game_duration / 60
        return round(gold_earned / minutes, 1)
    
    def _analyze_strengths_weaknesses(self, kpi: KPIResult) -> tuple[List[str], List[str]]:
        """プレイヤーの強み・弱みを分析"""
        strengths = []
        weaknesses = []
        
        cs_per_min = kpi.cs_per_10min / 10
        
        # KDA分析
        if kpi.kda >= self.config.EXCELLENT_KDA:
            strengths.append("優秀なKDA - キルデス管理が上手")
        elif kpi.kda < self.config.GOOD_KDA:
            weaknesses.append("KDA改善が必要 - デス数の削減を意識")
        
        # CS分析
        if cs_per_min >= self.config.EXCELLENT_CS:
            strengths.append("優秀なCS効率 - ファーミングスキルが高い")
        elif cs_per_min < self.config.GOOD_CS:
            weaknesses.append("CS効率改善が必要 - ラストヒット練習を推奨")
        
        # ビジョン分析
        if kpi.vision_score_per_min >= self.config.EXCELLENT_VISION:
            strengths.append("優秀なビジョン貢献 - マップ制圧力が高い")
        elif kpi.vision_score_per_min < self.config.GOOD_VISION:
            weaknesses.append("ビジョン貢献改善が必要 - ワード購入・設置を増やす")
        
        # ダメージ効率分析
        if kpi.damage_per_gold >= 1.5:
            strengths.append("高いダメージ効率 - ゴールドの有効活用")
        elif kpi.damage_per_gold < 1.0:
            weaknesses.append("ダメージ効率改善が必要 - アイテムビルド見直し")
        
        # ファーストブラッド分析
        if kpi.first_blood_contribution:
            strengths.append("序盤の積極性 - ファーストブラッド貢献")
        
        return strengths, weaknesses
    
    def _find_participant(self, match_data: Dict[str, Any], player_id: str) -> Dict[str, Any]:
        """マッチデータから特定プレイヤーの情報を取得"""
        participants = match_data.get("info", {}).get("participants", [])
        
        for participant in participants:
            if participant.get("puuid") == player_id:
                return participant
        
        return None
    
    def _calculate_kda(self, kills: int, deaths: int, assists: int) -> float:
        """KDA比を計算"""
        if deaths == 0:
            return float(kills + assists)  # Perfect KDA
        return round((kills + assists) / deaths, 2)
    
    def _calculate_overall_score(self, kpi: KPIResult) -> float:
        """総合スコアを計算"""
        # 重み付けによる総合スコア計算
        kda_score = min(kpi.kda * self.config.KDA_WEIGHT, 50)
        cs_score = min(kpi.cs_per_10min / self.config.CS_WEIGHT, 25)
        vision_score = min(kpi.vision_score_per_min * self.config.VISION_WEIGHT, 15)
        damage_score = min(kpi.damage_per_gold * self.config.DAMAGE_WEIGHT, 10)
        
        total_score = kda_score + cs_score + vision_score + damage_score
        return round(min(total_score, 100), 1)