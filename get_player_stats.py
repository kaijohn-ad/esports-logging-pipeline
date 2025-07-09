#!/usr/bin/env python3
"""
プレイヤー戦績データ取得スクリプト

kaihuu#JP1の戦績データ（マッチ履歴、キルイベント等）を取得・表示
"""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime

# プロジェクトのルートディレクトリをパスに追加
sys.path.append('src')

from collectors.lol_fetcher import LoLFetcher, PlayerNotFoundError
from canonizer.lol_canonizer import LoLCanonizer

def get_player_match_stats(riot_id: str):
    """プレイヤーの戦績データを取得・表示"""
    load_dotenv()
    api_key = os.getenv('RIOT_API_KEY')
    
    if not api_key:
        print('❌ RIOT_API_KEYが設定されていません')
        return
    
    try:
        # LoLFetcherを初期化
        fetcher = LoLFetcher(api_key, region='jp1')
        
        print(f'🎯 プレイヤー戦績取得開始: {riot_id}')
        print('=' * 50)
        
        # Riot ID形式で検索
        game_name, tag_line = riot_id.split('#', 1)
        
        # 1. プレイヤー情報取得
        print('📋 Step 1: プレイヤー情報取得...')
        account_data = fetcher.search_by_riot_id(game_name, tag_line)
        puuid = account_data["puuid"]
        
        summoner_data = fetcher.fetch_summoner_by_puuid(puuid)
        
        print(f'✅ プレイヤー情報:')
        print(f'   📝 名前: {account_data["gameName"]}#{account_data["tagLine"]}')
        print(f'   📊 レベル: {summoner_data["summonerLevel"]}')
        print(f'   🆔 PUUID: {puuid[:12]}...')
        
        # 2. 最新マッチ履歴取得
        print(f'\n📋 Step 2: 最新マッチ履歴取得...')
        match_ids = fetcher.fetch_latest_matches(puuid, count=3)
        
        if not match_ids:
            print('❌ マッチ履歴が見つかりません')
            return
            
        print(f'✅ {len(match_ids)}件のマッチが見つかりました')
        
        # 3. 各マッチの詳細とキルイベント取得
        total_kills = 0
        total_deaths = 0
        total_assists = 0
        
        for i, match_id in enumerate(match_ids, 1):
            print(f'\n📋 Step 3.{i}: マッチ {i}/{len(match_ids)} 分析中...')
            print(f'🆔 Match ID: {match_id}')
            
            try:
                # マッチ詳細取得
                match_data = fetcher.fetch_match_details(match_id)
                
                # プレイヤーのパフォーマンス取得
                player_performance = fetcher.extract_player_performance(match_data, puuid)
                
                if player_performance:
                    print(f'✅ マッチ{i}結果:')
                    print(f'   🏆 チャンピオン: {player_performance["championName"]}')
                    print(f'   ⚔️ KDA: {player_performance["kills"]}/{player_performance["deaths"]}/{player_performance["assists"]} (比率: {player_performance["kda"]})')
                    print(f'   🌾 CS: {player_performance["cs"]}')
                    print(f'   💰 獲得ゴールド: {player_performance["goldEarned"]:,}')
                    print(f'   ⚡ ダメージ: {player_performance["totalDamageDealt"]:,}')
                    
                    # 統計に追加
                    total_kills += player_performance["kills"]
                    total_deaths += player_performance["deaths"]
                    total_assists += player_performance["assists"]
                
                # タイムライン取得してキルイベント抽出
                print(f'🔍 キルイベント分析中...')
                timeline_data = fetcher.fetch_timeline(match_id)
                events = LoLCanonizer.timeline_to_events(timeline_data)
                
                kill_events = [e for e in events if e.event == "CHAMPION_KILL"]
                print(f'   📊 このマッチのキルイベント: {len(kill_events)}件')
                
                # 最初の数件のキルイベントを表示
                for j, event in enumerate(kill_events[:3]):
                    print(f'   ⚔️ Kill {j+1}: {event.timestamp:.1f}s - {event.actor} → {event.target}')
                
                if len(kill_events) > 3:
                    print(f'   ... その他 {len(kill_events) - 3}件のキルイベント')
                    
            except Exception as e:
                print(f'❌ マッチ{i}の処理中にエラー: {e}')
                continue
        
        # 4. 総合統計表示
        print(f'\n' + '=' * 50)
        print(f'📊 総合戦績サマリー（直近{len(match_ids)}ゲーム）')
        print(f'=' * 50)
        print(f'⚔️ 合計 KDA: {total_kills}/{total_deaths}/{total_assists}')
        
        if total_deaths > 0:
            avg_kda = (total_kills + total_assists) / total_deaths
            print(f'📈 平均KDA比: {avg_kda:.2f}')
        else:
            print(f'📈 平均KDA比: Perfect (死亡なし)')
            
        print(f'🎯 平均キル数: {total_kills / len(match_ids):.1f}')
        print(f'💀 平均デス数: {total_deaths / len(match_ids):.1f}')
        print(f'🤝 平均アシスト数: {total_assists / len(match_ids):.1f}')
        
        print(f'\n🎉 戦績データ取得完了！')
        
    except PlayerNotFoundError as e:
        print(f'❌ プレイヤーが見つかりません: {e}')
    except Exception as e:
        print(f'❌ エラーが発生しました: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # kaihuuプレイヤーの戦績を取得
    get_player_match_stats("kaihuu#JP1") 