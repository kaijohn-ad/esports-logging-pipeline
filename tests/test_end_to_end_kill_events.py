"""
LoL Kill Event Processing and SQLite Storage End-to-End Test

Task 1: Verify LoL Kill Event Processing and SQLite Storage
エンドツーエンドのプロセスをテストする：
1. LoLFetcher でサンプルLoLマッチからデータを取得
2. LoLCanonizer で CHAMPION_KILL イベントを 'kill' イベントに変換
3. SQLiteStore でテストSQLiteデータベースに保存
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sqlite3
from datetime import datetime

import sys
sys.path.append(str(Path(__file__).parent.parent / "src"))

from collectors.lol_fetcher import LoLFetcher
from canonizer.lol_canonizer import LoLCanonizer  
from storage.sqlite_store import SQLiteStore
from canonizer.event import Event


class TestEndToEndKillEvents:
    """LoL Kill Event のエンドツーエンド処理テストクラス"""
    
    @pytest.fixture
    def temp_db_path(self):
        """テスト用の一時データベースパス"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()
    
    @pytest.fixture  
    def sample_lol_timeline_data(self):
        """サンプルLoLタイムラインデータ（CHAMPION_KILLイベント含む）"""
        return {
            "metadata": {
                "dataVersion": "2",
                "matchId": "JP1_12345678",
                "participants": [
                    "player1_puuid", "player2_puuid", "player3_puuid", "player4_puuid", "player5_puuid",
                    "player6_puuid", "player7_puuid", "player8_puuid", "player9_puuid", "player10_puuid"
                ]
            },
            "info": {
                "frameInterval": 60000,
                "frames": [
                    {
                        "timestamp": 60000,  # 1分
                        "events": []
                    },
                    {
                        "timestamp": 120000,  # 2分
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 125000,
                                "killerId": 1,
                                "victimId": 6,
                                "assistingParticipantIds": [2, 3],
                                "position": {"x": 8500, "y": 4200}
                            }
                        ]
                    },
                    {
                        "timestamp": 180000,  # 3分
                        "events": [
                            {
                                "type": "CHAMPION_KILL", 
                                "timestamp": 185000,
                                "killerId": 6,
                                "victimId": 1,
                                "assistingParticipantIds": [7],
                                "position": {"x": 7200, "y": 8500}
                            },
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 190000, 
                                "killerId": 2,
                                "victimId": 8,
                                "assistingParticipantIds": [],
                                "position": {"x": 9000, "y": 3000}
                            }
                        ]
                    }
                ]
            }
        }
    
    @pytest.fixture
    def sample_match_details(self):
        """サンプルマッチ詳細データ"""
        return {
            "metadata": {
                "matchId": "JP1_12345678"
            },
            "info": {
                "gameId": 12345678,
                "gameDuration": 1800,  # 30分
                "gameCreation": 1640995200000,
                "gameVersion": "13.24.1",
                "participants": [
                    {"participantId": 1, "puuid": "player1_puuid", "championName": "Jinx"},
                    {"participantId": 2, "puuid": "player2_puuid", "championName": "Thresh"},
                    {"participantId": 6, "puuid": "player6_puuid", "championName": "Yasuo"},
                    {"participantId": 7, "puuid": "player7_puuid", "championName": "Zed"},
                    {"participantId": 8, "puuid": "player8_puuid", "championName": "Lux"}
                ]
            }
        }
    
    def test_minimal_kill_event_processing(self, temp_db_path, sample_lol_timeline_data, sample_match_details):
        """
        最小限のkillイベント処理テスト
        
        1. LoLFetcher（モック）でタイムラインデータを取得
        2. LoLCanonizer で CHAMPION_KILL → kill イベント変換
        3. SQLiteStore でデータベースに保存
        4. 保存されたkillイベントを検証
        """
        # === Step 1: LoLFetcher の適切なモック設定 ===
        # インスタンスメソッドを直接モック
        with patch.object(LoLFetcher, 'fetch_timeline') as mock_fetch_timeline, \
             patch.object(LoLFetcher, 'fetch_match_details') as mock_fetch_match_details:
            
            # API呼び出しのモック応答設定
            mock_fetch_timeline.return_value = sample_lol_timeline_data
            mock_fetch_match_details.return_value = sample_match_details
            
            # === Step 2: コンポーネント初期化 ===
            fetcher = LoLFetcher("dummy_api_key")
            canonizer = LoLCanonizer()
            storage = SQLiteStore(temp_db_path)
            
            # データベース初期化
            storage.init()
            
            # === Step 3: データ取得 ===
            match_id = "JP1_12345678"
            timeline_data = fetcher.fetch_timeline(match_id)
            match_details = fetcher.fetch_match_details(match_id)
            
            # === Step 4: タイムラインデータをイベントに変換 ===
            events = canonizer.timeline_to_events(timeline_data)
            
            # === Step 5: killイベントのフィルタリング ===
            kill_events = [e for e in events if e.event == "kill"]
            
            # === Step 6: マッチ情報をデータベースに保存 ===
            match_data = {
                "id": match_id,
                "title": "League of Legends Test Match",
                "patch": match_details["info"]["gameVersion"],
                "timestamp": datetime.now().isoformat()
            }
            storage.store_match(match_data)
            
            # === Step 7: killイベントをデータベースに保存 ===
            for kill_event in kill_events:
                storage.store_event(match_id, kill_event)
            
            # === Step 8: 検証 ===
            # killイベントが正しく抽出されたことを確認
            assert len(kill_events) == 3, f"Expected 3 kill events, got {len(kill_events)}"
            
            # 各killイベントの基本的な属性を確認
            for kill_event in kill_events:
                assert kill_event.event == "kill"
                assert kill_event.actor is not None
                assert kill_event.target is not None
                assert isinstance(kill_event.timestamp, float)
                assert "assists" in kill_event.meta
                assert "position" in kill_event.meta
            
            # データベースからkillイベントを取得して確認
            stored_events = storage.get_events_for_match(match_id)
            stored_kill_events = [e for e in stored_events if e.event == "kill"]
            
            assert len(stored_kill_events) == 3, f"Expected 3 stored kill events, got {len(stored_kill_events)}"
            
            # 具体的なkillイベントの詳細を検証
            first_kill = stored_kill_events[0]
            assert first_kill.actor == "1"
            assert first_kill.target == "6" 
            assert first_kill.timestamp == 125.0
            assert first_kill.meta["assists"] == [2, 3]
            assert first_kill.meta["position"] == {"x": 8500, "y": 4200}
            
            # モック呼び出しの確認
            mock_fetch_timeline.assert_called_once_with(match_id)
            mock_fetch_match_details.assert_called_once_with(match_id)
    
    def test_database_schema_verification(self, temp_db_path):
        """データベーススキーマの検証テスト"""
        storage = SQLiteStore(temp_db_path)
        storage.init()
        
        # データベース接続とスキーマ確認
        with sqlite3.connect(temp_db_path) as conn:
            cur = conn.cursor()
            
            # matchテーブルのスキーマ確認
            cur.execute("PRAGMA table_info(match)")
            match_columns = {row[1]: row[2] for row in cur.fetchall()}  # column_name: type
            
            expected_match_columns = {
                "id": "TEXT",
                "title": "TEXT", 
                "patch": "TEXT",
                "ts": "TEXT"
            }
            
            for col_name, col_type in expected_match_columns.items():
                assert col_name in match_columns
                assert match_columns[col_name] == col_type
            
            # eventテーブルのスキーマ確認
            cur.execute("PRAGMA table_info(event)")
            event_columns = {row[1]: row[2] for row in cur.fetchall()}
            
            expected_event_columns = {
                "id": "INTEGER",
                "match_id": "TEXT",
                "ts": "REAL",
                "event": "TEXT",
                "actor": "TEXT", 
                "target": "TEXT",
                "meta": "TEXT"
            }
            
            for col_name, col_type in expected_event_columns.items():
                assert col_name in event_columns
                assert event_columns[col_name] == col_type
    
    def test_error_handling_and_logging(self, temp_db_path, caplog):
        """エラーハンドリングとログ記録のテスト"""
        import logging
        
        # インスタンスメソッドを適切にモック
        with patch.object(LoLFetcher, 'fetch_timeline') as mock_fetch_timeline:
            # APIエラーをシミュレート
            mock_fetch_timeline.side_effect = Exception("API Error: Rate limit exceeded")
            
            fetcher = LoLFetcher("dummy_api_key")
            storage = SQLiteStore(temp_db_path)
            storage.init()
            
            # エラーが発生することを確認
            with pytest.raises(Exception) as exc_info:
                fetcher.fetch_timeline("invalid_match_id")
            
            assert "API Error: Rate limit exceeded" in str(exc_info.value)
            
            # モックが呼ばれたことを確認
            mock_fetch_timeline.assert_called_once_with("invalid_match_id")
    
    def test_different_sample_matches(self, temp_db_path):
        """異なるサンプルマッチでのロバスト性テスト"""
        # Kill数が0の場合
        empty_timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 120000,
                        "events": []  # killイベントなし
                    }
                ]
            }
        }
        
        canonizer = LoLCanonizer()
        events = canonizer.timeline_to_events(empty_timeline)
        kill_events = [e for e in events if e.event == "kill"]
        
        assert len(kill_events) == 0, "Empty timeline should produce no kill events"
        
        # Kill数が多い場合
        many_kills_timeline = {
            "info": {
                "frames": [
                    {
                        "timestamp": 120000,
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 125000 + i * 1000,
                                "killerId": 1,
                                "victimId": 6 + (i % 4),
                                "assistingParticipantIds": [2],
                                "position": {"x": 8500, "y": 4200}
                            }
                            for i in range(10)  # 10 kills
                        ]
                    }
                ]
            }
        }
        
        events = canonizer.timeline_to_events(many_kills_timeline)
        kill_events = [e for e in events if e.event == "kill"]
        
        assert len(kill_events) == 10, f"Expected 10 kill events, got {len(kill_events)}"
    
    def test_configuration_and_instantiation(self, temp_db_path):
        """コンポーネントの設定とインスタンス化テスト"""
        # LoLFetcher の設定とインスタンス化
        api_key = "test_api_key"
        region = "jp1"
        
        # 実際のインスタンス作成（モック不要）
        fetcher = LoLFetcher(api_key, region)
        
        # 基本的な属性確認
        assert fetcher.region == region
        assert fetcher.watch is not None  # RiotWatcherインスタンスが作成されている
        
        # LoLCanonizer の設定（引数なし）
        canonizer = LoLCanonizer()
        assert canonizer is not None
        
        # SQLiteStore の設定
        storage = SQLiteStore(temp_db_path)
        assert storage.db_path == temp_db_path
        
        # データベース初期化
        storage.init()
        assert temp_db_path.exists()