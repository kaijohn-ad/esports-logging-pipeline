"""
ダッシュボードモジュール

リアルタイムWebダッシュボード用のモジュール
"""

from .api import DashboardAPI
from .websocket import WebSocketManager

__all__ = ["DashboardAPI", "WebSocketManager"]