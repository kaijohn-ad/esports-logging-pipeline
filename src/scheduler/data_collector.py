"""
自動データ収集モジュール

プレイヤーデータを自動で収集し、データベースに保存
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..collectors.lol_fetcher import LoLFetcher
from ..canonizer.lol_canonizer import LoLCanonizer
from ..storage.sqlite_store import init_db
from ..config.lol_config import LoLConfig


class DataCollectionResult:
    """データ収集結果クラス"""
    
    def __init__(self):
        self.success: bool = True
        self.collected_matches: int = 0
        self.collected_events: int = 0
        self.errors: List[str] = []
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self.players_processed: int = 0
        self.players_failed: int = 0
        
    def add_error(self, error: str):
        """エラーを追加"""
        self.errors.append(error)
        self.success = False
        
    def complete(self):
        """収集完了を記録"""
        self.end_time = datetime.now()
        
    def get_duration(self) -> timedelta:
        """収集時間を取得"""
        end_time = self.end_time or datetime.now()
        return end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "success": self.success,
            "collected_matches": self.collected_matches,
            "collected_events": self.collected_events,
            "errors": self.errors,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.get_duration().total_seconds(),
            "players_processed": self.players_processed,
            "players_failed": self.players_failed
        }


class AutoDataCollector:
    """自動データ収集クラス"""
    
    def __init__(self, config: LoLConfig, db_path: str = "data/esports.db"):
        self.config = config
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
        # データベース初期化
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(self.db_path)
        
        # Fetcherの初期化
        self.fetcher = LoLFetcher(
            api_key=config.api.riot_api_key,
            region=config.api.riot_region,
            config=config
        )
        
        # Canonizer初期化
        self.canonizer = LoLCanonizer()
        
    async def collect_all_players_data(self, match_count: int = 5) -> DataCollectionResult:
        """すべての追跡プレイヤーのデータを収集"""
        result = DataCollectionResult()
        
        try:
            self.logger.info(f"Starting data collection for {len(self.config.scheduler.tracked_players)} players")
            
            for player_config in self.config.scheduler.tracked_players:
                try:
                    player_name = player_config.get("name", "Unknown")
                    puuid = player_config.get("puuid", "")
                    
                    if not puuid:
                        result.add_error(f"No PUUID found for player {player_name}")
                        result.players_failed += 1
                        continue
                    
                    self.logger.info(f"Collecting data for player: {player_name}")
                    
                    # プレイヤーデータ収集
                    player_result = await self.collect_player_data(puuid, match_count)
                    
                    # 結果を統合
                    result.collected_matches += player_result.collected_matches
                    result.collected_events += player_result.collected_events
                    result.errors.extend(player_result.errors)
                    
                    if player_result.success:
                        result.players_processed += 1
                    else:
                        result.players_failed += 1
                    
                    # レート制限対応のための待機
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    error_msg = f"Error collecting data for player {player_name}: {str(e)}"
                    self.logger.error(error_msg)
                    result.add_error(error_msg)
                    result.players_failed += 1
            
            result.complete()
            
            self.logger.info(f"Data collection completed: {result.players_processed} players processed, "
                           f"{result.collected_matches} matches, {result.collected_events} events")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error during data collection: {e}")
            result.add_error(f"Collection failed: {str(e)}")
            result.complete()
            return result
    
    async def collect_player_data(self, puuid: str, match_count: int = 5) -> DataCollectionResult:
        """特定プレイヤーのデータを収集"""
        result = DataCollectionResult()
        
        try:
            # 最新マッチID取得
            match_ids = await self.fetcher.fetch_with_enhanced_error_handling(
                self.fetcher.fetch_latest_matches, puuid, match_count
            )
            
            if not match_ids:
                result.add_error(f"No matches found for player {puuid}")
                return result
            
            # 各マッチのデータ収集
            for match_id in match_ids:
                try:
                    # 既存マッチのスキップ
                    if self._is_match_already_processed(match_id):
                        self.logger.debug(f"Skipping already processed match: {match_id}")
                        continue
                    
                    # マッチ詳細取得
                    match_data = await self.fetcher.fetch_with_enhanced_error_handling(
                        self.fetcher.fetch_match_details, match_id
                    )
                    
                    # タイムライン取得
                    timeline_data = await self.fetcher.fetch_with_enhanced_error_handling(
                        self.fetcher.fetch_timeline, match_id
                    )
                    
                    # データベースに保存
                    await self._save_match_data(match_id, match_data, timeline_data)
                    
                    result.collected_matches += 1
                    
                    # イベント数カウント
                    events = self.canonizer.timeline_to_events(timeline_data)
                    result.collected_events += len(events)
                    
                    self.logger.debug(f"Processed match {match_id}: {len(events)} events")
                    
                except Exception as e:
                    error_msg = f"Error processing match {match_id}: {str(e)}"
                    self.logger.error(error_msg)
                    result.add_error(error_msg)
            
            result.complete()
            return result
            
        except Exception as e:
            self.logger.error(f"Error collecting data for player {puuid}: {e}")
            result.add_error(f"Player data collection failed: {str(e)}")
            result.complete()
            return result
    
    def _is_match_already_processed(self, match_id: str) -> bool:
        """マッチが既に処理済みかチェック"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM match WHERE id = ?", (match_id,))
            count = cursor.fetchone()[0]
            
            conn.close()
            return count > 0
            
        except Exception as e:
            self.logger.error(f"Error checking match existence: {e}")
            return False
    
    async def _save_match_data(self, match_id: str, match_data: Dict[str, Any], timeline_data: Dict[str, Any]):
        """マッチデータをデータベースに保存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # マッチ情報を保存
            game_info = match_data.get("info", {})
            patch_version = game_info.get("gameVersion", "")
            
            cursor.execute(
                "INSERT OR IGNORE INTO match (id, title, patch, ts) VALUES (?, ?, ?, ?)",
                (match_id, "LoL", patch_version, datetime.now().isoformat())
            )
            
            # イベント情報を保存
            events = self.canonizer.timeline_to_events(timeline_data)
            event_rows = [event.to_row(match_id) for event in events]
            
            cursor.executemany(
                "INSERT INTO event (match_id, ts, event, actor, target, meta) VALUES (?, ?, ?, ?, ?, ?)",
                event_rows
            )
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"Saved match {match_id} with {len(events)} events")
            
        except Exception as e:
            self.logger.error(f"Error saving match data for {match_id}: {e}")
            raise
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """収集統計情報を取得"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 総マッチ数
            cursor.execute("SELECT COUNT(*) FROM match")
            total_matches = cursor.fetchone()[0]
            
            # 総イベント数
            cursor.execute("SELECT COUNT(*) FROM event")
            total_events = cursor.fetchone()[0]
            
            # 最新マッチ時刻
            cursor.execute("SELECT MAX(ts) FROM match")
            latest_match = cursor.fetchone()[0]
            
            # イベント種別ごとの数
            cursor.execute("SELECT event, COUNT(*) FROM event GROUP BY event")
            event_counts = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                "total_matches": total_matches,
                "total_events": total_events,
                "latest_match": latest_match,
                "event_counts": event_counts,
                "tracked_players": len(self.config.scheduler.tracked_players)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {e}")
            return {
                "total_matches": 0,
                "total_events": 0,
                "latest_match": None,
                "event_counts": {},
                "tracked_players": 0
            }
    
    def cleanup_old_data(self, retention_days: int = None):
        """古いデータのクリーンアップ"""
        retention_days = retention_days or self.config.scheduler.data_retention_days
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 古いマッチとイベントを削除
            cursor.execute("DELETE FROM match WHERE ts < ?", (cutoff_date.isoformat(),))
            cursor.execute("DELETE FROM event WHERE ts < ?", (cutoff_date.isoformat(),))
            
            deleted_matches = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted_matches} old matches older than {retention_days} days")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")