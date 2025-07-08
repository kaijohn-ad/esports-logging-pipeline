"""
SQLiteストレージのテスト

TDDアプローチに従い、失敗するテストを書いてから実装する。
"""

import pytest
import sqlite3
from pathlib import Path
import tempfile
import json
from datetime import datetime

from src.storage.sqlite_store import (
    init_db, 
    SQLiteStore,
    store_match, 
    store_event, 
    get_match,
    get_events_for_match,
    get_recent_matches
)
from src.canonizer.event import Event


class TestSQLiteStorage:
    """SQLiteストレージのテストクラス"""
    
    @pytest.fixture
    def temp_db_path(self):
        """テスト用の一時データベースパスを作成"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = Path(f.name)
        yield db_path
        if db_path.exists():
            db_path.unlink()
    
    @pytest.fixture
    def sample_event(self):
        """テスト用サンプルイベント"""
        return Event(
            timestamp=100.5,
            event="kill",
            actor="test_player",
            target="enemy_player",
            meta={"weapon": "Vandal", "headshot": True}
        )
    
    def test_init_db_creates_tables(self, temp_db_path):
        """データベース初期化でテーブルが作成されることをテスト"""
        # レッド: まだ実装されていない機能をテスト
        init_db(temp_db_path)
        
        # データベースファイルが作成されているか確認
        assert temp_db_path.exists()
        
        # テーブルが正しく作成されているか確認
        con = sqlite3.connect(temp_db_path)
        cur = con.cursor()
        
        # matchテーブルの存在確認
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='match'")
        assert cur.fetchone() is not None
        
        # eventテーブルの存在確認
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event'")
        assert cur.fetchone() is not None
        
        con.close()
    
    def test_store_match(self, temp_db_path):
        """試合データの保存テスト"""
        init_db(temp_db_path)
        
        match_data = {
            "id": "test_match_001",
            "title": "League of Legends",
            "patch": "14.5",
            "timestamp": datetime.now().isoformat()
        }
        
        # レッド: store_match関数がまだ実装されていない
        store_match(temp_db_path, match_data)
        
        # データが正しく保存されているか確認
        con = sqlite3.connect(temp_db_path)
        cur = con.cursor()
        cur.execute("SELECT * FROM match WHERE id = ?", (match_data["id"],))
        result = cur.fetchone()
        
        assert result is not None
        assert result[0] == match_data["id"]
        assert result[1] == match_data["title"]
        con.close()
    
    def test_store_event(self, temp_db_path, sample_event):
        """イベントデータの保存テスト"""
        init_db(temp_db_path)
        match_id = "test_match_001"
        
        # レッド: store_event関数がまだ実装されていない
        store_event(temp_db_path, match_id, sample_event)
        
        # データが正しく保存されているか確認
        con = sqlite3.connect(temp_db_path)
        cur = con.cursor()
        cur.execute("SELECT * FROM event WHERE match_id = ?", (match_id,))
        result = cur.fetchone()
        
        assert result is not None
        assert result[1] == match_id  # match_id
        assert result[2] == sample_event.timestamp  # ts
        assert result[3] == sample_event.event  # event
        assert result[4] == sample_event.actor  # actor
        assert result[5] == sample_event.target  # target
        assert json.loads(result[6]) == sample_event.meta  # meta
        con.close()
    
    def test_get_match(self, temp_db_path):
        """試合データの取得テスト"""
        init_db(temp_db_path)
        
        # テストデータを準備
        match_data = {
            "id": "test_match_001",
            "title": "League of Legends",
            "patch": "14.5",
            "timestamp": datetime.now().isoformat()
        }
        store_match(temp_db_path, match_data)
        
        # レッド: get_match関数がまだ実装されていない
        result = get_match(temp_db_path, match_data["id"])
        
        assert result is not None
        assert result["id"] == match_data["id"]
        assert result["title"] == match_data["title"]
    
    def test_get_events_for_match(self, temp_db_path, sample_event):
        """特定の試合のイベント取得テスト"""
        init_db(temp_db_path)
        match_id = "test_match_001"
        
        # テストデータを準備
        store_event(temp_db_path, match_id, sample_event)
        
        # レッド: get_events_for_match関数がまだ実装されていない
        events = get_events_for_match(temp_db_path, match_id)
        
        assert len(events) == 1
        assert events[0].timestamp == sample_event.timestamp
        assert events[0].event == sample_event.event
    
    def test_get_recent_matches(self, temp_db_path):
        """最近の試合取得テスト"""
        init_db(temp_db_path)
        
        # 複数の試合データを準備
        matches = [
            {"id": "match_001", "title": "LoL", "patch": "14.5", "timestamp": "2025-01-01T10:00:00"},
            {"id": "match_002", "title": "LoL", "patch": "14.5", "timestamp": "2025-01-02T10:00:00"},
            {"id": "match_003", "title": "LoL", "patch": "14.5", "timestamp": "2025-01-03T10:00:00"}
        ]
        
        for match in matches:
            store_match(temp_db_path, match)
        
        # レッド: get_recent_matches関数がまだ実装されていない
        recent_matches = get_recent_matches(temp_db_path, limit=2)
        
        assert len(recent_matches) == 2
        # 最新の試合が最初に来ることを確認
        assert recent_matches[0]["id"] == "match_003"
        assert recent_matches[1]["id"] == "match_002"
    
    def test_sqlite_store_class(self, temp_db_path):
        """SQLiteStoreクラスのテスト"""
        # レッド: SQLiteStoreクラスがまだ実装されていない
        store = SQLiteStore(temp_db_path)
        
        # 初期化
        store.init()
        
        # 試合データの保存と取得
        match_data = {
            "id": "test_match_001",
            "title": "League of Legends",
            "patch": "14.5",
            "timestamp": datetime.now().isoformat()
        }
        
        store.store_match(match_data)
        result = store.get_match(match_data["id"])
        
        assert result["id"] == match_data["id"]
    
    def test_event_to_row_conversion(self, sample_event):
        """EventのSQLite行形式への変換テスト"""
        match_id = "test_match_001"
        row = sample_event.to_row(match_id)
        
        assert len(row) == 6
        assert row[0] == match_id
        assert row[1] == sample_event.timestamp
        assert row[2] == sample_event.event
        assert row[3] == sample_event.actor
        assert row[4] == sample_event.target
        assert json.loads(row[5]) == sample_event.meta