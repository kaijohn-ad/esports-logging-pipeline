"""
LLM分析結果モジュール

LLM分析の結果を格納するデータクラス
"""

from typing import List
from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """LLM分析結果クラス"""
    player_id: str
    champion: str = ""
    
    # 分析結果
    performance_summary: str = ""
    key_strengths: List[str] = Field(default_factory=list)
    improvement_areas: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # チャンピオン特化情報
    role_analysis: str = ""
    build_suggestions: str = ""
    positioning_tips: str = ""
    
    # メタ情報
    llm_model: str = ""
    tokens_used: int = 0
    analysis_time: float = 0.0
    confidence_score: float = 0.0