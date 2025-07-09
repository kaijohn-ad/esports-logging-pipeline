#!/usr/bin/env python3
"""
ダッシュボードテストファイル

リアルタイムWebダッシュボードの動作確認用テストスクリプト
"""

import asyncio
import requests
import json
from pathlib import Path
from src.dashboard.api import create_dashboard_app
from src.storage.sqlite_store import init_db, store_match
from src.canonizer.event import Event


def setup_test_data():
    """テストデータを設定"""
    db_path = Path("data/esports.db")
    init_db(db_path)
    
    # テスト用マッチデータ
    test_match = {
        "id": "test_match_001",
        "title": "Test Match",
        "patch": "14.1",
        "timestamp": "2025-01-21T10:30:00Z"
    }
    
    store_match(db_path, test_match)
    
    # テスト用イベントデータ
    test_events = [
        Event(
            timestamp=300.5,
            event="champion_kill",
            actor="test_player_1",
            target="test_player_2",
            meta={"position": "bot"}
        ),
        Event(
            timestamp=450.2,
            event="champion_kill",
            actor="test_player_2",
            target="test_player_1",
            meta={"position": "mid"}
        )
    ]
    
    from src.storage.sqlite_store import store_event
    for event in test_events:
        store_event(db_path, "test_match_001", event)
    
    print("✅ テストデータが正常に設定されました")


def test_api_endpoints():
    """APIエンドポイントをテスト"""
    base_url = "http://localhost:8000"
    
    try:
        # ルートエンドポイント
        response = requests.get(f"{base_url}/")
        print(f"Root endpoint: {response.status_code} - {response.json()}")
        
        # プレイヤー一覧
        response = requests.get(f"{base_url}/api/players")
        print(f"Players endpoint: {response.status_code}")
        players = response.json()
        print(f"Found {len(players.get('players', []))} players")
        
        # プレイヤーKPI（最初のプレイヤーがいる場合）
        if players.get('players'):
            player_id = players['players'][0]['id']
            response = requests.get(f"{base_url}/api/players/{player_id}/kpi")
            print(f"Player KPI endpoint: {response.status_code}")
        
        print("✅ APIエンドポイントテストが完了しました")
        
    except requests.exceptions.ConnectionError:
        print("❌ サーバーに接続できません。dashboard_server.pyを起動してください")
    except Exception as e:
        print(f"❌ テストエラー: {e}")


def test_websocket_connection():
    """WebSocket接続をテスト"""
    import websockets
    import asyncio
    
    async def test_websocket():
        uri = "ws://localhost:8000/ws/test_player_1"
        try:
            async with websockets.connect(uri) as websocket:
                print("✅ WebSocket接続が成功しました")
                
                # メッセージを待機
                message = await asyncio.wait_for(websocket.recv(), timeout=5)
                data = json.loads(message)
                print(f"Received: {data}")
                
        except Exception as e:
            print(f"❌ WebSocket接続エラー: {e}")
    
    asyncio.run(test_websocket())


def main():
    """メイン関数"""
    print("🚀 ダッシュボードテストを開始...")
    
    print("\n1. テストデータセットアップ")
    setup_test_data()
    
    print("\n2. APIエンドポイントテスト")
    test_api_endpoints()
    
    print("\n3. WebSocket接続テスト")
    test_websocket_connection()
    
    print("\n✨ テスト完了!")
    print("\n📋 次のステップ:")
    print("1. バックエンドサーバーを起動: python dashboard_server.py")
    print("2. フロントエンドサーバーを起動: cd dashboard_frontend && npm start")
    print("3. ブラウザで http://localhost:3000 を開く")


if __name__ == "__main__":
    main()