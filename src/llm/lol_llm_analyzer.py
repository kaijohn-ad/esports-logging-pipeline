"""
League of Legends LLM分析モジュール

LoL特化のLLM分析機能を提供する
"""

import json
import logging
import time
from typing import Dict, Any, List

from .openrouter_client import OpenRouterClient
from .analysis_result import AnalysisResult
from ..kpi.kpi_result import KPIResult


class LoLLLMAnalyzer:
    """LoL特化LLMアナライザー"""
    
    def __init__(self, openrouter_client: OpenRouterClient = None):
        self.client = openrouter_client or OpenRouterClient()
        self.logger = logging.getLogger(__name__)
        
        # プロンプトテンプレート
        self.performance_prompt_template = """
あなたはLoL（League of Legends）の専門分析者です。
以下のプレイヤーのKPIデータを分析し、詳細なフィードバックを提供してください。

プレイヤー情報:
- チャンピオン: {champion}
- KDA: {kda}
- CS/10min: {cs_per_10min}
- ゴールド効率: {gold_per_min} gold/min
- ダメージ効率: {damage_per_gold}
- ビジョンスコア: {vision_score_per_min}/min
- 総合スコア: {overall_score}/100

既存の強み: {strengths}
既存の弱み: {weaknesses}

以下の形式でJSON応答してください:
{{
    "analysis": {{
        "performance_summary": "全体的なパフォーマンス要約",
        "key_strengths": ["強み1", "強み2", "強み3"],
        "improvement_areas": ["改善点1", "改善点2", "改善点3"]
    }},
    "recommendations": ["具体的推奨事項1", "具体的推奨事項2", "具体的推奨事項3"],
    "champion_specific": {{
        "role_analysis": "ロール特化分析",
        "build_suggestions": "ビルド提案",
        "positioning_tips": "ポジション改善提案"
    }}
}}
"""
    
    async def analyze_performance(self, kpi_result: KPIResult) -> AnalysisResult:
        """パフォーマンス分析を実行"""
        try:
            # プロンプト生成
            prompt = self._create_performance_prompt(kpi_result)
            
            # LLMリクエスト
            start_time = time.time()
            response = await self.client.request(prompt)
            analysis_time = max(time.time() - start_time, 0.001)  # 最小時間を保証
            
            # レスポンス解析
            result = self._parse_analysis_response(response, kpi_result)
            result.analysis_time = analysis_time
            
            self.logger.info(f"Performance analysis completed for {kpi_result.player_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing performance for {kpi_result.player_id}: {e}")
            # フォールバック: 基本的な分析結果を返す
            return self._create_fallback_analysis(kpi_result)
    
    def generate_recommendations(self, kpi_result: KPIResult) -> List[str]:
        """改善提案を生成（同期版）"""
        # 同期版の簡易実装
        recommendations = []
        
        if kpi_result.kda < 2.0:
            recommendations.append("デスを減らすため、安全な立ち位置を意識する")
        
        if kpi_result.cs_per_10min < 70:
            recommendations.append("ラストヒット練習でCS効率を向上させる")
        
        if kpi_result.vision_score_per_min < 1.0:
            recommendations.append("ワード購入・設置を増やしてビジョン貢献を向上させる")
        
        return recommendations
    
    async def analyze_champion_performance(self, kpi_result: KPIResult) -> Dict[str, str]:
        """チャンピオン特化分析"""
        champion_analysis = {
            "role_analysis": f"{kpi_result.champion}としてのパフォーマンス分析",
            "build_suggestions": f"{kpi_result.champion}向けビルド提案",
            "positioning_tips": f"{kpi_result.champion}のポジション改善提案"
        }
        
        self.logger.info(f"Champion analysis completed for {kpi_result.champion}")
        return champion_analysis
    
    def set_fallback_models(self, models: List[str]) -> None:
        """フォールバックモデルを設定"""
        self.client.fallback_models = models
        self.logger.info(f"Fallback models updated: {models}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得"""
        return self.client.get_usage_stats()
    
    def _create_performance_prompt(self, kpi_result: KPIResult) -> str:
        """パフォーマンス分析プロンプトを作成"""
        return self.performance_prompt_template.format(
            champion=kpi_result.champion,
            kda=kpi_result.kda,
            cs_per_10min=kpi_result.cs_per_10min,
            gold_per_min=kpi_result.gold_per_min,
            damage_per_gold=kpi_result.damage_per_gold,
            vision_score_per_min=kpi_result.vision_score_per_min,
            overall_score=kpi_result.overall_score,
            strengths=", ".join(kpi_result.strengths),
            weaknesses=", ".join(kpi_result.weaknesses)
        )
    
    def _parse_analysis_response(self, response: Dict[str, Any], kpi_result: KPIResult) -> AnalysisResult:
        """LLMレスポンスを解析してAnalysisResultに変換"""
        try:
            content = response["choices"][0]["message"]["content"]
            analysis_data = json.loads(content)
            
            return AnalysisResult(
                player_id=kpi_result.player_id,
                champion=kpi_result.champion,
                performance_summary=analysis_data["analysis"]["performance_summary"],
                key_strengths=analysis_data["analysis"]["key_strengths"],
                improvement_areas=analysis_data["analysis"]["improvement_areas"],
                recommendations=analysis_data["recommendations"],
                role_analysis=analysis_data["champion_specific"]["role_analysis"],
                build_suggestions=analysis_data["champion_specific"]["build_suggestions"],
                positioning_tips=analysis_data["champion_specific"]["positioning_tips"],
                llm_model=self.client.primary_model,
                tokens_used=response.get("usage", {}).get("total_tokens", 0),
                confidence_score=0.8  # デフォルト値
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            return self._create_fallback_analysis(kpi_result)
    
    def _create_fallback_analysis(self, kpi_result: KPIResult) -> AnalysisResult:
        """フォールバック分析結果を作成"""
        return AnalysisResult(
            player_id=kpi_result.player_id,
            champion=kpi_result.champion,
            performance_summary=f"{kpi_result.champion}プレイヤーの基本分析（総合スコア: {kpi_result.overall_score}）",
            key_strengths=kpi_result.strengths,
            improvement_areas=[],
            recommendations=self.generate_recommendations(kpi_result),
            role_analysis=f"{kpi_result.champion}としての基本分析",
            build_suggestions="一般的なビルドガイドを参照してください",
            positioning_tips="安全な立ち位置を心がけてください",
            llm_model="fallback",
            tokens_used=0,
            confidence_score=0.5
        )