"""
League of Legends データ取得モジュール

Riot Games APIを使用してLoLマッチデータを取得する
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Callable

from riotwatcher import LolWatcher, ApiError
from .rate_limiter import RateLimiter


class LoLFetcher:
    """拡張されたLoLデータ取得クラス"""
    
    def __init__(self, api_key: str, region: str = "jp1"):
        self.watch = LolWatcher(api_key)
        self.region = region
        self.rate_limiter = RateLimiter(20, 120)  # 20 requests per 2 minutes
        
        # ログ設定
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def _rate_limited_request(self, func: Callable, *args, **kwargs):
        """レート制限付きAPIリクエスト"""
        await self.rate_limiter.acquire()
        return func(*args, **kwargs)

    async def fetch_with_retry(self, func: Callable, *args, max_retries: int = 3, **kwargs):
        """指数バックオフによるリトライ機能付きAPIリクエスト"""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self._rate_limited_request(func, *args, **kwargs)
                
            except ApiError as e:
                last_error = e
                self.logger.warning(f"API error on attempt {attempt + 1}: {e}")
                
                # リトライしない条件
                if e.response.status_code in [400, 401, 403, 404]:
                    raise e
                    
                # リトライする条件
                if attempt < max_retries:
                    wait_time = (2 ** attempt) + (time.time() % 1)  # 指数バックオフ
                    self.logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Max retries exceeded for API call")
                    raise e
                    
        if last_error:
            raise last_error

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
    
    # 新しいマッチ詳細機能
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