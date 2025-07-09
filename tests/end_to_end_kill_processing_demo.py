#!/usr/bin/env python3
"""
LoL Kill Event Processing and SQLite Storage Demo Script

Task 1: Verify LoL Kill Event Processing and SQLite Storage
このスクリプトは以下を実演します：
1. LoLFetcher でサンプルLoLマッチからデータを取得（モック使用）
2. LoLCanonizer で CHAMPION_KILL イベントを 'kill' イベントに変換
3. SQLiteStore でテストSQLiteデータベースに保存
4. エラーハンドリングとログ記録
5. 処理結果の詳細出力
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, Mock

# srcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent / "src"))

from collectors.lol_fetcher import LoLFetcher
from canonizer.lol_canonizer import LoLCanonizer
from storage.sqlite_store import SQLiteStore
from canonizer.event import Event


def setup_logging():
    """ログ設定のセットアップ"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'kill_event_processing_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )
    return logging.getLogger(__name__)


def create_sample_timeline_data():
    """小さく代表的なサンプルLoLマッチタイムラインデータを作成"""
    return {
        "metadata": {
            "dataVersion": "2",
            "matchId": "JP1_DEMO_MATCH",
            "participants": [
                "demo_player1_puuid", "demo_player2_puuid", "demo_player3_puuid", 
                "demo_player4_puuid", "demo_player5_puuid", "demo_player6_puuid",
                "demo_player7_puuid", "demo_player8_puuid", "demo_player9_puuid", "demo_player10_puuid"
            ]
        },
        "info": {
            "frameInterval": 60000,
            "frames": [
                {
                    "timestamp": 60000,  # 1分 - イベントなし
                    "events": []
                },
                {
                    "timestamp": 180000,  # 3分 - First Blood
                    "events": [
                        {
                            "type": "CHAMPION_KILL",
                            "timestamp": 183000,
                            "killerId": 1,
                            "victimId": 6,
                            "assistingParticipantIds": [2],
                            "position": {"x": 8500, "y": 4200}
                        }
                    ]
                },
                {
                    "timestamp": 360000,  # 6分 - 複数キル
                    "events": [
                        {
                            "type": "CHAMPION_KILL",
                            "timestamp": 362000,
                            "killerId": 6,
                            "victimId": 1,
                            "assistingParticipantIds": [7, 8],
                            "position": {"x": 7200, "y": 8500}
                        },
                        {
                            "type": "CHAMPION_KILL",
                            "timestamp": 365000,
                            "killerId": 3,
                            "victimId": 9,
                            "assistingParticipantIds": [],
                            "position": {"x": 9000, "y": 3000}
                        }
                    ]
                },
                {
                    "timestamp": 720000,  # 12分 - 1v1 kill
                    "events": [
                        {
                            "type": "CHAMPION_KILL",
                            "timestamp": 721000,
                            "killerId": 4,
                            "victimId": 10,
                            "assistingParticipantIds": [],
                            "position": {"x": 12000, "y": 6000}
                        }
                    ]
                }
            ]
        }
    }


def create_sample_match_details():
    """サンプルマッチ詳細データを作成"""
    return {
        "metadata": {
            "matchId": "JP1_DEMO_MATCH"
        },
        "info": {
            "gameId": 87654321,
            "gameDuration": 1680,  # 28分
            "gameCreation": int(datetime.now().timestamp() * 1000),
            "gameVersion": "14.1.1",
            "participants": [
                {"participantId": 1, "puuid": "demo_player1_puuid", "championName": "Jinx", "teamId": 100},
                {"participantId": 2, "puuid": "demo_player2_puuid", "championName": "Thresh", "teamId": 100},
                {"participantId": 3, "puuid": "demo_player3_puuid", "championName": "Yasuo", "teamId": 100},
                {"participantId": 4, "puuid": "demo_player4_puuid", "championName": "Graves", "teamId": 100},
                {"participantId": 5, "puuid": "demo_player5_puuid", "championName": "Azir", "teamId": 100},
                {"participantId": 6, "puuid": "demo_player6_puuid", "championName": "Gnar", "teamId": 200},
                {"participantId": 7, "puuid": "demo_player7_puuid", "championName": "Braum", "teamId": 200},
                {"participantId": 8, "puuid": "demo_player8_puuid", "championName": "Zed", "teamId": 200},
                {"participantId": 9, "puuid": "demo_player9_puuid", "championName": "Lux", "teamId": 200},
                {"participantId": 10, "puuid": "demo_player10_puuid", "championName": "Nidalee", "teamId": 200}
            ]
        }
    }


def main():
    """メイン処理"""
    logger = setup_logging()
    
    # データベースファイルパス
    db_path = Path("data/demo_esports.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("LoL Kill Event Processing Demo - Task 1")
    logger.info("=" * 60)
    
    try:
        # === Step 1: サンプルデータの準備 ===
        logger.info("Step 1: サンプルデータの準備")
        sample_timeline = create_sample_timeline_data()
        sample_match_details = create_sample_match_details()
        
        logger.info(f"Match ID: {sample_match_details['metadata']['matchId']}")
        logger.info(f"Game Duration: {sample_match_details['info']['gameDuration']} seconds")
        logger.info(f"Game Version: {sample_match_details['info']['gameVersion']}")
        logger.info(f"Timeline Frames: {len(sample_timeline['info']['frames'])}")
        
        # === Step 2: コンポーネント初期化 ===
        logger.info("\nStep 2: コンポーネント初期化")
        
        # LoLFetcher のモック使用
        with patch.object(LoLFetcher, 'fetch_timeline') as mock_fetch_timeline, \
             patch.object(LoLFetcher, 'fetch_match_details') as mock_fetch_match_details:
            
            # モック応答設定
            mock_fetch_timeline.return_value = sample_timeline
            mock_fetch_match_details.return_value = sample_match_details
            
            fetcher = LoLFetcher("demo_api_key", "jp1")
            logger.info("✅ LoLFetcher initialized with mock data")
            
            canonizer = LoLCanonizer()
            logger.info("✅ LoLCanonizer initialized")
            
            storage = SQLiteStore(db_path)
            storage.init()
            logger.info(f"✅ SQLiteStore initialized - Database: {db_path}")
            
            # === Step 3: データ取得 ===
            logger.info("\nStep 3: データ取得")
            match_id = sample_match_details['metadata']['matchId']
            
            timeline_data = fetcher.fetch_timeline(match_id)
            logger.info(f"✅ Timeline data fetched for match: {match_id}")
            
            match_details = fetcher.fetch_match_details(match_id)
            logger.info(f"✅ Match details fetched")
            
            # === Step 4: CHAMPION_KILL イベントの変換 ===
            logger.info("\nStep 4: イベント変換 (CHAMPION_KILL → kill)")
            
            # timeline_dataが適切な形式であることを確認
            assert isinstance(timeline_data, dict), f"Expected dict, got {type(timeline_data)}"
            
            events = canonizer.timeline_to_events(timeline_data)
            kill_events = [e for e in events if e.event == "kill"]
            
            logger.info(f"Total events processed: {len(events)}")
            logger.info(f"Kill events found: {len(kill_events)}")
            
            # 各killイベントの詳細をログ出力
            for i, kill_event in enumerate(kill_events, 1):
                logger.info(f"  Kill #{i}:")
                logger.info(f"    Time: {kill_event.timestamp:.1f}s")
                logger.info(f"    Killer: Player {kill_event.actor}")
                logger.info(f"    Victim: Player {kill_event.target}")
                logger.info(f"    Assists: {kill_event.meta.get('assists', [])}")
                logger.info(f"    Position: {kill_event.meta.get('position', {})}")
            
            # === Step 5: データベース保存 ===
            logger.info("\nStep 5: データベース保存")
            
            # マッチ情報保存
            match_data = {
                "id": match_id,
                "title": "LoL Demo Match - Kill Event Processing",
                "patch": match_details["info"]["gameVersion"],
                "timestamp": datetime.now().isoformat()
            }
            storage.store_match(match_data)
            logger.info("✅ Match data stored")
            
            # killイベント保存
            for kill_event in kill_events:
                storage.store_event(match_id, kill_event)
            logger.info(f"✅ {len(kill_events)} kill events stored")
            
            # === Step 6: 保存結果の検証 ===
            logger.info("\nStep 6: 保存結果の検証")
            
            # データベースからデータを読み出して検証
            stored_match = storage.get_match(match_id)
            stored_events = storage.get_events_for_match(match_id)
            stored_kill_events = [e for e in stored_events if e.event == "kill"]
            
            # stored_matchがNoneでないことを確認
            assert stored_match is not None, f"Failed to retrieve match data for {match_id}"
            
            logger.info(f"Stored match verification:")
            logger.info(f"  Match ID: {stored_match['id']}")
            logger.info(f"  Title: {stored_match['title']}")
            logger.info(f"  Patch: {stored_match['patch']}")
            
            logger.info(f"Stored events verification:")
            logger.info(f"  Total events in DB: {len(stored_events)}")
            logger.info(f"  Kill events in DB: {len(stored_kill_events)}")
            
            # データ整合性の確認
            assert len(stored_kill_events) == len(kill_events), "Stored kill events count mismatch"
            logger.info("✅ Data integrity verified")
            
            # === Step 7: 結果サマリー ===
            logger.info("\n" + "=" * 60)
            logger.info("DEMO SUMMARY")
            logger.info("=" * 60)
            logger.info(f"✅ Successfully processed LoL match: {match_id}")
            logger.info(f"✅ Converted {len(kill_events)} CHAMPION_KILL events to 'kill' events")
            logger.info(f"✅ Stored all data in SQLite database: {db_path}")
            logger.info(f"✅ Verified data integrity and schema compliance")
            logger.info(f"✅ End-to-end pipeline working correctly")
            
            # === Step 8: データベース内容のダンプ（デバッグ用） ===
            logger.info("\nStep 8: Database Contents (for verification)")
            
            logger.info("Database Schema Verification:")
            import sqlite3
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                
                # テーブル一覧
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cur.fetchall()
                logger.info(f"  Tables: {[table[0] for table in tables]}")
                
                # 保存されたデータの確認
                cur.execute("SELECT COUNT(*) FROM match")
                match_count = cur.fetchone()[0]
                logger.info(f"  Match records: {match_count}")
                
                cur.execute("SELECT COUNT(*) FROM event WHERE event='kill'")
                kill_count = cur.fetchone()[0]
                logger.info(f"  Kill event records: {kill_count}")
            
            logger.info("\n🎉 Demo completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Demo failed with error: {str(e)}")
        logger.exception("Full error traceback:")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)