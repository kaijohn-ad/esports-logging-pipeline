"""
League of Legends データ取得モジュール

Riot Games APIを使用してLoLマッチデータを取得する
"""

import asyncio
import logging
import time
import json
import requests
import os
from typing import Dict, Any, List, Callable, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from riotwatcher import LolWatcher, ApiError
from .rate_limiter import RateLimiter

# 設定クラスのインポート
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.lol_config import LoLConfig, ErrorHandlingConfig


# カスタム例外クラス
class LoLFetcherError(Exception):
    """LoLFetcher関連のカスタム例外"""
    pass


class APIRateLimitError(LoLFetcherError):
    """APIレート制限エラー"""
    pass


class APIQuotaExceededError(LoLFetcherError):
    """API割当量超過エラー"""
    pass


class DataValidationError(LoLFetcherError):
    """データ検証エラー"""
    pass


class LoLFetcher:
    """拡張されたLoLデータ取得クラス"""
    
    def __init__(self, api_key: str, region: str = "jp1", config: Optional[LoLConfig] = None):
        self.watch = LolWatcher(api_key)
        self.region = region
        
        # 設定の初期化
        self.config = config or LoLConfig()
        error_config = self.config.error_handling
        
        # レート制限設定
        rate_config = self.config.api.rate_limit
        self.rate_limiter = RateLimiter(
            rate_config["max_requests"], 
            rate_config["time_window"]
        )
        
        # ログ設定
        self._setup_logging(error_config)
        
        # エラーメトリクス
        self.error_metrics = defaultdict(int)
        self.total_requests = 0
        self.consecutive_errors = 0
        self.last_error_time: Optional[datetime] = None
        
        # 設定ベースの初期化
        self.slack_webhook_url: Optional[str] = error_config.slack_webhook_url
        self.max_retries = error_config.max_retries
        self.retry_delay_base = error_config.retry_delay_base
        self.notify_on_errors = set(error_config.notify_on_errors)
        
        # メトリクス履歴（時系列データ）
        if error_config.collect_metrics:
            self.metrics_history = []
            self.metrics_retention = timedelta(hours=error_config.metrics_retention_hours)

    def _setup_logging(self, error_config: ErrorHandlingConfig):
        """ログ設定のセットアップ"""
        log_level = getattr(logging, error_config.log_level.upper(), logging.INFO)
        
        if error_config.structured_logging:
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        else:
            log_format = '%(message)s'
            
        logging.basicConfig(
            level=log_level,
            format=log_format
        )
        
        self.logger = logging.getLogger(__name__)
        
        # ファイルログ設定
        if error_config.log_to_file:
            os.makedirs(os.path.dirname(error_config.log_file_path), exist_ok=True)
            file_handler = logging.FileHandler(error_config.log_file_path)
            file_handler.setFormatter(logging.Formatter(log_format))
            self.logger.addHandler(file_handler)

    def set_slack_webhook(self, webhook_url: str):
        """Slack webhook URLを設定"""
        self.slack_webhook_url = webhook_url
        self.config.error_handling.slack_webhook_url = webhook_url
        
    def get_error_statistics(self) -> Dict[str, Any]:
        """エラー統計情報を取得"""
        total_errors = sum(self.error_metrics.values())
        error_rate = total_errors / max(self.total_requests, 1) * 100
        
        # 最近のエラー率計算（過去1時間）
        current_time = datetime.now()
        recent_errors = [
            entry for entry in self.metrics_history
            if current_time - entry['timestamp'] <= timedelta(hours=1)
        ]
        recent_error_rate = len([e for e in recent_errors if e['is_error']]) / max(len(recent_errors), 1) * 100
        
        return {
            'total_errors': total_errors,
            'error_by_type': dict(self.error_metrics),
            'error_rate': error_rate,
            'recent_error_rate': recent_error_rate,
            'total_requests': self.total_requests,
            'consecutive_errors': self.consecutive_errors,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None
        }

    def _should_alert(self, error: Exception) -> bool:
        """アラートを送信すべきかどうかを判定"""
        if not self.config.error_handling.slack_notifications_enabled:
            return False
            
        # エラータイプによる判定
        if isinstance(error, ApiError):
            if error.response.status_code not in self.notify_on_errors:
                return False
        
        # エラー率による判定
        stats = self.get_error_statistics()
        if stats['recent_error_rate'] > self.config.error_handling.error_rate_threshold:
            return True
            
        # 連続エラー数による判定
        if self.consecutive_errors >= self.config.error_handling.critical_error_threshold:
            return True
            
        return False

    def _log_structured_error(self, error: Exception, context: Dict[str, Any]):
        """構造化エラーログの記録"""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context,
            'consecutive_errors': self.consecutive_errors
        }
        
        if isinstance(error, ApiError):
            error_data.update({
                'status_code': error.response.status_code,
                'api_error': True
            })
            # メトリクス更新
            self.error_metrics[str(error.response.status_code)] += 1
            
        # メトリクス履歴に追加
        if self.config.error_handling.collect_metrics:
            self.metrics_history.append({
                'timestamp': datetime.now(),
                'is_error': True,
                'error_type': type(error).__name__,
                'context': context
            })
            self._cleanup_old_metrics()
        
        if self.config.error_handling.structured_logging:
            self.logger.error(json.dumps(error_data))
        else:
            self.logger.error(f"Error: {error_data['error_type']} - {error_data['error_message']}")
        
    def _cleanup_old_metrics(self):
        """古いメトリクスデータのクリーンアップ"""
        current_time = datetime.now()
        self.metrics_history = [
            entry for entry in self.metrics_history
            if current_time - entry['timestamp'] <= self.metrics_retention
        ]
        
    def _send_slack_notification(self, error: Exception, context: Dict[str, Any]):
        """Slack通知の送信"""
        if not self.slack_webhook_url or not self._should_alert(error):
            return
            
        try:
            stats = self.get_error_statistics()
            message = {
                'text': f"🚨 LoL API Error Alert\n"
                       f"**Error**: {type(error).__name__}\n"
                       f"**Message**: {str(error)}\n"
                       f"**Context**: {context.get('match_id', context.get('summoner_id', 'unknown'))}\n"
                       f"**Status Code**: {getattr(error, 'response', {}).get('status_code', 'N/A')}\n"
                       f"**Error Rate**: {stats['recent_error_rate']:.1f}%\n"
                       f"**Consecutive Errors**: {self.consecutive_errors}\n"
                       f"**Time**: {datetime.now().isoformat()}"
            }
            
            requests.post(self.slack_webhook_url, json=message, timeout=10)
            self.logger.info("Slack notification sent successfully")
        except Exception as slack_error:
            self.logger.warning(f"Failed to send Slack notification: {slack_error}")

    async def _rate_limited_request(self, func: Callable, *args, **kwargs):
        """レート制限付きAPIリクエスト"""
        if self.config.error_handling.respect_rate_limits:
            await self.rate_limiter.acquire()
        
        self.total_requests += 1
        
        # メトリクス履歴に追加
        if self.config.error_handling.collect_metrics:
            self.metrics_history.append({
                'timestamp': datetime.now(),
                'is_error': False,
                'context': {'function': func.__name__}
            })
            self._cleanup_old_metrics()
            
        return func(*args, **kwargs)

    async def fetch_with_retry(self, func: Callable, *args, max_retries: Optional[int] = None, **kwargs):
        """指数バックオフによるリトライ機能付きAPIリクエスト"""
        max_retries = max_retries or self.max_retries
        last_error = None
        context = {'function': func.__name__, 'args': args, 'kwargs': kwargs}
        
        for attempt in range(max_retries + 1):
            try:
                result = await self._rate_limited_request(func, *args, **kwargs)
                # 成功時は連続エラーカウントをリセット
                self.consecutive_errors = 0
                return result
                
            except ApiError as e:
                last_error = e
                self.consecutive_errors += 1
                self.last_error_time = datetime.now()
                
                context.update({'attempt': attempt + 1, 'max_retries': max_retries})
                
                self._log_structured_error(e, context)
                self.logger.warning(f"API error on attempt {attempt + 1}: {e}")
                
                # リトライしない条件
                if e.response.status_code in [400, 401, 403, 404]:
                    self._send_slack_notification(e, context)
                    raise e
                    
                # リトライする条件
                if attempt < max_retries:
                    wait_time = (self.retry_delay_base ** attempt) + (time.time() % 1)
                    self.logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Max retries exceeded for API call")
                    self._send_slack_notification(e, context)
                    raise e
                    
        if last_error:
            raise last_error

    async def fetch_with_enhanced_error_handling(self, func: Callable, *args, max_retries: Optional[int] = None, **kwargs):
        """拡張エラーハンドリング付きAPIリクエスト（カスタム例外変換）"""
        try:
            return await self.fetch_with_retry(func, *args, max_retries=max_retries, **kwargs)
        except ApiError as e:
            # APIエラーをカスタム例外に変換
            if e.response.status_code == 429:
                raise APIRateLimitError(f"Rate limit exceeded: {e}") from e
            elif e.response.status_code == 403:
                raise APIQuotaExceededError(f"API quota exceeded: {e}") from e
            else:
                raise e

    # 既存メソッドの安全版
    async def fetch_match_details_safe(self, match_id: str) -> Dict[str, Any]:
        """マッチ詳細情報を安全に取得（エラーハンドリング付き）"""
        context = {'match_id': match_id}
        try:
            return await self.fetch_with_retry(
                self.watch.match.by_id, self.region, match_id
            )
        except Exception as e:
            self._log_structured_error(e, context)
            raise

    async def fetch_summoner_rank_safe(self, summoner_id: str) -> Dict[str, Any]:
        """サマナーランク情報を安全に取得（エラーハンドリング付き）"""
        context = {'summoner_id': summoner_id}
        try:
            return await self.fetch_with_retry(
                self.watch.league.by_summoner, self.region, summoner_id
            )
        except Exception as e:
            self._log_structured_error(e, context)
            raise

    async def fetch_timeline_safe(self, match_id: str):
        """マッチタイムラインを安全に取得（エラーハンドリング付き）"""
        context = {'match_id': match_id}
        try:
            return await self.fetch_with_retry(
                self.watch.match.timeline_by_match, self.region, match_id
            )
        except Exception as e:
            self._log_structured_error(e, context)
            raise

    # === 既存メソッド（互換性のため保持）===
    def fetch_latest_matches(self, puuid: str, count: int = 5) -> List[str]:
        """最新のマッチIDリストを取得"""
        return self.watch.match.matchlist_by_puuid(self.region, puuid, count=count)

    def fetch_timeline(self, match_id: str):
        """マッチタイムラインを取得"""
        return self.watch.match.timeline_by_match(self.region, match_id)
    
    def fetch_match_details(self, match_id: str) -> Dict[str, Any]:
        """マッチ詳細情報を取得"""
        return self.watch.match.by_id(self.region, match_id)
    
    def fetch_summoner_rank(self, summoner_id: str) -> Dict[str, Any]:
        """サマナーランク情報を取得"""
        return self.watch.league.by_summoner(self.region, summoner_id)
    
    # === 以下は既存の拡張メソッド ===
    def fetch_match_with_player_info(self, match_id: str) -> Dict[str, Any]:
        """プレイヤー情報付きマッチ詳細を取得"""
        match_data = self.fetch_match_details(match_id)
        
        # プレイヤー情報を拡張
        for participant in match_data.get("info", {}).get("participants", []):
            puuid = participant.get("puuid")
            if puuid:
                try:
                    summoner_info = self.fetch_summoner_by_puuid(puuid)
                    participant["summonerInfo"] = summoner_info
                except Exception as e:
                    self.logger.warning(f"Failed to fetch summoner info for {puuid}: {e}")
                    participant["summonerInfo"] = None
        
        return match_data
    
    def extract_player_performance(self, match_data: Dict[str, Any], puuid: str) -> Dict[str, Any]:
        """特定プレイヤーのパフォーマンス情報を抽出"""
        participants = match_data.get("info", {}).get("participants", [])
        
        for participant in participants:
            if participant.get("puuid") == puuid:
                return {
                    "puuid": puuid,
                    "championName": participant.get("championName"),
                    "teamId": participant.get("teamId"),
                    "kills": participant.get("kills", 0),
                    "deaths": participant.get("deaths", 0),
                    "assists": participant.get("assists", 0),
                    "kda": self._calculate_kda(
                        participant.get("kills", 0),
                        participant.get("deaths", 0),
                        participant.get("assists", 0)
                    ),
                    "cs": participant.get("totalMinionsKilled", 0) + participant.get("neutralMinionsKilled", 0),
                    "goldEarned": participant.get("goldEarned", 0),
                    "totalDamageDealt": participant.get("totalDamageDealtToChampions", 0),
                    "visionScore": participant.get("visionScore", 0),
                    "gameDuration": match_data.get("info", {}).get("gameDuration", 0)
                }
        
        return None
    
    def extract_team_performance(self, match_data: Dict[str, Any], team_id: int) -> Dict[str, Any]:
        """特定チームのパフォーマンス情報を抽出"""
        teams = match_data.get("info", {}).get("teams", [])
        
        for team in teams:
            if team.get("teamId") == team_id:
                objectives = team.get("objectives", {})
                return {
                    "teamId": team_id,
                    "win": team.get("win", False),
                    "baron": objectives.get("baron", {}).get("kills", 0),
                    "dragon": objectives.get("dragon", {}).get("kills", 0),
                    "tower": objectives.get("tower", {}).get("kills", 0),
                    "inhibitor": objectives.get("inhibitor", {}).get("kills", 0),
                    "riftHerald": objectives.get("riftHerald", {}).get("kills", 0)
                }
        
        return None
    
    def fetch_summoner_by_puuid(self, puuid: str) -> Dict[str, Any]:
        """PUUIDによるサマナー情報取得"""
        return self.watch.summoner.by_puuid(self.region, puuid)
    
    def batch_fetch_player_ranks(self, summoner_ids: List[str]) -> Dict[str, Any]:
        """複数プレイヤーのランク情報をバッチ取得"""
        results = {}
        
        for summoner_id in summoner_ids:
            try:
                rank_info = self.fetch_summoner_rank(summoner_id)
                results[summoner_id] = rank_info
            except Exception as e:
                self.logger.warning(f"Failed to fetch rank for {summoner_id}: {e}")
                results[summoner_id] = None
        
        return results
    
    def _calculate_kda(self, kills: int, deaths: int, assists: int) -> float:
        """KDA比を計算"""
        if deaths == 0:
            return float(kills + assists)  # Perfect KDA
        return round((kills + assists) / deaths, 2)