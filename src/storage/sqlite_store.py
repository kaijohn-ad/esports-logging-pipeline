"""
SQLiteストレージモジュール

データベースの初期化と基本操作を管理
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import contextmanager

# EVENT_CLASSのインポートを追加（遅延インポートで対応）
EVENT_CLASS = None

DB_PATH = Path("data/esports.db")


@contextmanager
def get_db_connection(db_path: Path):
    """データベース接続のコンテキストマネージャー"""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(path: Path = DB_PATH):
    """データベースの初期化"""
    path.parent.mkdir(parents=True, exist_ok=True)  # dataディレクトリを作成
    
    with get_db_connection(path) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS match (
            id       TEXT PRIMARY KEY,
            title    TEXT,
            patch    TEXT,
            ts       TEXT
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS event (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT,
            ts       REAL,
            event    TEXT,
            actor    TEXT,
            target   TEXT,
            meta     TEXT
        );
        """)
        conn.commit()


def store_match(db_path: Path, match_data: Dict[str, Any]) -> None:
    """試合データをデータベースに保存"""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        cur.execute("""
        INSERT OR REPLACE INTO match (id, title, patch, ts)
        VALUES (?, ?, ?, ?)
        """, (
            match_data["id"],
            match_data["title"],
            match_data["patch"],
            match_data["timestamp"]
        ))
        
        conn.commit()


def store_event(db_path: Path, match_id: str, event) -> None:
    """イベントデータをデータベースに保存"""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        # Eventオブジェクトのto_rowメソッドを使用
        row_data = event.to_row(match_id)
        
        cur.execute("""
        INSERT INTO event (match_id, ts, event, actor, target, meta)
        VALUES (?, ?, ?, ?, ?, ?)
        """, row_data)
        
        conn.commit()


def get_match(db_path: Path, match_id: str) -> Optional[Dict[str, Any]]:
    """特定の試合データを取得"""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM match WHERE id = ?", (match_id,))
        result = cur.fetchone()
        
        if result:
            return {
                "id": result[0],
                "title": result[1],
                "patch": result[2],
                "timestamp": result[3]
            }
        return None


def _get_event_class():
    """Eventクラスを遅延インポートで取得"""
    global EVENT_CLASS
    if EVENT_CLASS is None:
        import sys
        import os
        # 親ディレクトリをパスに追加
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.append(parent_dir)
        
        from canonizer.event import Event
        EVENT_CLASS = Event
    return EVENT_CLASS


def get_events_for_match(db_path: Path, match_id: str) -> List:
    """特定の試合のイベントを取得"""
    Event = _get_event_class()
    
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM event WHERE match_id = ? ORDER BY ts", (match_id,))
        results = cur.fetchall()
        
        events = []
        for row in results:
            # row: (id, match_id, ts, event, actor, target, meta)
            event = Event(
                timestamp=row[2],
                event=row[3],
                actor=row[4],
                target=row[5],
                meta=json.loads(row[6]) if row[6] else {}
            )
            events.append(event)
        
        return events


def get_recent_matches(db_path: Path, limit: int = 10) -> List[Dict[str, Any]]:
    """最近の試合を取得"""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        
        cur.execute("""
        SELECT * FROM match 
        ORDER BY ts DESC 
        LIMIT ?
        """, (limit,))
        
        results = cur.fetchall()
        
        matches = []
        for row in results:
            matches.append({
                "id": row[0],
                "title": row[1],
                "patch": row[2],
                "timestamp": row[3]
            })
        
        return matches


class SQLiteStore:
    """SQLiteストレージクラス
    
    データベース操作をカプセル化し、一貫したインターフェースを提供する
    """
    
    def __init__(self, db_path: Path):
        """
        SQLiteStoreを初期化
        
        Args:
            db_path: データベースファイルのパス
        """
        self.db_path = db_path
    
    def init(self):
        """データベースを初期化"""
        init_db(self.db_path)
    
    def store_match(self, match_data: Dict[str, Any]) -> None:
        """試合データを保存"""
        store_match(self.db_path, match_data)
    
    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """試合データを取得"""
        return get_match(self.db_path, match_id)
    
    def store_event(self, match_id: str, event) -> None:
        """イベントデータを保存"""
        store_event(self.db_path, match_id, event)
    
    def get_events_for_match(self, match_id: str) -> List:
        """特定の試合のイベントを取得"""
        return get_events_for_match(self.db_path, match_id)
    
    def get_recent_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最近の試合を取得"""
        return get_recent_matches(self.db_path, limit)