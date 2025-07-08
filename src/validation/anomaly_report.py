"""
異常検出レポートモジュール

データ異常の検出結果を格納するデータクラス
"""

from pydantic import BaseModel


class AnomalyReport(BaseModel):
    """異常検出レポートクラス"""
    event_id: str
    anomaly_type: str
    severity: str  # low, medium, high, critical
    description: str
    suggested_action: str = ""
    confidence: float = 0.0  # 0.0 - 1.0