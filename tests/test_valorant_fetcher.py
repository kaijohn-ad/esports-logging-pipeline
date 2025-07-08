"""ValorantFetcher機能のテスト

TDD（テスト駆動開発）に基づき、ValorantFetcherクラスの
機能をテストします。
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import aiohttp
import time
import json

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from collectors.valorant_fetcher import ValorantFetcher
from collectors.rate_limiter import RateLimiter


class TestValorantFetcher:
    """ValorantFetcher機能のテストクラス"""
    
    @pytest.fixture
    def fetcher(self):
        """テスト用のValorantFetcherインスタンス"""
        return ValorantFetcher(region="ap")
    
    @pytest.fixture
    def sample_match_data(self):
        """テスト用のマッチデータ"""
        return {
            "status": 200,
            "data": {
                "metadata": {
                    "matchid": "test_match_123",
                    "map": "Bind",
                    "game_version": "release-08.11",
                    "game_length": 1800000,  # 30分をms
                    "game_start": 1640995200,
                    "rounds_played": 13,
                    "mode": "Competitive",
                    "queue": "competitive",
                    "region": "ap",
                    "cluster": "ap"
                },
                "players": {
                    "all_players": [
                        {
                            "puuid": "test_puuid_1",
                            "name": "TestPlayer",
                            "tag": "TST",
                            "team": "Red",
                            "character": "Sage",
                            "stats": {
                                "kills": 15,
                                "deaths": 8,
                                "assists": 5,
                                "score": 3250,
                                "headshots": 8,
                                "bodyshots": 12,
                                "legshots": 3,
                                "damage": {
                                    "made": 2800,
                                    "received": 1900
                                },
                                "first_bloods": 3,
                                "first_deaths": 1
                            }
                        }
                    ]
                },
                "teams": {
                    "red": {
                        "has_won": True,
                        "rounds_won": 13,
                        "rounds_lost": 5
                    },
                    "blue": {
                        "has_won": False,
                        "rounds_won": 5,
                        "rounds_lost": 13
                    }
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
                                "player_puuid": "test_puuid_1",
                                "kills": 2,
                                "damage": 350,
                                "score": 250
                            }
                        ]
                    }
                ]
            }
        }
    
    def test_fetcher_initialization(self, fetcher):
        """ValorantFetcherの初期化テスト"""
        # Given: ValorantFetcherクラスが実装されている
        # When: インスタンスを作成
        # Then: 適切に初期化される
        assert fetcher.base_url == "https://api.henrikdev.xyz/valorant"
        assert fetcher.region == "ap"
        assert hasattr(fetcher, 'rate_limiter')
        assert fetcher.rate_limiter.max_requests == 60
        assert fetcher.rate_limiter.time_window == 60
    
    def test_rate_limiter_initialization(self, fetcher):
        """レート制限機能の初期化テスト"""
        # Given: ValorantFetcherインスタンス
        # Then: レート制限機能が正しく設定される
        assert isinstance(fetcher.rate_limiter, RateLimiter)
        assert fetcher.rate_limiter.max_requests == 60  # 60 req/min
        assert fetcher.rate_limiter.time_window == 60
    
    @pytest.mark.asyncio
    async def test_context_manager_functionality(self, fetcher):
        """非同期コンテキストマネージャーのテスト"""
        # Given: ValorantFetcherインスタンス
        # When: async withブロックで使用
        async with fetcher as f:
            # Then: HTTPセッションが作成される
            assert f.session is not None
            assert isinstance(f.session, aiohttp.ClientSession)
        
        # Then: コンテキストマネージャー終了時にセッションが閉じられる
        assert f.session.closed
    
    @pytest.mark.asyncio
    async def test_make_request_success(self, fetcher):
        """API リクエスト成功時のテスト"""
        # Given: 成功レスポンスを返すモックAPI
        mock_response_data = {"status": 200, "data": {"test": "data"}}
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with fetcher:
                # When: API リクエストを実行
                result = await fetcher._make_request("v1/test")
                
                # Then: 正しい結果が返される
                assert result == mock_response_data
    
    @pytest.mark.asyncio
    async def test_make_request_rate_limit_429(self, fetcher):
        """レート制限（429エラー）時のテスト"""
        # Given: 429エラーを返すモックAPI
        with patch('aiohttp.ClientSession.get') as mock_get:
            # 最初は429エラー、次は成功
            mock_response_429 = AsyncMock()
            mock_response_429.status = 429
            mock_response_429.headers = {'Retry-After': '1'}
            
            mock_response_success = AsyncMock()
            mock_response_success.status = 200
            mock_response_success.json = AsyncMock(return_value={"success": True})
            
            mock_get.return_value.__aenter__.side_effect = [
                mock_response_429,
                mock_response_success
            ]
            
            with patch('asyncio.sleep') as mock_sleep:
                async with fetcher:
                    # When: レート制限エラーが発生
                    result = await fetcher._make_request("v1/test")
                    
                    # Then: 再試行後に成功する
                    assert result == {"success": True}
                    mock_sleep.assert_called_once_with(1)
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_success(self, fetcher):
        """リトライ機能付きAPI呼び出し成功テスト"""
        # Given: 成功レスポンス
        mock_data = {"status": 200, "data": {"player": "info"}}
        
        with patch.object(fetcher, '_make_request') as mock_request:
            mock_request.return_value = mock_data
            
            # When: リトライ機能付きでリクエスト
            result = await fetcher.fetch_with_retry("v1/account/player/tag")
            
            # Then: 正しい結果が返される
            assert result == mock_data
            mock_request.assert_called_once_with("v1/account/player/tag", None)
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_max_retries_exceeded(self, fetcher):
        """最大リトライ回数を超えた場合のテスト"""
        # Given: 常にエラーを返すAPI
        with patch.object(fetcher, '_make_request') as mock_request:
            mock_request.side_effect = Exception("API Error")
            
            # When: 最大リトライ回数を超える
            # Then: 例外が発生する
            with pytest.raises(Exception):
                await fetcher.fetch_with_retry("v1/test", max_retries=2)
            
            # 3回（初回 + 2回リトライ）呼ばれることを確認
            assert mock_request.call_count == 3
    
    @pytest.mark.asyncio
    async def test_fetch_player_info(self, fetcher):
        """プレイヤー情報取得テスト"""
        # Given: プレイヤー情報レスポンス
        mock_data = {
            "data": {
                "puuid": "test_puuid",
                "region": "ap",
                "account_level": 100
            }
        }
        
        with patch.object(fetcher, 'fetch_with_retry') as mock_fetch:
            mock_fetch.return_value = mock_data
            
            # When: プレイヤー情報を取得
            result = await fetcher.fetch_player_info("TestPlayer", "TST")
            
            # Then: 正しいエンドポイントが呼ばれる
            mock_fetch.assert_called_once_with("v1/account/TestPlayer/TST")
            assert result == mock_data
    
    @pytest.mark.asyncio
    async def test_fetch_match_history(self, fetcher):
        """マッチ履歴取得テスト"""
        # Given: マッチ履歴レスポンス
        mock_data = {
            "data": [
                {"metadata": {"matchid": "match1"}},
                {"metadata": {"matchid": "match2"}}
            ]
        }
        
        with patch.object(fetcher, 'fetch_with_retry') as mock_fetch:
            mock_fetch.return_value = mock_data
            
            # When: マッチ履歴を取得
            result = await fetcher.fetch_match_history("TestPlayer", "TST", size=5)
            
            # Then: 正しいエンドポイントとパラメータが使用される
            mock_fetch.assert_called_once_with("v3/matches/ap/TestPlayer/TST", {"size": 5})
            assert result == mock_data
    
    def test_extract_player_performance(self, fetcher, sample_match_data):
        """プレイヤーパフォーマンス抽出テスト"""
        # Given: サンプルマッチデータ
        # When: プレイヤーパフォーマンスを抽出
        result = fetcher.extract_player_performance(sample_match_data, "test_puuid_1")
        
        # Then: 正しいパフォーマンスデータが返される
        assert result is not None
        assert result["puuid"] == "test_puuid_1"
        assert result["name"] == "TestPlayer#TST"
        assert result["agent"] == "Sage"
        assert result["team"] == "Red"
        assert result["kills"] == 15
        assert result["deaths"] == 8
        assert result["assists"] == 5
        assert result["kda"] == 2.5  # (15 + 5) / 8
        assert result["headshots"] == 8
        assert result["damage_made"] == 2800
        assert result["first_bloods"] == 3
    
    def test_extract_player_performance_not_found(self, fetcher, sample_match_data):
        """存在しないプレイヤーのパフォーマンス抽出テスト"""
        # Given: サンプルマッチデータ
        # When: 存在しないプレイヤーのパフォーマンスを抽出
        result = fetcher.extract_player_performance(sample_match_data, "nonexistent_puuid")
        
        # Then: Noneが返される
        assert result is None
    
    def test_extract_team_performance(self, fetcher, sample_match_data):
        """チームパフォーマンス抽出テスト"""
        # Given: サンプルマッチデータ
        # When: チームパフォーマンスを抽出
        result = fetcher.extract_team_performance(sample_match_data, "red")
        
        # Then: 正しいチームデータが返される
        assert result is not None
        assert result["team"] == "red"
        assert result["has_won"] is True
        assert result["rounds_won"] == 13
        assert result["rounds_lost"] == 5
    
    def test_extract_match_metadata(self, fetcher, sample_match_data):
        """マッチメタデータ抽出テスト"""
        # Given: サンプルマッチデータ
        # When: マッチメタデータを抽出
        result = fetcher.extract_match_metadata(sample_match_data)
        
        # Then: 正しいメタデータが返される
        assert result["matchid"] == "test_match_123"
        assert result["map"] == "Bind"
        assert result["game_version"] == "release-08.11"
        assert result["game_length"] == 1800000
        assert result["rounds_played"] == 13
        assert result["mode"] == "Competitive"
        assert result["region"] == "ap"
    
    def test_calculate_kda(self, fetcher):
        """KDA計算テスト"""
        # Given: キル、デス、アシスト数
        # When: KDAを計算
        # Then: 正しいKDAが返される
        
        # 通常のKDA
        assert fetcher._calculate_kda(10, 5, 3) == 2.6
        
        # パーフェクトKDA（デス0）
        assert fetcher._calculate_kda(8, 0, 2) == 10.0
        
        # デスのみ
        assert fetcher._calculate_kda(0, 5, 0) == 0.0
    
    def test_get_headshot_percentage(self, fetcher):
        """ヘッドショット率計算テスト"""
        # Given: プレイヤーデータ
        player_data = {
            "stats": {
                "headshots": 8,
                "bodyshots": 12,
                "legshots": 5
            }
        }
        
        # When: ヘッドショット率を計算
        result = fetcher.get_headshot_percentage(player_data)
        
        # Then: 正しい割合が返される
        expected = (8 / (8 + 12 + 5)) * 100  # 32%
        assert result == round(expected, 2)
    
    def test_get_headshot_percentage_no_shots(self, fetcher):
        """ショット数0の場合のヘッドショット率テスト"""
        # Given: ショット数0のプレイヤーデータ
        player_data = {
            "stats": {
                "headshots": 0,
                "bodyshots": 0,
                "legshots": 0
            }
        }
        
        # When: ヘッドショット率を計算
        result = fetcher.get_headshot_percentage(player_data)
        
        # Then: 0.0が返される
        assert result == 0.0
    
    @pytest.mark.asyncio
    async def test_batch_fetch_match_details(self, fetcher):
        """マッチ詳細バッチ取得テスト"""
        # Given: 複数のマッチID
        match_ids = ["match1", "match2", "match3"]
        mock_responses = {
            "match1": {"data": {"match1": "data"}},
            "match2": {"data": {"match2": "data"}},
            "match3": None  # エラーケース
        }
        
        with patch.object(fetcher, 'fetch_match_details') as mock_fetch:
            # 3回目だけエラー
            mock_fetch.side_effect = [
                mock_responses["match1"],
                mock_responses["match2"],
                Exception("API Error")
            ]
            
            # When: バッチ取得を実行
            results = await fetcher.batch_fetch_match_details(match_ids)
            
            # Then: 成功分は結果が、失敗分はNoneが返される
            assert results["match1"] == mock_responses["match1"]
            assert results["match2"] == mock_responses["match2"]
            assert results["match3"] is None
            assert mock_fetch.call_count == 3


class TestValorantFetcherEdgeCases:
    """ValorantFetcher のエッジケーステスト"""
    
    @pytest.fixture
    def fetcher(self):
        return ValorantFetcher(region="ap")
    
    def test_extract_player_performance_empty_data(self, fetcher):
        """空のデータでのプレイヤーパフォーマンス抽出テスト"""
        # Given: 空のマッチデータ
        empty_data = {"data": {"players": {"all_players": []}}}
        
        # When: パフォーマンスを抽出
        result = fetcher.extract_player_performance(empty_data, "any_puuid")
        
        # Then: Noneが返される
        assert result is None
    
    def test_extract_team_performance_nonexistent_team(self, fetcher):
        """存在しないチームのパフォーマンス抽出テスト"""
        # Given: チームデータ
        data = {"data": {"teams": {"red": {"has_won": True}}}}
        
        # When: 存在しないチームのパフォーマンスを抽出
        result = fetcher.extract_team_performance(data, "green")
        
        # Then: Noneが返される
        assert result is None
    
    def test_get_first_blood_percentage_empty_matches(self, fetcher):
        """空のマッチリストでのファーストブラッド率計算テスト"""
        # Given: 空のマッチリスト
        empty_matches = []
        
        # When: ファーストブラッド率を計算
        result = fetcher.get_first_blood_percentage(empty_matches, "test_puuid")
        
        # Then: 0.0が返される
        assert result == 0.0