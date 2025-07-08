"""LoLFetcher拡張機能のテスト

TDD（テスト駆動開発）に基づき、LoLFetcherクラスの
拡張機能をテストします。
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import time

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLFetcher, RateLimiter
from riotwatcher import ApiError


class TestLoLFetcherEnhanced:
    """LoLFetcher拡張機能のテストクラス"""
    
    @pytest.fixture
    def fetcher(self):
        """テスト用のLoLFetcherインスタンス"""
        return LoLFetcher("test_api_key", region="jp1")
    
    def test_rate_limiter_initialization(self, fetcher):
        """レート制限機能の初期化テスト"""
        # レート制限機能が正しく初期化されているかテスト
        assert hasattr(fetcher, 'rate_limiter')
        assert fetcher.rate_limiter.max_requests == 20
        assert fetcher.rate_limiter.time_window == 120
    
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, fetcher):
        """レート制限が正しく適用されるかテスト"""
        # 20回のリクエスト後、レート制限が適用されるかテスト
        start_time = time.time()
        
        # モックAPI呼び出し
        with patch.object(fetcher.watch.match, 'by_id', return_value={"matchId": "test"}):
            # 20回連続でAPI呼び出し
            for i in range(20):
                await fetcher._rate_limited_request(
                    fetcher.watch.match.by_id, f"test_match_{i}"
                )
            
            # 21回目はレート制限により待機が発生するはず
            await fetcher._rate_limited_request(
                fetcher.watch.match.by_id, "test_match_21"
            )
        
        elapsed_time = time.time() - start_time
        # レート制限により待機時間が発生することを確認
        assert elapsed_time > 0.1  # 最低限の待機時間
    
    @pytest.mark.asyncio
    async def test_retry_on_api_error(self, fetcher):
        """API エラー時のリトライ機能テスト"""
        # 429エラー（レート制限）が発生した場合のリトライテスト
        error_429 = ApiError("Rate limit exceeded", 429)
        
        with patch.object(fetcher.watch.match, 'by_id') as mock_api:
            # 最初の2回は429エラー、3回目は成功
            mock_api.side_effect = [
                error_429,
                error_429,
                {"matchId": "success"}
            ]
            
            result = await fetcher.fetch_with_retry(
                fetcher.watch.match.by_id, "test_match"
            )
            
            assert result["matchId"] == "success"
            assert mock_api.call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self, fetcher):
        """最大リトライ回数を超えた場合のテスト"""
        error_500 = ApiError("Internal server error", 500)
        
        with patch.object(fetcher.watch.match, 'by_id') as mock_api:
            mock_api.side_effect = error_500
            
            with pytest.raises(ApiError):
                await fetcher.fetch_with_retry(
                    fetcher.watch.match.by_id, "test_match", max_retries=3
                )
            
            assert mock_api.call_count == 4  # 初回 + 3回リトライ
    
    def test_fetch_match_details_exists(self, fetcher):
        """マッチ詳細情報の取得メソッドが存在することのテスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'fetch_match_details')
        assert callable(getattr(fetcher, 'fetch_match_details'))
    
    def test_fetch_summoner_rank_exists(self, fetcher):
        """サマナーランク情報の取得メソッドが存在することのテスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'fetch_summoner_rank')
        assert callable(getattr(fetcher, 'fetch_summoner_rank'))
    
    def test_structured_logging_setup(self, fetcher):
        """構造化ログの設定テスト"""
        # ログ機能が設定されているかテスト
        assert hasattr(fetcher, 'logger')
        assert fetcher.logger is not None
    
    def test_metrics_collection_setup(self, fetcher):
        """メトリクス収集機能の設定テスト"""
        # メトリクス機能が設定されているかテスト（まだ実装されていない）
        assert not hasattr(fetcher, 'metrics')  # 実装前は失敗すべき


class TestRateLimiter:
    """レート制限機能のテスト"""
    
    def test_rate_limiter_initialization(self):
        """レート制限クラスが実装されていることのテスト"""
        # RateLimiterクラスが存在することを確認
        rate_limiter = RateLimiter(10, 60)
        assert rate_limiter.max_requests == 10
        assert rate_limiter.time_window == 60
    
    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_basic(self):
        """レート制限の基本的な動作テスト"""
        rate_limiter = RateLimiter(2, 10)  # 10秒間に2リクエスト
        
        # 最初の2リクエストは即座に通るはず
        start_time = time.time()
        await rate_limiter.acquire()
        await rate_limiter.acquire()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1  # ほぼ即座に完了 