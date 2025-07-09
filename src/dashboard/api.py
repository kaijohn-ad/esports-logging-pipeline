"""
ダッシュボード用 FastAPI REST API

プレイヤーパフォーマンスメトリクスのためのAPIエンドポイント
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

from ..storage.sqlite_store import SQLiteStore
from ..kpi.lol_kpi_calculator import LoLKPICalculator
from ..kpi.lol_kpi_config import LoLKPIConfig
from ..kpi.kpi_result import KPIResult
from .websocket import WebSocketManager


class DashboardAPI:
    """ダッシュボード用API管理クラス"""
    
    def __init__(self, db_path: Path = Path("data/esports.db")):
        """
        DashboardAPIを初期化
        
        Args:
            db_path: データベースファイルのパス
        """
        self.logger = logging.getLogger(__name__)
        self.db_store = SQLiteStore(db_path)
        self.kpi_calculator = LoLKPICalculator()
        self.websocket_manager = WebSocketManager()
        
        # FastAPIアプリケーションを初期化
        self.app = FastAPI(
            title="eSports Dashboard API",
            description="リアルタイムプレイヤーパフォーマンスメトリクス API",
            version="1.0.0"
        )
        
        # CORS設定
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],  # React dev server
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """APIルートを設定"""
        
        @self.app.get("/")
        async def root():
            """ルートエンドポイント"""
            return {"message": "eSports Dashboard API", "version": "1.0.0"}
        
        @self.app.get("/api/players")
        async def get_players():
            """プレイヤー一覧を取得"""
            try:
                # データベースから最近の試合を取得
                recent_matches = self.db_store.get_recent_matches(limit=50)
                
                # プレイヤーIDを収集
                player_ids = set()
                for match in recent_matches:
                    events = self.db_store.get_events_for_match(match["id"])
                    for event in events:
                        if event.actor:
                            player_ids.add(event.actor)
                
                players = [{"id": pid, "name": pid} for pid in player_ids]
                return {"players": players}
                
            except Exception as e:
                self.logger.error(f"Error getting players: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/api/players/{player_id}/kpi")
        async def get_player_kpi(
            player_id: str,
            days: int = Query(7, description="過去何日間のデータを取得するか"),
            match_limit: int = Query(10, description="最大試合数")
        ):
            """プレイヤーのKPIデータを取得"""
            try:
                # 最近の試合を取得
                recent_matches = self.db_store.get_recent_matches(limit=match_limit)
                
                kpi_data = []
                for match in recent_matches:
                    try:
                        # TODO: 実際のマッチデータを取得するロジックを実装
                        # 現在は模擬データを使用
                        mock_match_data = self._create_mock_match_data(match["id"], player_id)
                        kpi_result = self.kpi_calculator.calculate_advanced_kpi(
                            mock_match_data, player_id
                        )
                        
                        kpi_data.append({
                            "match_id": match["id"],
                            "timestamp": match["timestamp"],
                            "kpi": kpi_result.dict()
                        })
                    except Exception as e:
                        self.logger.warning(f"Error calculating KPI for match {match['id']}: {e}")
                        continue
                
                return {
                    "player_id": player_id,
                    "kpi_data": kpi_data,
                    "summary": self._calculate_kpi_summary(kpi_data)
                }
                
            except Exception as e:
                self.logger.error(f"Error getting KPI for player {player_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/api/players/{player_id}/performance")
        async def get_player_performance(
            player_id: str,
            time_range: str = Query("week", description="時間範囲: day, week, month")
        ):
            """プレイヤーのパフォーマンス履歴を取得"""
            try:
                # 時間範囲に基づいてデータを取得
                time_ranges = {
                    "day": 1,
                    "week": 7,
                    "month": 30
                }
                
                days = time_ranges.get(time_range, 7)
                
                # パフォーマンスデータを取得
                performance_data = await self._get_performance_data(player_id, days)
                
                return {
                    "player_id": player_id,
                    "time_range": time_range,
                    "performance": performance_data
                }
                
            except Exception as e:
                self.logger.error(f"Error getting performance for player {player_id}: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.get("/api/players/compare")
        async def compare_players(
            player_ids: str = Query(..., description="比較するプレイヤーID（カンマ区切り）"),
            metric: str = Query("kda", description="比較するメトリック")
        ):
            """複数プレイヤーの比較データを取得"""
            try:
                player_list = [pid.strip() for pid in player_ids.split(",")]
                
                if len(player_list) > 5:
                    raise HTTPException(status_code=400, detail="最大5名まで比較可能です")
                
                comparison_data = []
                for player_id in player_list:
                    kpi_data = await self._get_player_kpi_data(player_id)
                    comparison_data.append({
                        "player_id": player_id,
                        "data": kpi_data
                    })
                
                return {
                    "players": player_list,
                    "metric": metric,
                    "comparison": comparison_data
                }
                
            except Exception as e:
                self.logger.error(f"Error comparing players: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
        @self.app.websocket("/ws/{player_id}")
        async def websocket_endpoint(websocket: WebSocket, player_id: str):
            """WebSocketエンドポイント"""
            await self.websocket_manager.connect(websocket, player_id)
            try:
                while True:
                    # リアルタイムデータ更新のシミュレーション
                    await asyncio.sleep(5)
                    
                    # 最新のKPIデータを取得
                    kpi_data = await self._get_player_kpi_data(player_id)
                    
                    # WebSocketでデータを送信
                    await self.websocket_manager.send_personal_message(
                        json.dumps({
                            "type": "kpi_update",
                            "player_id": player_id,
                            "data": kpi_data,
                            "timestamp": datetime.now().isoformat()
                        }),
                        player_id
                    )
                    
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(player_id)
    
    def _create_mock_match_data(self, match_id: str, player_id: str) -> Dict[str, Any]:
        """模擬マッチデータを作成（テスト用）"""
        return {
            "info": {
                "gameDuration": 1800,  # 30分
                "participants": [
                    {
                        "puuid": player_id,
                        "championName": "Jinx",
                        "kills": 8,
                        "deaths": 3,
                        "assists": 12,
                        "totalMinionsKilled": 165,
                        "neutralMinionsKilled": 20,
                        "goldEarned": 12500,
                        "totalDamageDealtToChampions": 18000,
                        "visionScore": 15,
                        "wardsPlaced": 8,
                        "wardsKilled": 3,
                        "firstBloodKill": False,
                        "firstBloodAssist": True
                    }
                ]
            }
        }
    
    def _calculate_kpi_summary(self, kpi_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """KPIデータの要約を計算"""
        if not kpi_data:
            return {}
        
        # 平均値を計算
        total_kda = sum(data["kpi"]["kda"] for data in kpi_data)
        total_cs = sum(data["kpi"]["cs_per_10min"] for data in kpi_data)
        total_gold = sum(data["kpi"]["gold_per_min"] for data in kpi_data)
        
        count = len(kpi_data)
        
        return {
            "avg_kda": round(total_kda / count, 2),
            "avg_cs_per_10min": round(total_cs / count, 2),
            "avg_gold_per_min": round(total_gold / count, 2),
            "total_games": count
        }
    
    async def _get_performance_data(self, player_id: str, days: int) -> Dict[str, Any]:
        """パフォーマンスデータを取得"""
        # TODO: 実際のデータベースクエリを実装
        return {
            "kda_trend": [2.1, 2.3, 1.8, 2.5, 2.7],
            "cs_trend": [7.2, 7.5, 6.8, 7.1, 7.4],
            "win_rate": 0.65,
            "games_played": 12
        }
    
    async def _get_player_kpi_data(self, player_id: str) -> Dict[str, Any]:
        """プレイヤーのKPIデータを取得"""
        # 最新の試合データを取得
        recent_matches = self.db_store.get_recent_matches(limit=1)
        
        if not recent_matches:
            return {}
        
        match = recent_matches[0]
        mock_match_data = self._create_mock_match_data(match["id"], player_id)
        
        try:
            kpi_result = self.kpi_calculator.calculate_advanced_kpi(
                mock_match_data, player_id
            )
            return kpi_result.dict()
        except Exception as e:
            self.logger.error(f"Error calculating KPI: {e}")
            return {}


def create_dashboard_app(db_path: Path = Path("data/esports.db")) -> FastAPI:
    """ダッシュボードアプリケーションを作成"""
    dashboard_api = DashboardAPI(db_path)
    return dashboard_api.app