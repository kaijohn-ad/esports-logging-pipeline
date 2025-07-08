"""
VALORANT データ取得モジュール

非公式APIを使用してVALORANTマッチデータを取得する
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import aiohttp

from .rate_limiter import RateLimiter


class ValorantFetcher:
    """VALORANTデータ取得クラス"""
    
    def __init__(self, region: str = "ap"):
        self.base_url = "https://api.henrikdev.xyz/valorant"
        self.region = region
        self.rate_limiter = RateLimiter(60, 60)  # 60 requests per minute
        
        # ログ設定
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # HTTPセッション
        self.session = None

    async def __aenter__(self):
        """非同期コンテキストマネージャー開始"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャー終了"""
        if self.session:
            await self.session.close()

    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """API リクエストを実行"""
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}/{endpoint}"
        
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                elif response.status == 429:
                    # レート制限に引っかかった場合
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    return await self._make_request(endpoint, params)
                else:
                    self.logger.error(f"API request failed: {response.status}")
                    response.raise_for_status()
                    
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            raise

    async def fetch_with_retry(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Dict[str, Any]:
        """指数バックオフによるリトライ機能付きAPIリクエスト"""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return await self._make_request(endpoint, params)
                
            except Exception as e:
                last_error = e
                self.logger.warning(f"API error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries:
                    wait_time = (2 ** attempt) + (time.time() % 1)  # 指数バックオフ
                    self.logger.info(f"Retrying in {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Max retries exceeded for API call")
                    raise e
                    
        if last_error:
            raise last_error

    async def fetch_player_info(self, username: str, tag: str) -> Dict[str, Any]:
        """プレイヤー基本情報を取得"""
        endpoint = f"v1/account/{username}/{tag}"
        return await self.fetch_with_retry(endpoint)

    async def fetch_match_history(self, username: str, tag: str, size: int = 5) -> Dict[str, Any]:
        """マッチ履歴を取得"""
        endpoint = f"v3/matches/{self.region}/{username}/{tag}"
        params = {"size": size}
        return await self.fetch_with_retry(endpoint, params)

    async def fetch_match_details(self, match_id: str) -> Dict[str, Any]:
        """マッチ詳細情報を取得"""
        endpoint = f"v2/match/{match_id}"
        return await self.fetch_with_retry(endpoint)

    async def fetch_player_stats(self, username: str, tag: str, mode: str = "competitive") -> Dict[str, Any]:
        """プレイヤー統計情報を取得"""
        endpoint = f"v1/stats/{self.region}/{username}/{tag}"
        params = {"mode": mode}
        return await self.fetch_with_retry(endpoint, params)

    async def fetch_player_rank(self, username: str, tag: str) -> Dict[str, Any]:
        """プレイヤーランク情報を取得"""
        endpoint = f"v1/mmr/{self.region}/{username}/{tag}"
        return await self.fetch_with_retry(endpoint)

    def extract_player_performance(self, match_data: Dict[str, Any], puuid: str) -> Optional[Dict[str, Any]]:
        """特定プレイヤーのパフォーマンス情報を抽出"""
        players = match_data.get("data", {}).get("players", {}).get("all_players", [])
        
        for player in players:
            if player.get("puuid") == puuid:
                stats = player.get("stats", {})
                return {
                    "puuid": puuid,
                    "name": f"{player.get('name')}#{player.get('tag')}",
                    "agent": player.get("character"),
                    "team": player.get("team"),
                    "kills": stats.get("kills", 0),
                    "deaths": stats.get("deaths", 0),
                    "assists": stats.get("assists", 0),
                    "kda": self._calculate_kda(
                        stats.get("kills", 0),
                        stats.get("deaths", 0),
                        stats.get("assists", 0)
                    ),
                    "score": stats.get("score", 0),
                    "bodyshots": stats.get("bodyshots", 0),
                    "headshots": stats.get("headshots", 0),
                    "legshots": stats.get("legshots", 0),
                    "damage_made": stats.get("damage", {}).get("made", 0),
                    "damage_received": stats.get("damage", {}).get("received", 0),
                    "first_bloods": stats.get("first_bloods", 0),
                    "first_deaths": stats.get("first_deaths", 0)
                }
        
        return None

    def extract_team_performance(self, match_data: Dict[str, Any], team: str) -> Optional[Dict[str, Any]]:
        """特定チームのパフォーマンス情報を抽出"""
        teams = match_data.get("data", {}).get("teams", {})
        
        if team in teams:
            team_data = teams[team]
            return {
                "team": team,
                "has_won": team_data.get("has_won", False),
                "rounds_won": team_data.get("rounds_won", 0),
                "rounds_lost": team_data.get("rounds_lost", 0)
            }
        
        return None

    def extract_match_metadata(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """マッチのメタデータを抽出"""
        metadata = match_data.get("data", {}).get("metadata", {})
        return {
            "matchid": metadata.get("matchid"),
            "map": metadata.get("map"),
            "game_version": metadata.get("game_version"),
            "game_length": metadata.get("game_length"),
            "game_start": metadata.get("game_start"),
            "game_start_patched": metadata.get("game_start_patched"),
            "rounds_played": metadata.get("rounds_played"),
            "mode": metadata.get("mode"),
            "queue": metadata.get("queue"),
            "season_id": metadata.get("season_id"),
            "platform": metadata.get("platform"),
            "premiere_info": metadata.get("premiere_info"),
            "region": metadata.get("region"),
            "cluster": metadata.get("cluster")
        }

    def extract_round_details(self, match_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ラウンド詳細情報を抽出"""
        rounds = match_data.get("data", {}).get("rounds", [])
        round_details = []
        
        for round_data in rounds:
            round_info = {
                "round_num": round_data.get("round_num"),
                "round_result": round_data.get("round_result"),
                "round_ceremony": round_data.get("round_ceremony"),
                "winning_team": round_data.get("winning_team"),
                "bomb_planted": round_data.get("plant_events") is not None,
                "bomb_defused": round_data.get("defuse_events") is not None,
                "plant_events": round_data.get("plant_events", []),
                "defuse_events": round_data.get("defuse_events", []),
                "player_stats": round_data.get("player_stats", [])
            }
            round_details.append(round_info)
        
        return round_details

    async def batch_fetch_match_details(self, match_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """複数マッチの詳細情報をバッチ取得"""
        results = {}
        
        # 並列処理で複数のマッチ詳細を取得
        tasks = []
        for match_id in match_ids:
            task = self.fetch_match_details(match_id)
            tasks.append((match_id, task))
        
        # 順次実行（レート制限を考慮）
        for match_id, task in tasks:
            try:
                result = await task
                results[match_id] = result
            except Exception as e:
                self.logger.warning(f"Failed to fetch match details for {match_id}: {e}")
                results[match_id] = None
        
        return results

    def _calculate_kda(self, kills: int, deaths: int, assists: int) -> float:
        """KDA比を計算"""
        if deaths == 0:
            return float(kills + assists)  # Perfect KDA
        return round((kills + assists) / deaths, 2)

    def get_headshot_percentage(self, player_data: Dict[str, Any]) -> float:
        """ヘッドショット率を計算"""
        stats = player_data.get("stats", {})
        headshots = stats.get("headshots", 0)
        bodyshots = stats.get("bodyshots", 0)
        legshots = stats.get("legshots", 0)
        
        total_shots = headshots + bodyshots + legshots
        
        if total_shots == 0:
            return 0.0
        
        return round((headshots / total_shots) * 100, 2)

    def get_first_blood_percentage(self, matches_data: List[Dict[str, Any]], puuid: str) -> float:
        """ファーストブラッド率を計算"""
        total_rounds = 0
        first_blood_rounds = 0
        
        for match in matches_data:
            player_data = self.extract_player_performance(match, puuid)
            if player_data:
                # マッチ中のラウンド数を取得
                match_rounds = match.get("data", {}).get("metadata", {}).get("rounds_played", 0)
                total_rounds += match_rounds
                first_blood_rounds += player_data.get("first_bloods", 0)
        
        if total_rounds == 0:
            return 0.0
        
        return round((first_blood_rounds / total_rounds) * 100, 2)