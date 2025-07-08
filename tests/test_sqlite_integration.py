"""
SQLiteストレージの統合テスト

実際のワークフローをテストして、全体的な機能が正しく動作することを確認
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.storage.sqlite_store import SQLiteStore
from src.canonizer.event import Event


class TestSQLiteIntegration:
    """SQLiteストレージの統合テストクラス"""
    
    @pytest.fixture
    def temp_db_path(self):
        """テスト用の一時データベースパスを作成"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()
    
    def test_complete_match_workflow(self, temp_db_path):
        """完全な試合ワークフローのテスト"""
        # ストレージを初期化
        store = SQLiteStore(temp_db_path)
        store.init()
        
        # 試合データを作成・保存
        match_data = {
            "id": "integration_match_001",
            "title": "League of Legends",
            "patch": "14.5",
            "timestamp": datetime.now().isoformat()
        }
        store.store_match(match_data)
        
        # 複数のイベントを作成・保存
        events = [
            Event(timestamp=100.0, event="kill", actor="player1", target="enemy1", 
                  meta={"weapon": "Sword", "location": "jungle"}),
            Event(timestamp=150.5, event="death", actor="player1", target=None,
                  meta={"killer": "enemy2", "assist": ["enemy3"]}),
            Event(timestamp=200.0, event="ult", actor="player2", target="enemy1",
                  meta={"ability": "Divine Judgement", "damage": 500})
        ]
        
        for event in events:
            store.store_event(match_data["id"], event)
        
        # データの取得と検証
        retrieved_match = store.get_match(match_data["id"])
        assert retrieved_match is not None
        assert retrieved_match["id"] == match_data["id"]
        assert retrieved_match["title"] == match_data["title"]
        
        # イベントの取得と検証
        retrieved_events = store.get_events_for_match(match_data["id"])
        assert len(retrieved_events) == 3
        
        # イベントの順序確認（タイムスタンプ順）
        assert retrieved_events[0].timestamp == 100.0
        assert retrieved_events[0].event == "kill"
        assert retrieved_events[1].timestamp == 150.5
        assert retrieved_events[1].event == "death"
        assert retrieved_events[2].timestamp == 200.0
        assert retrieved_events[2].event == "ult"
        
        # メタデータの確認
        assert retrieved_events[0].meta["weapon"] == "Sword"
        assert retrieved_events[1].meta["killer"] == "enemy2"
        assert retrieved_events[2].meta["damage"] == 500
    
    def test_multiple_matches_workflow(self, temp_db_path):
        """複数試合のワークフローテスト"""
        store = SQLiteStore(temp_db_path)
        store.init()
        
        # 複数の試合を作成
        matches = [
            {
                "id": "match_001",
                "title": "LoL",
                "patch": "14.5",
                "timestamp": "2025-01-01T10:00:00"
            },
            {
                "id": "match_002", 
                "title": "LoL",
                "patch": "14.5",
                "timestamp": "2025-01-02T15:30:00"
            },
            {
                "id": "match_003",
                "title": "LoL", 
                "patch": "14.6",
                "timestamp": "2025-01-03T20:45:00"
            }
        ]
        
        # 試合データを保存
        for match in matches:
            store.store_match(match)
            
            # 各試合にイベントを追加
            event = Event(
                timestamp=60.0,
                event="first_blood",
                actor="player1",
                target="enemy1",
                meta={"gold_reward": 400}
            )
            store.store_event(match["id"], event)
        
        # 最近の試合を取得
        recent_matches = store.get_recent_matches(limit=2)
        assert len(recent_matches) == 2
        
        # 最新の試合が最初に来ることを確認
        assert recent_matches[0]["id"] == "match_003"
        assert recent_matches[1]["id"] == "match_002"
        
        # 各試合のイベントが正しく保存されていることを確認
        for match in matches:
            events = store.get_events_for_match(match["id"])
            assert len(events) == 1
            assert events[0].event == "first_blood"
            assert events[0].meta["gold_reward"] == 400
    
    def test_empty_database_behavior(self, temp_db_path):
        """空のデータベースの動作テスト"""
        store = SQLiteStore(temp_db_path)
        store.init()
        
        # 存在しない試合の取得
        result = store.get_match("nonexistent_match")
        assert result is None
        
        # 存在しない試合のイベント取得
        events = store.get_events_for_match("nonexistent_match")
        assert len(events) == 0
        
        # 空のデータベースから最近の試合を取得
        recent_matches = store.get_recent_matches()
        assert len(recent_matches) == 0