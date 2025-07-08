"""
KPI計算結果モジュール

KPI計算の結果を格納するデータクラス
"""

from typing import List
from pydantic import BaseModel, Field


class KPIResult(BaseModel):
    """KPI計算結果クラス"""
    player_id: str
    champion: str = ""
    game_duration: float = 0.0
    
    # 基本KPI
    kda: float = 0.0
    cs_per_10min: float = 0.0
    gold_per_min: float = 0.0
    damage_per_gold: float = 0.0
    
    # 上級KPI
    vision_score_per_min: float = 0.0
    ward_efficiency: float = 0.0
    objective_contribution: float = 0.0
    first_blood_contribution: bool = False
    
    # メタ情報
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    overall_score: float = 0.0  # 0.0 - 100.0