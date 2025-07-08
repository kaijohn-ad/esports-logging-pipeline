"""
共通イベントスキーマ

全ゲームタイトルで共通使用するイベント形式を定義
"""

import json
from typing import Dict, Any
from pydantic import BaseModel, Field


class Event(BaseModel):
    """共通イベントスキーマ v1.0"""
    timestamp: float  # seconds since match start
    event: str        # kill, death, stun, ult, ring_move ...
    actor: str        # self / teammate / enemy-name
    target: str | None = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    def to_row(self, match_id: str):
        """SQLite保存用のタプルに変換"""
        return (match_id, self.timestamp, self.event, self.actor, self.target, json.dumps(self.meta))