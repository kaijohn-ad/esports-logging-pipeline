"""
WebSocket管理モジュール

リアルタイムデータ更新のためのWebSocket接続を管理
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import logging
import json
from datetime import datetime


class WebSocketManager:
    """WebSocket接続管理クラス"""
    
    def __init__(self):
        """WebSocketManagerを初期化"""
        self.logger = logging.getLogger(__name__)
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_data: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, player_id: str):
        """WebSocket接続を受け入れる"""
        await websocket.accept()
        self.active_connections[player_id] = websocket
        self.connection_data[player_id] = {
            "connected_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        
        self.logger.info(f"WebSocket connected for player: {player_id}")
        
        # 接続通知を送信
        await self.send_personal_message(
            json.dumps({
                "type": "connection_established",
                "player_id": player_id,
                "timestamp": datetime.now().isoformat()
            }),
            player_id
        )
    
    def disconnect(self, player_id: str):
        """WebSocket接続を切断"""
        if player_id in self.active_connections:
            del self.active_connections[player_id]
        if player_id in self.connection_data:
            del self.connection_data[player_id]
        
        self.logger.info(f"WebSocket disconnected for player: {player_id}")
    
    async def send_personal_message(self, message: str, player_id: str):
        """特定のプレイヤーにメッセージを送信"""
        if player_id in self.active_connections:
            try:
                await self.active_connections[player_id].send_text(message)
                self.connection_data[player_id]["last_activity"] = datetime.now().isoformat()
            except Exception as e:
                self.logger.error(f"Error sending message to {player_id}: {e}")
                # 接続が切れている場合は削除
                self.disconnect(player_id)
    
    async def broadcast(self, message: str):
        """すべての接続されたクライアントにメッセージを送信"""
        disconnected_players = []
        
        for player_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
                self.connection_data[player_id]["last_activity"] = datetime.now().isoformat()
            except Exception as e:
                self.logger.error(f"Error broadcasting to {player_id}: {e}")
                disconnected_players.append(player_id)
        
        # 切断されたクライアントを削除
        for player_id in disconnected_players:
            self.disconnect(player_id)
    
    async def send_kpi_update(self, player_id: str, kpi_data: Dict):
        """KPIデータ更新を送信"""
        message = {
            "type": "kpi_update",
            "player_id": player_id,
            "data": kpi_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_personal_message(json.dumps(message), player_id)
    
    async def send_performance_update(self, player_id: str, performance_data: Dict):
        """パフォーマンスデータ更新を送信"""
        message = {
            "type": "performance_update",
            "player_id": player_id,
            "data": performance_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.send_personal_message(json.dumps(message), player_id)
    
    async def send_match_event(self, match_id: str, event_data: Dict):
        """試合イベントを送信"""
        message = {
            "type": "match_event",
            "match_id": match_id,
            "event": event_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.broadcast(json.dumps(message))
    
    def get_active_connections(self) -> List[str]:
        """アクティブな接続のプレイヤーIDリストを取得"""
        return list(self.active_connections.keys())
    
    def get_connection_count(self) -> int:
        """アクティブな接続数を取得"""
        return len(self.active_connections)
    
    def get_connection_info(self, player_id: str) -> Dict:
        """特定のプレイヤーの接続情報を取得"""
        return self.connection_data.get(player_id, {})