"""
League of Legends 設定モジュール

LoL関連の設定を管理する
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field


class APIConfig(BaseModel):
    """API設定クラス"""
    riot_api_key: str = ""
    openrouter_api_key: str = ""
    riot_region: str = "jp1"
    rate_limit: Dict[str, int] = Field(default_factory=lambda: {
        "max_requests": 20,
        "time_window": 120
    })


class PlayerConfig(BaseModel):
    """プレイヤー設定クラス"""
    summoner_name: str = ""
    puuid: str = ""
    default_region: str = "jp1"
    tracked_champions: List[str] = Field(default_factory=list)


class LoLConfig(BaseModel):
    """LoL総合設定クラス"""
    api: APIConfig = Field(default_factory=APIConfig)
    player: PlayerConfig = Field(default_factory=PlayerConfig)