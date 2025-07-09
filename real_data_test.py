#!/usr/bin/env python3
"""
実際の試合データ取得テストスクリプト

このスクリプトは以下をテストします：
1. Riot Games API（LoL）での実際のプレイヤーデータ取得
2. Henrik API（VALORANT）での実際のプレイヤーデータ取得
3. APIキー設定と接続確認

実行前の準備：
1. .env ファイルを作成してAPIキーを設定
2. プレイヤー名を設定

使用方法:
python real_data_test.py --player-name "YourSummonerName" --valorant-name "YourValorantName#TAG"
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional
import argparse

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent / "src"))

from collectors.lol_fetcher import LoLFetcher
from collectors.valorant_fetcher import ValorantFetcher
from canonizer.lol_canonizer import LoLCanonizer
from canonizer.valorant_canonizer import ValorantCanonizer
from storage.sqlite_store import SQLiteStore

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_env_file():
    """環境変数ファイルの存在確認と作成ガイド"""
    env_path = Path('.env')
    
    if not env_path.exists():
        logger.warning(".env ファイルが見つかりません")
        print("\n🔧 設定が必要です！")
        print("=" * 50)
        print("1. .env ファイルを作成してください：")
        print("""
# .env ファイルの内容例
# Riot Games API Key (LoL用)
RIOT_API_KEY=RGAPI-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# リージョン設定
RIOT_REGION=jp1

# OpenRouter API Key (LLM分析用、オプション)
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        """)
        print("\n2. APIキーの取得方法：")
        print("🎮 Riot Games API Key:")
        print("   - https://developer.riotgames.com/ にアクセス")
        print("   - Riot アカウントでサインイン")
        print("   - 'REGENERATE API KEY' をクリック")
        print("   - 24時間有効の開発用キーを取得")
        print("")
        print("🎯 VALORANT API:")
        print("   - Henrik APIは無料で使用可能（APIキー不要）")
        print("   - プレイヤー名とタグ（例: PlayerName#TAG）が必要")
        print("")
        return False
    
    return True


def load_api_keys():
    """APIキーを環境変数から読み込み"""
    from dotenv import load_dotenv
    load_dotenv()
    
    riot_api_key = os.getenv('RIOT_API_KEY')
    riot_region = os.getenv('RIOT_REGION', 'jp1')
    
    if not riot_api_key:
        logger.error("RIOT_API_KEY が設定されていません")
        return None, None
    
    logger.info(f"API設定読み込み完了 - Region: {riot_region}")
    return riot_api_key, riot_region


async def test_lol_data_fetch(summoner_name: str, api_key: str, region: str):
    """LoL実際データ取得テスト"""
    print(f"\n🎮 LoL データ取得テスト")
    print(f"サマナー名: {summoner_name}")
    print(f"リージョン: {region}")
    print("-" * 40)
    
    try:
        # LoLFetcher初期化
        fetcher = LoLFetcher(api_key, region)
        
        # 1. サマナー情報取得
        print("1. サマナー情報を取得中...")
        summoner = fetcher.watch.summoner.by_name(region, summoner_name)
        puuid = summoner["puuid"]
        print(f"   ✅ PUUID: {puuid[:8]}...")
        print(f"   ✅ レベル: {summoner['summonerLevel']}")
        
        # 2. 最新マッチ取得
        print("2. 最新マッチを取得中...")
        match_ids = fetcher.fetch_latest_matches(puuid, count=3)
        print(f"   ✅ 取得マッチ数: {len(match_ids)}")
        
        if match_ids:
            # 3. マッチ詳細とタイムライン取得
            print("3. マッチ詳細を取得中...")
            latest_match = match_ids[0]
            
            match_details = fetcher.fetch_match_details(latest_match)
            timeline_data = fetcher.fetch_timeline(latest_match)
            
            print(f"   ✅ マッチID: {latest_match}")
            print(f"   ✅ ゲーム時間: {match_details['info']['gameDuration']}秒")
            print(f"   ✅ ゲームモード: {match_details['info']['gameMode']}")
            
            # 4. killイベント抽出
            print("4. killイベントを抽出中...")
            canonizer = LoLCanonizer()
            events = canonizer.timeline_to_events(timeline_data)
            kill_events = [e for e in events if e.event == "kill"]
            
            print(f"   ✅ 総イベント数: {len(events)}")
            print(f"   ✅ killイベント数: {len(kill_events)}")
            
            if kill_events:
                print("   🎯 killイベント例:")
                for i, kill in enumerate(kill_events[:3]):
                    print(f"      Kill #{i+1}: {kill.timestamp:.1f}s - Player {kill.actor} → Player {kill.target}")
            
            # 5. データベース保存テスト
            print("5. データベース保存テスト...")
            db_path = Path("data/real_test_lol.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            store = SQLiteStore(db_path)
            store.init()
            
            # マッチ保存
            match_data = {
                "id": latest_match,
                "title": f"Real LoL Match - {summoner_name}",
                "patch": match_details["info"]["gameVersion"],
                "timestamp": str(match_details["info"]["gameCreation"])
            }
            store.store_match(match_data)
            
            # イベント保存
            for event in kill_events:
                store.store_event(latest_match, event)
            
            print(f"   ✅ データベース保存完了: {db_path}")
            print(f"   ✅ 保存されたkillイベント: {len(kill_events)}件")
            
            return True, f"LoL: {len(kill_events)} kill events from {summoner_name}"
            
    except Exception as e:
        logger.error(f"LoL データ取得エラー: {e}")
        print(f"   ❌ エラー: {e}")
        return False, str(e)


async def test_valorant_data_fetch(player_name: str, tag: str):
    """VALORANT実際データ取得テスト"""
    print(f"\n🎯 VALORANT データ取得テスト")
    print(f"プレイヤー: {player_name}#{tag}")
    print("-" * 40)
    
    try:
        async with ValorantFetcher() as fetcher:
            # 1. プレイヤー情報取得
            print("1. プレイヤー情報を取得中...")
            player_info = await fetcher.fetch_player_info(player_name, tag)
            
            if not player_info or 'data' not in player_info:
                print("   ❌ プレイヤーが見つかりません")
                return False, "VALORANT player not found"
            
            print(f"   ✅ プレイヤー確認: {player_info['data']['name']}#{player_info['data']['tag']}")
            
            # 2. マッチ履歴取得
            print("2. マッチ履歴を取得中...")
            match_history = await fetcher.fetch_match_history(player_name, tag, size=1)
            
            if not match_history or 'data' not in match_history:
                print("   ❌ マッチ履歴が見つかりません")
                return False, "No VALORANT match history found"
            
            matches = match_history['data']
            print(f"   ✅ 取得マッチ数: {len(matches)}")
            
            if matches:
                latest_match = matches[0]
                
                # 3. マッチ詳細取得
                print("3. マッチ詳細を取得中...")
                match_id = latest_match.get('metadata', {}).get('matchid')
                
                if match_id:
                    match_details = await fetcher.fetch_match_details(match_id)
                    
                    print(f"   ✅ マッチID: {match_id}")
                    print(f"   ✅ マップ: {match_details.get('data', {}).get('metadata', {}).get('map', 'Unknown')}")
                    print(f"   ✅ ゲームモード: {match_details.get('data', {}).get('metadata', {}).get('mode', 'Unknown')}")
                    
                    # 4. killイベント抽出
                    print("4. killイベントを抽出中...")
                    canonizer = ValorantCanonizer()
                    events = canonizer.match_to_events(match_details)
                    round_kills_events = [e for e in events if e.event == "round_kills"]
                    
                    # round_killsをkillイベントに変換
                    kill_events = canonizer.convert_round_kills_to_kill_events(events)
                    
                    print(f"   ✅ 総イベント数: {len(events)}")
                    print(f"   ✅ round_killsイベント数: {len(round_kills_events)}")
                    print(f"   ✅ 変換後killイベント数: {len(kill_events)}")
                    
                    # 5. データベース保存テスト
                    print("5. データベース保存テスト...")
                    db_path = Path("data/real_test_valorant.db")
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    store = SQLiteStore(db_path)
                    store.init()
                    
                    # マッチ保存
                    match_data = {
                        "id": match_id,
                        "title": f"Real VALORANT Match - {player_name}#{tag}",
                        "patch": match_details.get('data', {}).get('metadata', {}).get('game_version', 'Unknown'),
                        "timestamp": str(match_details.get('data', {}).get('metadata', {}).get('game_start', 0))
                    }
                    store.store_match(match_data)
                    
                    # イベント保存
                    all_events = events + kill_events
                    for event in all_events:
                        store.store_event(match_id, event)
                    
                    print(f"   ✅ データベース保存完了: {db_path}")
                    print(f"   ✅ 保存されたkillイベント: {len(kill_events)}件")
                    
                    return True, f"VALORANT: {len(kill_events)} kill events from {player_name}#{tag}"
                
    except Exception as e:
        logger.error(f"VALORANT データ取得エラー: {e}")
        print(f"   ❌ エラー: {e}")
        return False, str(e)


async def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='実際の試合データ取得テスト')
    parser.add_argument('--lol-player', type=str, help='LoLサマナー名')
    parser.add_argument('--valorant-player', type=str, help='VALORANTプレイヤー名（例: PlayerName#TAG）')
    parser.add_argument('--skip-env-check', action='store_true', help='環境変数チェックをスキップ')
    
    args = parser.parse_args()
    
    print("🚀 実際の試合データ取得テスト")
    print("=" * 50)
    
    # 1. 環境設定確認
    if not args.skip_env_check and not check_env_file():
        return 1
    
    results = []
    
    # 2. LoLデータ取得テスト
    if args.lol_player:
        try:
            # python-dotenvをインストールする必要があります
            api_key, region = load_api_keys()
            if api_key:
                success, message = await test_lol_data_fetch(args.lol_player, api_key, region)
                results.append(("LoL", success, message))
            else:
                results.append(("LoL", False, "API key not configured"))
        except ImportError:
            print("⚠️ python-dotenv が必要です: pip install python-dotenv")
            results.append(("LoL", False, "python-dotenv not installed"))
    
    # 3. VALORANTデータ取得テスト
    if args.valorant_player:
        if '#' in args.valorant_player:
            player_name, tag = args.valorant_player.split('#', 1)
            success, message = await test_valorant_data_fetch(player_name, tag)
            results.append(("VALORANT", success, message))
        else:
            print("⚠️ VALORANTプレイヤー名は 'PlayerName#TAG' 形式で指定してください")
            results.append(("VALORANT", False, "Invalid format"))
    
    # 4. 結果サマリー
    print("\n📊 テスト結果サマリー")
    print("=" * 50)
    
    for game, success, message in results:
        status = "✅ 成功" if success else "❌ 失敗"
        print(f"{game}: {status}")
        print(f"   詳細: {message}")
    
    # 5. 次のステップ案内
    if any(success for _, success, _ in results):
        print("\n🎉 実際のデータ取得に成功しました！")
        print("\n🚀 次のステップ:")
        print("1. データベースに保存されたkillイベントを確認")
        print("2. KPI計算機能でパフォーマンス分析")
        print("3. LLM（OpenRouter）を使用したフィードバック生成")
        print("4. 定期的なデータ収集の自動化")
    else:
        print("\n🔧 設定が必要です。上記のエラーメッセージを確認して再試行してください。")
    
    return 0 if any(success for _, success, _ in results) else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️ テストが中断されました")
        sys.exit(1) 