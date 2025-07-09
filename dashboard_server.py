#!/usr/bin/env python3
"""
ダッシュボードサーバー

リアルタイムWebダッシュボード用のFastAPIサーバー
"""

import uvicorn
import logging
from pathlib import Path
from src.dashboard.api import create_dashboard_app
from src.storage.sqlite_store import init_db

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_database():
    """データベースを初期化"""
    db_path = Path("data/esports.db")
    logger.info(f"データベースを初期化: {db_path}")
    init_db(db_path)

def main():
    """メイン関数"""
    logger.info("ダッシュボードサーバーを起動中...")
    
    # データベースを初期化
    setup_database()
    
    # FastAPIアプリケーションを作成
    app = create_dashboard_app()
    
    # サーバーを起動
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True,  # 開発時のみ
        workers=1
    )

if __name__ == "__main__":
    main()