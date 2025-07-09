#!/usr/bin/env python3
"""
VALORANT Kill Event Processing Demo Script

Task 2: Verify VALORANT Kill Event Processing and SQLite Storage
このスクリプトは以下の処理を実行します：
1. ValorantFetcher を使用してサンプルVALORANTマッチデータを取得
2. ValorantCanonizer でround_killsイベントをkillイベントに変換
3. SQLiteStore でデータベースに保存
4. 結果を検証

実行方法: python valorant_kill_event_demo.py
"""

import asyncio
import json
import logging
from pathlib import Path
import sys

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / "src"))

from collectors.valorant_fetcher import ValorantFetcher
from canonizer.valorant_canonizer import ValorantCanonizer
from storage.sqlite_store import SQLiteStore

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_valorant_kill_event_processing():
    """VALORANTキルイベント処理のデモを実行"""
    
    logger.info("🎮 VALORANT Kill Event Processing Demo 開始")
    
    # サンプルVALORANTマッチデータ（実際のAPIレスポンス形式）
    sample_match_data = {
        "status": 200,
        "data": {
            "metadata": {
                "matchid": "demo_match_789",
                "map": "Ascent",
                "game_version": "release-09.01",
                "game_length": 2400000,  # 40分
                "game_start": 1640995200,
                "rounds_played": 20,
                "mode": "Competitive",
                "queue": "competitive",
                "region": "ap",
                "cluster": "ap"
            },
            "players": {
                "all_players": [
                    {
                        "puuid": "demo_puuid_1",
                        "name": "DemoPlayer",
                        "tag": "DEMO",
                        "team": "Red",
                        "character": "Sage",
                        "stats": {
                            "kills": 25,
                            "deaths": 15,
                            "assists": 12,
                            "score": 5200,
                            "headshots": 15,
                            "bodyshots": 18,
                            "legshots": 7,
                            "damage": {
                                "made": 4200,
                                "received": 3500
                            },
                            "first_bloods": 6,
                            "first_deaths": 3
                        }
                    },
                    {
                        "puuid": "demo_puuid_2",
                        "name": "EnemyPlayer",
                        "tag": "OPPO",
                        "team": "Blue",
                        "character": "Reyna",
                        "stats": {
                            "kills": 22,
                            "deaths": 18,
                            "assists": 8,
                            "score": 4800,
                            "headshots": 12,
                            "bodyshots": 15,
                            "legshots": 5,
                            "damage": {
                                "made": 3800,
                                "received": 3900
                            },
                            "first_bloods": 4,
                            "first_deaths": 5
                        }
                    }
                ]
            },
            "teams": {
                "red": {"has_won": True, "rounds_won": 13, "rounds_lost": 7},
                "blue": {"has_won": False, "rounds_won": 7, "rounds_lost": 13}
            },
            "rounds": [
                {
                    "round_num": 1,
                    "round_result": "Team Won",
                    "winning_team": "Red",
                    "plant_events": [],
                    "defuse_events": [],
                    "player_stats": [
                        {
                            "player_puuid": "demo_puuid_1",
                            "kills": 4,
                            "damage": 600,
                            "score": 450
                        },
                        {
                            "player_puuid": "demo_puuid_2",
                            "kills": 2,
                            "damage": 400,
                            "score": 250
                        }
                    ]
                },
                {
                    "round_num": 2,
                    "round_result": "Eliminated",
                    "winning_team": "Blue",
                    "plant_events": [],
                    "defuse_events": [],
                    "player_stats": [
                        {
                            "player_puuid": "demo_puuid_1",
                            "kills": 1,
                            "damage": 300,
                            "score": 200
                        },
                        {
                            "player_puuid": "demo_puuid_2",
                            "kills": 5,
                            "damage": 750,
                            "score": 600
                        }
                    ]
                }
            ]
        }
    }
    
    try:
        # 1. ValorantCanonizer でデータを正規化
        logger.info("📊 ValorantCanonizer でマッチデータを正規化中...")
        events = ValorantCanonizer.match_to_events(sample_match_data)
        logger.info(f"✅ {len(events)} 個のイベントを生成")
        
        # round_killsイベントの確認
        round_kills_events = [e for e in events if e.event == "round_kills"]
        logger.info(f"🎯 {len(round_kills_events)} 個のround_killsイベントを発見")
        
        # 2. round_killsイベントをkillイベントに変換
        logger.info("⚔️ round_killsイベントをkillイベントに変換中...")
        kill_events = ValorantCanonizer.convert_round_kills_to_kill_events(events)
        logger.info(f"✅ {len(kill_events)} 個のkillイベントを生成")
        
        # 生成されたkillイベントの詳細を表示
        for i, kill_event in enumerate(kill_events[:5]):  # 最初の5個を表示
            logger.info(f"  キル #{i+1}: {kill_event.actor} (ラウンド {kill_event.meta['round_num']}, キル番号 {kill_event.meta['kill_number']})")
        
        # 3. SQLiteStore でデータベースに保存
        logger.info("💾 SQLiteデータベースにデータを保存中...")
        db_path = Path("data/demo_valorant.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        store = SQLiteStore(db_path)
        store.init()
        
        # マッチメタデータを保存
        match_metadata = {
            "id": sample_match_data["data"]["metadata"]["matchid"],
            "title": f"VALORANT Demo Match on {sample_match_data['data']['metadata']['map']}",
            "patch": sample_match_data["data"]["metadata"]["game_version"],
            "timestamp": str(sample_match_data["data"]["metadata"]["game_start"])
        }
        store.store_match(match_metadata)
        logger.info(f"✅ マッチ '{match_metadata['id']}' を保存")
        
        # 全イベント（正規化イベント + killイベント）を保存
        all_events = events + kill_events
        for event in all_events:
            store.store_event(match_metadata["id"], event)
        logger.info(f"✅ {len(all_events)} 個のイベントを保存")
        
        # 4. データベースの内容を検証
        logger.info("🔍 データベースの内容を検証中...")
        
        # 保存されたマッチを確認
        stored_match = store.get_match(match_metadata["id"])
        assert stored_match is not None, "マッチが保存されていません"
        logger.info(f"✅ マッチ確認: {stored_match['title']}")
        
        # 保存されたイベントを確認
        stored_events = store.get_events_for_match(match_metadata["id"])
        logger.info(f"✅ 保存されたイベント数: {len(stored_events)}")
        
        # killイベントの確認
        stored_kill_events = [e for e in stored_events if e.event == "kill"]
        logger.info(f"✅ 保存されたkillイベント数: {len(stored_kill_events)}")
        
        # killイベントの詳細を表示
        for i, kill_event in enumerate(stored_kill_events[:3]):  # 最初の3個を表示
            logger.info(f"  保存済みキル #{i+1}: {kill_event.actor} - ラウンド {kill_event.meta['round_num']}")
        
        # 5. 結果サマリー
        logger.info("\n" + "="*60)
        logger.info("📋 VALORANT Kill Event Processing Demo 結果サマリー")
        logger.info("="*60)
        logger.info(f"📊 処理マッチ: {stored_match['title']}")
        logger.info(f"🎯 総イベント数: {len(stored_events)}")
        logger.info(f"⚔️ killイベント数: {len(stored_kill_events)}")
        logger.info(f"🗃️ データベースパス: {db_path}")
        logger.info("="*60)
        logger.info("✅ Task 2: VALORANTキルイベント処理とSQLite保存 - 成功!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}")
        raise


def main():
    """メイン実行関数"""
    try:
        # 非同期処理を実行
        result = asyncio.run(demo_valorant_kill_event_processing())
        if result:
            print("\n🎉 Demo完了! VALORANTキルイベント処理パイプラインが正常に動作しました。")
            return 0
    except Exception as e:
        print(f"\n💥 Demo失敗: {e}")
        return 1


if __name__ == "__main__":
    exit(main())