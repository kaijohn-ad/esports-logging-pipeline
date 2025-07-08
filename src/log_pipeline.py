"""eSports Logging Pipeline Skeleton
====================================
Python 3.12 / Typer CLI で動かす最小構成サンプル。
- Riot Games API（LoL）用バッチ取得
- Overwolf RT Collector からの JSONL 読み込み
- 共通スキーマへのキャノナイズ
- SQLite 保存

依存: typer, pydantic, riotwatcher, aiofiles, aiohttp
インストール:
    pip install typer[all] pydantic riotwatcher aiofiles aiohttp

このファイルを `python log_pipeline.py --help` で実行すると、
pull-all / run-gep / build-kpi などのサブコマンドが使えます。
"""

import json
import sqlite3
import asyncio
import datetime as dt
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Callable
from collections import deque

import typer
from pydantic import BaseModel, Field
from riotwatcher import LolWatcher, ApiError

app = typer.Typer(help="eSports log pipeline CLI")
DB_PATH = Path("data/esports.db")
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Rate Limiter for API calls
# ---------------------------------------------------------------------------
class RateLimiter:
    """API レート制限管理クラス"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """レート制限チェック、必要に応じて待機"""
        async with self._lock:
            now = time.time()
            
            # time_window を過ぎたリクエストを削除
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()
            
            # 制限に達している場合は待機
            if len(self.requests) >= self.max_requests:
                wait_time = self.requests[0] + self.time_window - now + 0.1
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    return await self.acquire()  # 再帰的に再チェック
            
            # リクエスト時刻を記録
            self.requests.append(now)

# ---------------------------------------------------------------------------
# Common schema (v1.0)
# ---------------------------------------------------------------------------
class Event(BaseModel):
    timestamp: float  # seconds since match start
    event: str        # kill, death, stun, ult, ring_move ...
    actor: str        # self / teammate / enemy-name
    target: str | None = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    def to_row(self, match_id: str):
        return (match_id, self.timestamp, self.event, self.actor, self.target, json.dumps(self.meta))

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db(path: Path = DB_PATH):
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS match (
        id       TEXT PRIMARY KEY,
        title    TEXT,
        patch    TEXT,
        ts       TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS event (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id TEXT,
        ts       REAL,
        event    TEXT,
        actor    TEXT,
        target   TEXT,
        meta     TEXT
    );
    """)
    con.commit()
    con.close()

# ---------------------------------------------------------------------------
# LoL Batch Fetcher (RiotWatcher) - Enhanced
# ---------------------------------------------------------------------------

class LoLCanonizer:
    """Convert Riot Timeline JSON -> List[Event]"""

    @staticmethod
    def timeline_to_events(tl: Dict[str, Any]) -> List[Event]:
        events: List[Event] = []
        for frame in tl.get("info", {}).get("frames", []):
            ts_base = frame["timestamp"] / 1000.0  # ms -> s
            for e in frame.get("events", []):
                etype = e.get("type")
                if etype == "CHAMPION_KILL":
                    events.append(Event(timestamp=ts_base,
                                          event="kill",
                                          actor=e["killerId"],
                                          target=e["victimId"],
                                          meta={"assists": e.get("assistingParticipantIds", [])}))
                elif etype == "SKILL_LEVEL_UP":
                    continue  # skip verbose events for now
        return events

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

# ---------------------------------------------------------------------------
# Overwolf RT Reader (consume JSONL produced by TS app)
# ---------------------------------------------------------------------------

async def consume_overwolf_jsonl(game_key: str):
    """Continuously tail JSONL files dumped by Overwolf TS listener"""
    from aiofiles import open as aio_open
    log_dir = RAW_DIR / game_key
    log_dir.mkdir(exist_ok=True)
    latest = max(log_dir.glob("*.jsonl"), default=None, key=lambda p: p.stat().st_mtime)
    if latest is None:
        typer.echo("No jsonl yet; waiting for producer…")
    else:
        typer.echo(f"Tail {latest}")
        async with aio_open(latest, "r") as f:
            await f.seek(0, 2)  # go to EOF
            while True:
                line = await f.readline()
                if line:
                    raw = json.loads(line)
                    # TODO: map raw to Event, then save
                else:
                    await asyncio.sleep(0.5)

# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

@app.command()
def init(db: Path = typer.Option(DB_PATH, help="SQLite path")):
    """Create DB schema"""
    init_db(db)
    typer.echo("DB initialized → " + str(db))

@app.command()
def pull_all(api_key: str = typer.Argument(..., envvar="RIOT_API_KEY"),
             summoner_name: str = typer.Option(...)):
    """Pull latest LoL matches and save to DB"""
    init_db()
    fetcher = LoLFetcher(api_key)
    puuid = fetcher.watch.summoner.by_name(fetcher.region, summoner_name)["puuid"]
    match_ids = fetcher.fetch_latest_matches(puuid, count=3)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    for mid in match_ids:
        typer.echo(f"Processing {mid}…")
        tl = fetcher.fetch_timeline(mid)
        events = LoLCanonizer.timeline_to_events(tl)
        cur.execute("INSERT OR IGNORE INTO match (id,title,patch,ts) VALUES (?,?,?,?)", (
            mid, "LoL", tl.get("info", {}).get("gameVersion", ""), dt.datetime.utcnow().isoformat()))
        cur.executemany("INSERT INTO event (match_id,ts,event,actor,target,meta) VALUES (?,?,?,?,?,?)",
                         [e.to_row(mid) for e in events])
    con.commit()
    con.close()
    typer.echo("Done.")

@app.command()
def build_kpi():
    """Aggregate simple KPIs (example: kill counts)"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT event, COUNT(*) FROM event GROUP BY event")
    for ev, cnt in cur.fetchall():
        typer.echo(f"{ev}: {cnt}")
    con.close()

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app()
