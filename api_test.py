#!/usr/bin/env python3
"""
Riot Games API プレイヤー検索機能テスト & 実装サンプル

このファイルは、プロジェクト内でプレイヤー検索を実装する際の参照実装として機能します。

=== プレイヤー検索の実装パターン ===

2023年11月以降、Riot Games APIでのプレイヤー検索方法が大きく変更されました：

【推奨】新しいRiot ID検索:
- 形式: "GameName#Tagline" (例: "Day1week#Day1")
- エンドポイント: https://{riot_region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
- リージョン: asia, americas, europe (platform非依存)
- 成功率: 高い
- 実装: search_riot_id() 関数

【非推奨】Legacy Summoner Name検索:
- 形式: "SummonerName" (例: "Day1week")
- エンドポイント: https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{name}
- リージョン: jp1, kr, na1 etc (platform依存)
- 成功率: 低い（403エラー多発）
- 実装: search_summoner_legacy() 関数

=== 他のモジュールでの使用方法 ===

1. メインプロジェクトコード（src/collectors/lol_fetcher.py）:
   ```python
   from src.collectors.lol_fetcher import LoLFetcher, PlayerNotFoundError
   
   # 推奨方法: Riot ID検索
   fetcher = LoLFetcher(api_key)
   account_data = fetcher.search_by_riot_id("Day1week", "Day1")
   puuid = account_data["puuid"]
   summoner_data = fetcher.fetch_summoner_by_puuid(puuid)
   
   # 包括的検索（自動フォールバック付き）
   account, summoner = fetcher.search_player_comprehensive("Day1week#Day1")
   ```

2. このテストファイルのコード:
   ```python
   # 直接API呼び出し（デバッグ用）
   account_data = search_riot_id("Day1week", "Day1")
   legacy_data = search_summoner_legacy("Day1week")  # 非推奨
   ```

=== テスト実行方法 ===

基本テスト:
    python api_test.py

特定プレイヤーのテスト:
    python -c "from api_test import search_riot_id; print(search_riot_id('Day1week', 'Day1'))"

=== 参照 ===
- LoLFetcher実装: src/collectors/lol_fetcher.py
- 設定管理: src/config/lol_config.py
- Riot Developer Portal: https://developer.riotgames.com/docs/summoner-name-to-riot-id-faq
"""

from dotenv import load_dotenv
import os
import requests
import urllib.parse

def test_api_key():
    """Riot Games APIキーの有効性を検証
    
    プラットフォーム固有のエンドポイント（lol/status/v4）を使用してAPIキーをテスト。
    このテストが成功すれば、基本的なAPI接続は正常に動作している。
    
    Returns:
        bool: APIキーが有効で接続可能な場合True
        
    Note:
        - jp1リージョンのLoLサーバーステータスAPIを使用
        - 認証が必要なエンドポイントなので、APIキーの有効性を確認可能
    """
    load_dotenv()
    api_key = os.getenv('RIOT_API_KEY')
    region = os.getenv('RIOT_REGION', 'jp1').strip()
    
    print(f'🔑 API Key (末尾5文字): ...{api_key[-5:] if api_key else "NOT_SET"}')
    print(f'🔍 API Key 長さ: {len(api_key) if api_key else 0}')
    print(f'🔍 API Key repr: {repr(api_key) if api_key else "None"}')
    print(f'🌏 Region: {region}')
    print(f'🔍 Region repr: {repr(region)}')
    
    if not api_key:
        print('❌ RIOT_API_KEYが設定されていません')
        return False
    
    # APIキーの基本形式チェック
    if not api_key.startswith('RGAPI-'):
        print('❌ APIキーの形式が正しくありません（RGAPI-で始まる必要があります）')
        return False
    
    # 標準的な長さチェック（RGAPI- + UUID形式なら42文字）
    expected_length = 42  # RGAPI- (6) + UUID (36)
    if len(api_key) != expected_length:
        print(f'⚠️ APIキーの長さが予想と異なります（期待値: {expected_length}, 実際: {len(api_key)}）')
    
    # サーバーステータスAPIで接続テスト（認証が必要）
    url = f'https://{region}.api.riotgames.com/lol/status/v4/platform-data'
    headers = {
        'X-Riot-Token': api_key.strip(),  # strip()を追加
        'User-Agent': 'eSportsLoggingPipeline/1.0'
    }
    
    try:
        print(f'🔍 APIテスト中: {url}')
        print(f'🔍 ヘッダー: X-Riot-Token={api_key[:10]}...')
        
        response = requests.get(url, headers=headers, timeout=10)
        print(f'📊 レスポンス: {response.status_code}')
        
        if response.status_code == 200:
            print('✅ APIキーが有効です！')
            data = response.json()
            print(f'📡 サーバー名: {data.get("name", "Unknown")}')
            return True
        elif response.status_code == 401:
            print('❌ APIキーが無効または期限切れです')
            print('💡 https://developer.riotgames.com/ で新しいキーを取得してください')
            print('💡 新しいキーがアクティブになるまで数分かかる場合があります')
        elif response.status_code == 403:
            print('❌ APIキーにアクセス権限がありません')
        elif response.status_code == 429:
            print('⚠️ レート制限に達しました。しばらく待ってから再試行してください')
        else:
            print(f'❌ APIエラー: {response.status_code}')
            print(f'Response: {response.text[:200]}')
        
        return False
        
    except Exception as e:
        print(f'❌ 接続エラー: {e}')
        return False

def search_summoner_legacy(summoner_name):
    """【非推奨】レガシーSummoner APIでプレイヤー検索
    
    2023年11月以降は403エラーが多発するため非推奨。
    互換性とフォールバック目的でのみ使用。
    
    Args:
        summoner_name (str): Summoner Name（例: "Day1week"）
        
    Returns:
        bool: 検索成功時True、失敗時False
        
    Note:
        - エンドポイント: summoner/v4/summoners/by-name/{name}
        - プラットフォーム固有リージョン（jp1）を使用
        - 403エラーが頻発する場合、search_riot_id()を使用推奨
        - このコードは src/collectors/lol_fetcher.py の fetch_summoner_by_name() と同等
        
    Example:
        >>> success = search_summoner_legacy("Day1week")
        >>> if not success:
        >>>     # Riot ID検索にフォールバック
        >>>     search_riot_id("Day1week", "Day1")
    """
    load_dotenv()
    api_key = os.getenv('RIOT_API_KEY')
    region = os.getenv('RIOT_REGION', 'jp1').strip()
    
    if not api_key:
        print('❌ RIOT_API_KEYが設定されていません')
        return False
    
    # プレイヤー名をURLエンコード（特殊文字対応）
    encoded_name = urllib.parse.quote(summoner_name, safe='')
    print(f'🔍 検索するプレイヤー名: {summoner_name}')
    print(f'🔍 URLエンコード後: {encoded_name}')
    
    # Summoner APIでプレイヤー検索（レガシー）
    url = f'https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{encoded_name}'
    headers = {
        'X-Riot-Token': api_key.strip(),
        'User-Agent': 'eSportsLoggingPipeline/1.0'
    }
    
    try:
        print(f'🔍 Legacy API URL: {url}')
        response = requests.get(url, headers=headers, timeout=10)
        print(f'📊 レスポンス: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print('✅ プレイヤーが見つかりました！（Legacy API）')
            print(f'📝 名前: {data.get("name")}')
            print(f'📊 レベル: {data.get("summonerLevel")}')
            print(f'🆔 PUUID: {data.get("puuid", "")[:8]}...')
            print(f'🆔 Summoner ID: {data.get("id", "")[:8]}...')
            return True
        elif response.status_code == 404:
            print('❌ プレイヤーが見つかりません（Legacy API）')
        elif response.status_code == 401:
            print('❌ APIキーが無効または期限切れです')
        elif response.status_code == 403:
            print('❌ APIキーにアクセス権限がありません')
            print('💡 2023年11月以降、Legacy APIのアクセスが制限されています')
            print('💡 新しいRiot ID検索（search_riot_id）を使用してください')
        elif response.status_code == 429:
            print('⚠️ レート制限に達しました。しばらく待ってから再試行してください')
        else:
            print(f'❌ APIエラー: {response.status_code}')
            print(f'Response: {response.text[:200]}')
        
        return False
        
    except Exception as e:
        print(f'❌ 接続エラー: {e}')
        return False

def search_riot_id(game_name, tag_line):
    """【推奨】新しいRiot ID形式でプレイヤー検索
    
    2023年11月以降の推奨プレイヤー検索方法。
    Legacy APIよりも成功率が高く、国際的に統一された形式。
    
    Args:
        game_name (str): Riot IDのゲーム名部分（例: "Day1week"）
        tag_line (str): Riot IDのタグライン部分（例: "Day1"）
        
    Returns:
        bool: 検索成功時True、失敗時False
        
    Technical Details:
        - エンドポイント: riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
        - リージョンマッピング: jp1 -> asia （プラットフォーム固有でない）
        - URLエンコード: 自動適用（特殊文字対応）
        - User-Agent: プロジェクト識別のため設定
        
    Integration:
        このコードは src/collectors/lol_fetcher.py の search_by_riot_id() メソッドとほぼ同等。
        プロダクションコードでは LoLFetcher クラスを使用推奨。
        
    Example:
        >>> # Riot ID "Day1week#Day1" を検索
        >>> success = search_riot_id("Day1week", "Day1")
        >>> if success:
        >>>     print("検索成功")
        
    Note:
        - GameName: 3-16文字、#文字は使用禁止
        - Tagline: 3-5文字のアルファベット・数字のみ
        - 区切り文字: #はGameNameとTaglineの区切り文字
        - リージョン自動マッピング: jp1 -> asia region
    """
    load_dotenv()
    api_key = os.getenv('RIOT_API_KEY')
    
    # Riot IDの検索はリージョンマッピングが必要
    # プラットフォーム固有（jp1）から Riot リージョン（asia）への変換
    region_mapping = {
        'jp1': 'asia',      # 日本/韓国
        'kr': 'asia', 
        'na1': 'americas',  # 北米
        'euw1': 'europe',   # ヨーロッパ西
        'eun1': 'europe'    # ヨーロッパ北東
    }
    
    local_region = os.getenv('RIOT_REGION', 'jp1').strip()
    riot_region = region_mapping.get(local_region, 'asia')
    
    if not api_key:
        print('❌ RIOT_API_KEYが設定されていません')
        return False
    
    # Game NameとTaglineをURLエンコード（特殊文字・日本語対応）
    encoded_game_name = urllib.parse.quote(game_name, safe='')
    encoded_tag_line = urllib.parse.quote(tag_line, safe='')
    
    print(f'🔍 Game Name: {game_name}')
    print(f'🔍 Tagline: {tag_line}')
    print(f'🔍 URLエンコード後: {encoded_game_name}#{encoded_tag_line}')
    print(f'🔍 リージョンマッピング: {local_region} -> {riot_region}')
    
    # Account APIでRiot ID検索
    # 注意: summoner APIではなく、account APIを使用
    url = f'https://{riot_region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_game_name}/{encoded_tag_line}'
    headers = {
        'X-Riot-Token': api_key.strip(),
        'User-Agent': 'eSportsLoggingPipeline/1.0'  # プロジェクト識別
    }
    
    try:
        print(f'🔍 Riot ID API URL: {url}')
        response = requests.get(url, headers=headers, timeout=10)
        print(f'📊 レスポンス: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print('✅ プレイヤーが見つかりました！（Riot ID API）')
            print(f'📝 Game Name: {data.get("gameName")}')
            print(f'🏷️ Tagline: {data.get("tagLine")}')
            print(f'🆔 PUUID: {data.get("puuid", "")[:8]}...')
            
            # PUUIDを使ってローカルのSummoner情報も取得
            # これによりレベルやSummoner IDなどの詳細情報を取得可能
            puuid = data.get("puuid")
            if puuid:
                print('\n🔍 PUUIDを使ってSummoner情報を取得...')
                get_summoner_by_puuid(puuid)
            
            return True
        elif response.status_code == 404:
            print('❌ Riot IDが見つかりません')
            print('💡 プレイヤー名とタグラインのスペルをご確認ください')
            print('💡 大文字小文字は区別されません')
        elif response.status_code == 401:
            print('❌ APIキーが無効または期限切れです')
        elif response.status_code == 403:
            print('❌ APIキーにアクセス権限がありません')
        elif response.status_code == 429:
            print('⚠️ レート制限に達しました。しばらく待ってから再試行してください')
        else:
            print(f'❌ APIエラー: {response.status_code}')
            print(f'Response: {response.text[:200]}')
        
        return False
        
    except Exception as e:
        print(f'❌ 接続エラー: {e}')
        return False

def get_summoner_by_puuid(puuid):
    """PUUIDを使ってプラットフォーム固有のSummoner情報を取得
    
    Riot ID検索で取得したPUUIDを使用して、プラットフォーム固有の
    Summoner情報（レベル、Summoner IDなど）を取得。
    
    Args:
        puuid (str): Riot ID検索で取得した一意識別子
        
    Note:
        - エンドポイント: summoner/v4/summoners/by-puuid/{puuid}
        - プラットフォーム固有リージョン（jp1）を使用
        - Riot ID検索との組み合わせで最大限の情報を取得可能
        - このパターンは src/collectors/lol_fetcher.py でも使用
        
    Workflow:
        1. search_riot_id() でアカウント情報とPUUIDを取得
        2. get_summoner_by_puuid() でSummoner詳細情報を取得
        3. 両方の情報を組み合わせて完全なプレイヤープロファイル作成
    """
    load_dotenv()
    api_key = os.getenv('RIOT_API_KEY')
    region = os.getenv('RIOT_REGION', 'jp1').strip()
    
    # PUUIDベースのSummoner情報取得（プラットフォーム固有）
    url = f'https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}'
    headers = {
        'X-Riot-Token': api_key.strip(),
        'User-Agent': 'eSportsLoggingPipeline/1.0'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print('✅ Summoner情報取得成功！')
            print(f'📊 レベル: {data.get("summonerLevel")}')
            print(f'🆔 Summoner ID: {data.get("id", "")[:8]}...')
            print(f'📅 最終更新: {data.get("revisionDate", "Unknown")}')
            return data
        else:
            print(f'❌ Summoner情報取得失敗: {response.status_code}')
            print(f'Response: {response.text[:100]}')
            return None
    except Exception as e:
        print(f'❌ Summoner情報取得エラー: {e}')
        return None

def search_player_comprehensive(player_identifier):
    """包括的プレイヤー検索（推奨統合メソッド）
    
    プレイヤー識別子の形式を自動判定し、最適な検索方法を選択。
    Riot ID検索を優先し、失敗時にLegacy検索にフォールバック。
    
    Args:
        player_identifier (str): プレイヤー識別子
            - Riot ID形式: "GameName#Tagline" (例: "Day1week#Day1")
            - Legacy形式: "SummonerName" (例: "Day1week")
            
    Returns:
        bool: 検索成功時True
        
    Usage Pattern:
        >>> # 新しいRiot ID形式
        >>> search_player_comprehensive("Day1week#Day1")
        >>> 
        >>> # Legacy形式（自動フォールバック）
        >>> search_player_comprehensive("Day1week")
        
    Note:
        このメソッドは src/collectors/lol_fetcher.py の 
        search_player_comprehensive() メソッドと同等のロジック。
        プロダクションコードでは LoLFetcher クラスを使用推奨。
    """
    print(f'🎯 包括的プレイヤー検索: {player_identifier}')
    
    # Riot ID形式の判定（#文字の存在）
    if '#' in player_identifier:
        print('📋 Riot ID形式を検出')
        game_name, tag_line = player_identifier.split('#', 1)
        
        # Riot ID検索を試行
        if search_riot_id(game_name, tag_line):
            return True
        else:
            print('\n⚠️ Riot ID検索失敗、Legacy検索にフォールバック...')
            # Game Name部分のみでLegacy検索を試行
            return search_summoner_legacy(game_name)
    else:
        print('📋 Legacy Summoner Name形式を検出')
        # Legacy検索を直接実行
        return search_summoner_legacy(player_identifier)

if __name__ == "__main__":
    """
    メインテスト実行部
    
    複数の検索方法を順次テストし、結果を比較表示。
    実際の開発では、このテスト結果を参考に最適な検索方法を選択。
    """
    print('=' * 50)
    print('🔍 Riot Games API プレイヤー検索テスト')
    print('🎯 テスト対象: Day1week#Day1 (日本ランキング上位プレイヤー)')
    print('=' * 50)
    
    # ステップ1: APIキー有効性確認
    api_success = test_api_key()
    
    if api_success:
        print('\n' + '=' * 50)
        print('👤 プレイヤー検索テスト - 3つの手法比較')
        print('=' * 50)
        
        # テスト対象プレイヤー
        test_name = "Day1week#Day1"
        print(f'🎯 テスト対象: {test_name}')
        
        # Method 1: レガシーAPI（#を含めた形式）
        print('\n' + '-' * 30)
        print('📊 Method 1: Legacy API（#を含む完全名）')
        print('💡 期待結果: 403エラー（2023年11月以降制限）')
        print('-' * 30)
        search_summoner_legacy(test_name)
        
        # Method 2: レガシーAPI（#を除いた形式）
        print('\n' + '-' * 30)
        print('📊 Method 2: Legacy API（Game Name のみ）')
        print('💡 期待結果: 403エラー（2023年11月以降制限）')
        print('-' * 30)
        search_summoner_legacy("Day1week")
        
        # Method 3: 新しいRiot ID API
        print('\n' + '-' * 30)
        print('📊 Method 3: Riot ID API（推奨）')
        print('💡 期待結果: 成功（高い確率）')
        print('-' * 30)
        search_riot_id("Day1week", "Day1")
        
        # Method 4: 包括的検索（統合メソッド）
        print('\n' + '-' * 30)
        print('📊 Method 4: 包括的検索（自動フォールバック）')
        print('💡 期待結果: Riot ID成功、またはLegacyフォールバック')
        print('-' * 30)
        search_player_comprehensive(test_name)
        
        # テスト結果まとめ
        print('\n' + '=' * 50)
        print('📊 検索結果まとめ')
        print('=' * 50)
        print('💡 テストした検索方法:')
        print('   1. Legacy API + 完全名（Day1week#Day1）')
        print('   2. Legacy API + Game Name のみ（Day1week）')
        print('   3. Riot ID API + 分離形式（Day1week + Day1）✅ 推奨')
        print('   4. 包括的検索（自動判定・フォールバック）✅ 実用的')
        print('')
        print('🔧 実装参照先:')
        print('   - 本ファイル（api_test.py）: テスト・デバッグ用実装')
        print('   - src/collectors/lol_fetcher.py: プロダクション用実装')
        print('   - LoLFetcher.search_by_riot_id(): 推奨メソッド')
        print('   - LoLFetcher.search_player_comprehensive(): 統合メソッド')
        print('')
        print('📚 詳細ドキュメント:')
        print('   - Riot Developer Portal: https://developer.riotgames.com/')
        print('   - Summoner Name to Riot ID FAQ: .../summoner-name-to-riot-id-faq')
    else:
        print('\n❌ APIキーの設定に問題があります。')
        print('💡 .envファイルにRIOT_API_KEYを設定してください。') 