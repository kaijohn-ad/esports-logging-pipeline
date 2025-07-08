"""
SQLiteストレージモジュール

データベースの初期化と基本操作を管理
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/esports.db")


def init_db(path: Path = DB_PATH):
    """データベースの初期化"""
    path.parent.mkdir(parents=True, exist_ok=True)  # dataディレクトリを作成
    
    con = sqlite3.connect(path)
    cur = con.cursor()
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
    con.commit()
    con.close()