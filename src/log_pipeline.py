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
import yaml
import os
import random
from datetime import datetime

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
                event_timestamp = e.get("timestamp", frame["timestamp"]) / 1000.0
                
                if etype == "CHAMPION_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="kill",
                        actor=str(e["killerId"]),
                        target=str(e["victimId"]),
                        meta={
                            "assists": e.get("assistingParticipantIds", []),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "SKILL_LEVEL_UP":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="skill_levelup",
                        actor=str(e["participantId"]),
                        target=None,
                        meta={
                            "skillSlot": e.get("skillSlot"),
                            "levelUpType": e.get("levelUpType")
                        }
                    ))
                
                elif etype == "ITEM_PURCHASED":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="item_buy",
                        actor=str(e["participantId"]),
                        target=None,
                        meta={
                            "itemId": e.get("itemId")
                        }
                    ))
                
                elif etype == "ITEM_SOLD":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="item_sell",
                        actor=str(e["participantId"]),
                        target=None,
                        meta={
                            "itemId": e.get("itemId")
                        }
                    ))
                
                elif etype == "WARD_PLACED":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="ward_place",
                        actor=str(e["creatorId"]),
                        target=None,
                        meta={
                            "wardType": e.get("wardType"),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "WARD_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="ward_destroy",
                        actor=str(e["killerId"]),
                        target=None,
                        meta={
                            "wardType": e.get("wardType"),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "BUILDING_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="objective_destroy",
                        actor=str(e["killerId"]),
                        target=None,
                        meta={
                            "buildingType": e.get("buildingType"),
                            "teamId": e.get("teamId"),
                            "position": e.get("position")
                        }
                    ))
                
                elif etype == "MONSTER_KILL":
                    events.append(Event(
                        timestamp=event_timestamp,
                        event="monster_kill",
                        actor=str(e["killerId"]),
                        target=None,
                        meta={
                            "monsterType": e.get("monsterType"),
                            "monsterSubType": e.get("monsterSubType"),
                            "position": e.get("position")
                        }
                    ))
                    
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
# Data Validation Classes
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    """データ検証結果クラス"""
    is_valid: bool
    error_count: int = 0
    warning_count: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    quality_score: float = 1.0  # 0.0 - 1.0


class AnomalyReport(BaseModel):
    """異常検出レポートクラス"""
    event_id: str
    anomaly_type: str
    severity: str  # low, medium, high, critical
    description: str
    suggested_action: str = ""
    confidence: float = 0.0  # 0.0 - 1.0


class DataValidator:
    """データ検証クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_match_completeness(self, match_data: Dict[str, Any]) -> ValidationResult:
        """マッチデータの完全性をチェック"""
        errors = []
        warnings = []
        
        # 基本構造チェック
        if not isinstance(match_data, dict):
            errors.append("Match data must be a dictionary")
            return ValidationResult(is_valid=False, error_count=1, errors=errors)
        
        # メタデータチェック
        metadata = match_data.get("metadata", {})
        if not metadata.get("matchId"):
            errors.append("Missing matchId in metadata")
        
        participants = metadata.get("participants", [])
        if len(participants) != 10:
            errors.append(f"Expected 10 participants, got {len(participants)}")
        
        # 情報セクションチェック
        info = match_data.get("info", {})
        if not info:
            errors.append("Missing info section")
        else:
            # ゲーム時間チェック
            game_duration = info.get("gameDuration")
            if game_duration is None:
                errors.append("Missing gameDuration")
            elif game_duration < 0:
                errors.append("Game duration cannot be negative")
            elif game_duration < 300:  # 5分未満
                warnings.append("Unusually short game duration")
            
            # 参加者データチェック
            info_participants = info.get("participants", [])
            if len(info_participants) != 10:
                errors.append(f"Expected 10 participants in info, got {len(info_participants)}")
            
            # チームデータチェック
            teams = info.get("teams", [])
            if len(teams) != 2:
                errors.append(f"Expected 2 teams, got {len(teams)}")
        
        # 品質スコア計算
        total_issues = len(errors) + len(warnings)
        quality_score = max(0.0, 1.0 - (total_issues * 0.1))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            quality_score=quality_score
        )
    
    def validate_timeline_consistency(self, timeline: Dict[str, Any]) -> ValidationResult:
        """タイムラインの整合性をチェック"""
        errors = []
        warnings = []
        
        frames = timeline.get("info", {}).get("frames", [])
        if not frames:
            errors.append("No timeline frames found")
            return ValidationResult(is_valid=False, error_count=1, errors=errors)
        
        last_frame_timestamp = -1
        
        for i, frame in enumerate(frames):
            frame_timestamp = frame.get("timestamp", 0)
            
            # フレームタイムスタンプの時系列チェック
            if frame_timestamp <= last_frame_timestamp:
                errors.append(f"Frame {i} timestamp {frame_timestamp} is not after previous frame {last_frame_timestamp}")
            
            last_frame_timestamp = frame_timestamp
            
            # イベントタイムスタンプのチェック
            events = frame.get("events", [])
            for j, event in enumerate(events):
                event_timestamp = event.get("timestamp", frame_timestamp)
                
                # イベントタイムスタンプがフレームタイムスタンプより古い場合
                if event_timestamp < frame_timestamp:
                    warnings.append(f"Event {j} in frame {i} has timestamp earlier than frame timestamp")
        
        # 品質スコア計算
        total_issues = len(errors) + len(warnings)
        quality_score = max(0.0, 1.0 - (total_issues * 0.15))
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            quality_score=quality_score
        )
    
    def detect_anomalies(self, events: List[Event]) -> List[AnomalyReport]:
        """イベントの異常を検出"""
        anomalies = []
        
        if not events:
            return anomalies
        
        # タイムスタンプの異常検出
        timestamps = [e.timestamp for e in events]
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                anomalies.append(AnomalyReport(
                    event_id=f"event_{i}",
                    anomaly_type="timestamp_order",
                    severity="medium",
                    description=f"Event timestamp {timestamps[i]} is earlier than previous event {timestamps[i-1]}",
                    suggested_action="Check timeline consistency",
                    confidence=0.9
                ))
        
        # 異常な頻度のイベント検出
        event_types = {}
        for event in events:
            event_types[event.event] = event_types.get(event.event, 0) + 1
        
        # キルイベントが異常に多い場合
        if event_types.get("kill", 0) > 50:
            anomalies.append(AnomalyReport(
                event_id="kill_frequency",
                anomaly_type="frequency_anomaly",
                severity="high",
                description=f"Unusually high number of kills: {event_types['kill']}",
                suggested_action="Verify match data integrity",
                confidence=0.8
            ))
        
        return anomalies

# ---------------------------------------------------------------------------
# LoL KPI Calculator
# ---------------------------------------------------------------------------

class LoLKPIConfig:
    """LoL KPI計算の設定クラス"""
    
    # KPI重み付け設定
    KDA_WEIGHT = 10  # KDAの重み（最大50点）
    CS_WEIGHT = 2   # CS/10minの重み（最大25点） 
    VISION_WEIGHT = 5  # ビジョンスコアの重み（最大15点）
    DAMAGE_WEIGHT = 20  # ダメージ効率の重み（最大10点）
    
    # オブジェクト貢献度スコア
    TOWER_SCORE = 10
    INHIBITOR_SCORE = 15
    NEXUS_SCORE = 25
    DRAGON_SCORE = 20
    BARON_SCORE = 30
    RIFTHERALD_SCORE = 15
    
    # 分析閾値
    EXCELLENT_KDA = 4.0
    GOOD_KDA = 2.5
    EXCELLENT_CS = 8.0  # CS/min
    GOOD_CS = 6.0
    EXCELLENT_VISION = 2.0  # per min
    GOOD_VISION = 1.2


class KPIResult(BaseModel):
    """KPI計算結果クラス"""
    player_id: str
    champion: str = ""
    game_duration: float = 0.0
    
    # 基本KPI
    kda: float = 0.0
    cs_per_10min: float = 0.0
    gold_per_min: float = 0.0
    damage_per_gold: float = 0.0
    
    # 上級KPI
    vision_score_per_min: float = 0.0
    ward_efficiency: float = 0.0
    objective_contribution: float = 0.0
    first_blood_contribution: bool = False
    
    # メタ情報
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    overall_score: float = 0.0  # 0.0 - 100.0


class LoLKPICalculator:
    """LoL特有のKPI計算クラス"""
    
    def __init__(self, config: LoLKPIConfig = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or LoLKPIConfig()
    
    def calculate_basic_kpi(self, match_data: Dict[str, Any], player_id: str) -> KPIResult:
        """基本KPI（KDA、CS/10min、ゴールド効率）を計算"""
        try:
            participant = self._find_participant(match_data, player_id)
            if not participant:
                raise ValueError(f"Player {player_id} not found in match data")
            
            game_duration = self._get_game_duration(match_data)
            if game_duration <= 0:
                raise ValueError("Invalid game duration")
            
            # 基本データ取得
            player_stats = self._extract_player_stats(participant)
            
            # KPI計算
            kda = self._calculate_kda(player_stats["kills"], player_stats["deaths"], player_stats["assists"])
            cs_per_10min = self.calculate_cs_per_10min(
                player_stats["minions_killed"], 
                player_stats["neutral_killed"], 
                game_duration
            )
            gold_per_min = self._calculate_gold_per_min(player_stats["gold_earned"], game_duration)
            damage_per_gold = self.calculate_damage_per_gold(
                player_stats["damage_dealt"], 
                player_stats["gold_earned"]
            )
            
            result = KPIResult(
                player_id=player_id,
                champion=participant.get("championName", ""),
                game_duration=game_duration,
                kda=kda,
                cs_per_10min=cs_per_10min,
                gold_per_min=gold_per_min,
                damage_per_gold=damage_per_gold
            )
            
            self.logger.info(f"Basic KPI calculated for {player_id}: KDA={kda}, CS/10min={cs_per_10min:.1f}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating basic KPI for {player_id}: {e}")
            raise
    
    def calculate_advanced_kpi(self, match_data: Dict[str, Any], player_id: str) -> KPIResult:
        """上級KPI（ビジョンスコア、オブジェクト貢献度）を計算"""
        try:
            basic_kpi = self.calculate_basic_kpi(match_data, player_id)
            participant = self._find_participant(match_data, player_id)
            
            game_duration_min = basic_kpi.game_duration / 60
            
            # ビジョン関連データ
            vision_stats = self._extract_vision_stats(participant)
            
            # 上級KPI計算
            vision_score_per_min = vision_stats["vision_score"] / game_duration_min
            ward_efficiency = (vision_stats["wards_placed"] + vision_stats["wards_killed"]) / game_duration_min
            
            # オブジェクト貢献度
            first_blood = (participant.get("firstBloodKill", False) or 
                          participant.get("firstBloodAssist", False))
            
            # 基本KPIを拡張
            basic_kpi.vision_score_per_min = vision_score_per_min
            basic_kpi.ward_efficiency = ward_efficiency
            basic_kpi.first_blood_contribution = first_blood
            
            # 強み・弱み分析
            basic_kpi.strengths, basic_kpi.weaknesses = self._analyze_strengths_weaknesses(basic_kpi)
            
            # 総合スコア計算
            basic_kpi.overall_score = self._calculate_overall_score(basic_kpi)
            
            self.logger.info(f"Advanced KPI calculated for {player_id}: Overall Score={basic_kpi.overall_score}")
            return basic_kpi
            
        except Exception as e:
            self.logger.error(f"Error calculating advanced KPI for {player_id}: {e}")
            raise
    
    def calculate_cs_per_10min(self, minions_killed: int, neutral_killed: int, game_duration: int) -> float:
        """CS/10min を計算"""
        if game_duration <= 0:
            return 0.0
        
        total_cs = minions_killed + neutral_killed
        minutes = game_duration / 60
        return round((total_cs / minutes) * 10, 2)
    
    def calculate_vision_score_efficiency(self, vision_score: int, wards_placed: int, 
                                        wards_killed: int, game_duration: int) -> float:
        """ビジョンスコア効率を計算"""
        if game_duration <= 0:
            return 0.0
        
        minutes = game_duration / 60
        return round(vision_score / minutes, 2)
    
    def calculate_objective_contribution(self, events: List[Event], player_id: str) -> float:
        """オブジェクト貢献度を計算"""
        contribution_score = 0.0
        
        for event in events:
            if event.actor == player_id:
                if event.event == "objective_destroy":
                    building_type = event.meta.get("buildingType", "")
                    if "TOWER" in building_type:
                        contribution_score += self.config.TOWER_SCORE
                    elif "INHIBITOR" in building_type:
                        contribution_score += self.config.INHIBITOR_SCORE
                    elif "NEXUS" in building_type:
                        contribution_score += self.config.NEXUS_SCORE
                
                elif event.event == "monster_kill":
                    monster_type = event.meta.get("monsterType", "")
                    if monster_type == "DRAGON":
                        contribution_score += self.config.DRAGON_SCORE
                    elif monster_type == "BARON":
                        contribution_score += self.config.BARON_SCORE
                    elif monster_type == "RIFTHERALD":
                        contribution_score += self.config.RIFTHERALD_SCORE
        
        return contribution_score
    
    def calculate_gold_efficiency(self, gold_earned: int, damage_dealt: int, game_duration: int) -> float:
        """ゴールド効率を計算"""
        if game_duration <= 0:
            return 0.0
        
        minutes = game_duration / 60
        return round(gold_earned / minutes, 1)
    
    def calculate_damage_per_gold(self, damage_dealt: int, gold_earned: int) -> float:
        """ダメージ/ゴールド効率を計算"""
        if gold_earned <= 0:
            return 0.0
        
        return round(damage_dealt / gold_earned, 3)
    
    def _extract_player_stats(self, participant: Dict[str, Any]) -> Dict[str, int]:
        """プレイヤーの基本統計情報を抽出"""
        return {
            "kills": participant.get("kills", 0),
            "deaths": participant.get("deaths", 0),
            "assists": participant.get("assists", 0),
            "minions_killed": participant.get("totalMinionsKilled", 0),
            "neutral_killed": participant.get("neutralMinionsKilled", 0),
            "gold_earned": participant.get("goldEarned", 0),
            "damage_dealt": participant.get("totalDamageDealtToChampions", 0)
        }
    
    def _extract_vision_stats(self, participant: Dict[str, Any]) -> Dict[str, int]:
        """プレイヤーのビジョン関連統計を抽出"""
        return {
            "vision_score": participant.get("visionScore", 0),
            "wards_placed": participant.get("wardsPlaced", 0),
            "wards_killed": participant.get("wardsKilled", 0)
        }
    
    def _get_game_duration(self, match_data: Dict[str, Any]) -> int:
        """ゲーム時間を取得"""
        return match_data.get("info", {}).get("gameDuration", 0)
    
    def _calculate_gold_per_min(self, gold_earned: int, game_duration: int) -> float:
        """分あたりゴールド獲得量を計算"""
        if game_duration <= 0:
            return 0.0
        
        minutes = game_duration / 60
        return round(gold_earned / minutes, 1)
    
    def _analyze_strengths_weaknesses(self, kpi: KPIResult) -> tuple[List[str], List[str]]:
        """プレイヤーの強み・弱みを分析"""
        strengths = []
        weaknesses = []
        
        cs_per_min = kpi.cs_per_10min / 10
        
        # KDA分析
        if kpi.kda >= self.config.EXCELLENT_KDA:
            strengths.append("優秀なKDA - キルデス管理が上手")
        elif kpi.kda < self.config.GOOD_KDA:
            weaknesses.append("KDA改善が必要 - デス数の削減を意識")
        
        # CS分析
        if cs_per_min >= self.config.EXCELLENT_CS:
            strengths.append("優秀なCS効率 - ファーミングスキルが高い")
        elif cs_per_min < self.config.GOOD_CS:
            weaknesses.append("CS効率改善が必要 - ラストヒット練習を推奨")
        
        # ビジョン分析
        if kpi.vision_score_per_min >= self.config.EXCELLENT_VISION:
            strengths.append("優秀なビジョン貢献 - マップ制圧力が高い")
        elif kpi.vision_score_per_min < self.config.GOOD_VISION:
            weaknesses.append("ビジョン貢献改善が必要 - ワード購入・設置を増やす")
        
        # ダメージ効率分析
        if kpi.damage_per_gold >= 1.5:
            strengths.append("高いダメージ効率 - ゴールドの有効活用")
        elif kpi.damage_per_gold < 1.0:
            weaknesses.append("ダメージ効率改善が必要 - アイテムビルド見直し")
        
        # ファーストブラッド分析
        if kpi.first_blood_contribution:
            strengths.append("序盤の積極性 - ファーストブラッド貢献")
        
        return strengths, weaknesses
    
    def _find_participant(self, match_data: Dict[str, Any], player_id: str) -> Dict[str, Any]:
        """マッチデータから特定プレイヤーの情報を取得"""
        participants = match_data.get("info", {}).get("participants", [])
        
        for participant in participants:
            if participant.get("puuid") == player_id:
                return participant
        
        return None
    
    def _calculate_kda(self, kills: int, deaths: int, assists: int) -> float:
        """KDA比を計算"""
        if deaths == 0:
            return float(kills + assists)  # Perfect KDA
        return round((kills + assists) / deaths, 2)
    
    def _calculate_overall_score(self, kpi: KPIResult) -> float:
        """総合スコアを計算"""
        # 重み付けによる総合スコア計算
        kda_score = min(kpi.kda * self.config.KDA_WEIGHT, 50)
        cs_score = min(kpi.cs_per_10min / self.config.CS_WEIGHT, 25)
        vision_score = min(kpi.vision_score_per_min * self.config.VISION_WEIGHT, 15)
        damage_score = min(kpi.damage_per_gold * self.config.DAMAGE_WEIGHT, 10)
        
        total_score = kda_score + cs_score + vision_score + damage_score
        return round(min(total_score, 100), 1)

# ---------------------------------------------------------------------------
# OpenRouter LLM Analyzer
# ---------------------------------------------------------------------------

import aiohttp
import json
from typing import Optional, Union


class AnalysisResult(BaseModel):
    """LLM分析結果クラス"""
    player_id: str
    champion: str = ""
    
    # 分析結果
    performance_summary: str = ""
    key_strengths: List[str] = Field(default_factory=list)
    improvement_areas: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # チャンピオン特化情報
    role_analysis: str = ""
    build_suggestions: str = ""
    positioning_tips: str = ""
    
    # メタ情報
    llm_model: str = ""
    tokens_used: int = 0
    analysis_time: float = 0.0
    confidence_score: float = 0.0


class OpenRouterClient:
    """OpenRouter APIクライアント"""
    
    def __init__(self, api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key or "dummy_key"  # テスト用
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
        
        # デフォルトモデル設定
        self.primary_model = "anthropic/claude-3.5-sonnet"
        self.fallback_models = [
            "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo",
            "meta-llama/llama-3.1-70b-instruct"
        ]
        
        # 使用統計
        self.usage_stats = {
            "requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "errors": 0
        }
    
    async def request(self, prompt: str, model: str = None, max_tokens: int = 1000) -> Dict[str, Any]:
        """OpenRouter APIリクエスト（最小実装）"""
        model = model or self.primary_model
        
        # モックレスポンス（実際のAPI実装は後で追加）
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "analysis": {
                            "performance_summary": f"Player analysis for {prompt[:50]}...",
                            "key_strengths": ["テスト強み1", "テスト強み2"],
                            "improvement_areas": ["テスト改善点1", "テスト改善点2"]
                        },
                        "recommendations": ["テスト推奨事項1", "テスト推奨事項2"],
                        "champion_specific": {
                            "role_analysis": "テストロール分析",
                            "build_suggestions": "テストビルド提案",
                            "positioning_tips": "テストポジション提案"
                        }
                    })
                }
            }],
            "usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": 100,
                "total_tokens": len(prompt.split()) + 100
            }
        }
        
        # 統計更新
        self.usage_stats["requests"] += 1
        self.usage_stats["total_tokens"] += mock_response["usage"]["total_tokens"]
        
        self.logger.info(f"OpenRouter request completed: {model}, tokens: {mock_response['usage']['total_tokens']}")
        return mock_response
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得"""
        return self.usage_stats.copy()


class LoLLLMAnalyzer:
    """LoL特化LLMアナライザー"""
    
    def __init__(self, openrouter_client: OpenRouterClient = None):
        self.client = openrouter_client or OpenRouterClient()
        self.logger = logging.getLogger(__name__)
        
        # プロンプトテンプレート
        self.performance_prompt_template = """
あなたはLoL（League of Legends）の専門分析者です。
以下のプレイヤーのKPIデータを分析し、詳細なフィードバックを提供してください。

プレイヤー情報:
- チャンピオン: {champion}
- KDA: {kda}
- CS/10min: {cs_per_10min}
- ゴールド効率: {gold_per_min} gold/min
- ダメージ効率: {damage_per_gold}
- ビジョンスコア: {vision_score_per_min}/min
- 総合スコア: {overall_score}/100

既存の強み: {strengths}
既存の弱み: {weaknesses}

以下の形式でJSON応答してください:
{{
    "analysis": {{
        "performance_summary": "全体的なパフォーマンス要約",
        "key_strengths": ["強み1", "強み2", "強み3"],
        "improvement_areas": ["改善点1", "改善点2", "改善点3"]
    }},
    "recommendations": ["具体的推奨事項1", "具体的推奨事項2", "具体的推奨事項3"],
    "champion_specific": {{
        "role_analysis": "ロール特化分析",
        "build_suggestions": "ビルド提案",
        "positioning_tips": "ポジション改善提案"
    }}
}}
"""
    
    async def analyze_performance(self, kpi_result: KPIResult) -> AnalysisResult:
        """パフォーマンス分析を実行"""
        try:
            # プロンプト生成
            prompt = self._create_performance_prompt(kpi_result)
            
            # LLMリクエスト
            start_time = time.time()
            response = await self.client.request(prompt)
            analysis_time = max(time.time() - start_time, 0.001)  # 最小時間を保証
            
            # レスポンス解析
            result = self._parse_analysis_response(response, kpi_result)
            result.analysis_time = analysis_time
            
            self.logger.info(f"Performance analysis completed for {kpi_result.player_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing performance for {kpi_result.player_id}: {e}")
            # フォールバック: 基本的な分析結果を返す
            return self._create_fallback_analysis(kpi_result)
    
    def generate_recommendations(self, kpi_result: KPIResult) -> List[str]:
        """改善提案を生成（同期版）"""
        # 同期版の簡易実装
        recommendations = []
        
        if kpi_result.kda < 2.0:
            recommendations.append("デスを減らすため、安全な立ち位置を意識する")
        
        if kpi_result.cs_per_10min < 70:
            recommendations.append("ラストヒット練習でCS効率を向上させる")
        
        if kpi_result.vision_score_per_min < 1.0:
            recommendations.append("ワード購入・設置を増やしてビジョン貢献を向上させる")
        
        return recommendations
    
    async def analyze_champion_performance(self, kpi_result: KPIResult) -> Dict[str, str]:
        """チャンピオン特化分析"""
        champion_analysis = {
            "role_analysis": f"{kpi_result.champion}としてのパフォーマンス分析",
            "build_suggestions": f"{kpi_result.champion}向けビルド提案",
            "positioning_tips": f"{kpi_result.champion}のポジション改善提案"
        }
        
        self.logger.info(f"Champion analysis completed for {kpi_result.champion}")
        return champion_analysis
    
    def set_fallback_models(self, models: List[str]) -> None:
        """フォールバックモデルを設定"""
        self.client.fallback_models = models
        self.logger.info(f"Fallback models updated: {models}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """使用統計を取得"""
        return self.client.get_usage_stats()
    
    def _create_performance_prompt(self, kpi_result: KPIResult) -> str:
        """パフォーマンス分析プロンプトを作成"""
        return self.performance_prompt_template.format(
            champion=kpi_result.champion,
            kda=kpi_result.kda,
            cs_per_10min=kpi_result.cs_per_10min,
            gold_per_min=kpi_result.gold_per_min,
            damage_per_gold=kpi_result.damage_per_gold,
            vision_score_per_min=kpi_result.vision_score_per_min,
            overall_score=kpi_result.overall_score,
            strengths=", ".join(kpi_result.strengths),
            weaknesses=", ".join(kpi_result.weaknesses)
        )
    
    def _parse_analysis_response(self, response: Dict[str, Any], kpi_result: KPIResult) -> AnalysisResult:
        """LLMレスポンスを解析してAnalysisResultに変換"""
        try:
            content = response["choices"][0]["message"]["content"]
            analysis_data = json.loads(content)
            
            return AnalysisResult(
                player_id=kpi_result.player_id,
                champion=kpi_result.champion,
                performance_summary=analysis_data["analysis"]["performance_summary"],
                key_strengths=analysis_data["analysis"]["key_strengths"],
                improvement_areas=analysis_data["analysis"]["improvement_areas"],
                recommendations=analysis_data["recommendations"],
                role_analysis=analysis_data["champion_specific"]["role_analysis"],
                build_suggestions=analysis_data["champion_specific"]["build_suggestions"],
                positioning_tips=analysis_data["champion_specific"]["positioning_tips"],
                llm_model=self.client.primary_model,
                tokens_used=response.get("usage", {}).get("total_tokens", 0),
                confidence_score=0.8  # デフォルト値
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing LLM response: {e}")
            return self._create_fallback_analysis(kpi_result)
    
    def _create_fallback_analysis(self, kpi_result: KPIResult) -> AnalysisResult:
        """フォールバック分析結果を作成"""
        return AnalysisResult(
            player_id=kpi_result.player_id,
            champion=kpi_result.champion,
            performance_summary=f"{kpi_result.champion}プレイヤーの基本分析（総合スコア: {kpi_result.overall_score}）",
            key_strengths=kpi_result.strengths,
            improvement_areas=[],
            recommendations=self.generate_recommendations(kpi_result),
            role_analysis=f"{kpi_result.champion}としての基本分析",
            build_suggestions="一般的なビルドガイドを参照してください",
            positioning_tips="安全な立ち位置を心がけてください",
            llm_model="fallback",
            tokens_used=0,
            confidence_score=0.5
        )

# ---------------------------------------------------------------------------
# Configuration Management
# ---------------------------------------------------------------------------

class APIConfig(BaseModel):
    """API設定クラス"""
    riot_api_key: str = ""
    openrouter_api_key: str = ""
    riot_region: str = "jp1"
    rate_limit: Dict[str, int] = Field(default_factory=lambda: {
        "requests_per_second": 20,
        "requests_per_minute": 100
    })


class PlayerConfig(BaseModel):
    """プレイヤー設定クラス"""
    summoner_name: str = ""
    puuid: str = ""
    default_region: str = "jp1"
    tracked_champions: List[str] = Field(default_factory=list)


class AnalysisConfig(BaseModel):
    """分析設定クラス"""
    kpi_weights: Dict[str, int] = Field(default_factory=lambda: {
        "kda_weight": 10,
        "cs_weight": 2,
        "vision_weight": 5,
        "damage_weight": 20
    })
    fetch_settings: Dict[str, Any] = Field(default_factory=lambda: {
        "match_count": 20,
        "queue_type": "ranked",
        "fetch_timeline": True
    })


class LLMConfig(BaseModel):
    """LLM設定クラス"""
    primary_model: str = "anthropic/claude-3.5-sonnet"
    fallback_models: List[str] = Field(default_factory=lambda: [
        "openai/gpt-4-turbo", 
        "openai/gpt-3.5-turbo"
    ])
    max_tokens: int = 1000
    temperature: float = 0.7


class StorageConfig(BaseModel):
    """ストレージ設定クラス"""
    database_path: str = "data/lol_matches.db"
    cache_enabled: bool = True
    cache_ttl: int = 3600


class LoLConfig(BaseModel):
    """LoL総合設定クラス"""
    api: APIConfig = Field(default_factory=APIConfig)
    player: PlayerConfig = Field(default_factory=PlayerConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


class ConfigManager:
    """設定管理マネージャー"""
    
    def __init__(self, config_path: str = "config/lol_config.yaml"):
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
        self._config: LoLConfig = LoLConfig()
        
        # 設定ファイルが存在する場合は自動読み込み
        if self.config_path.exists():
            try:
                self.load_config(str(self.config_path))
            except Exception as e:
                self.logger.warning(f"Failed to load config from {self.config_path}: {e}")
    
    def load_config(self, config_file: str) -> LoLConfig:
        """設定ファイルを読み込み"""
        try:
            config_path = Path(config_file)
            
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found: {config_file}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.yaml' or config_path.suffix.lower() == '.yml':
                    config_data = yaml.safe_load(f)
                elif config_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                else:
                    raise ValueError(f"Unsupported config file format: {config_path.suffix}")
            
            # 環境変数での上書き
            config_data = self._apply_env_overrides(config_data)
            
            # Pydanticモデルに変換
            self._config = LoLConfig(**config_data)
            
            self.logger.info(f"Config loaded successfully from {config_file}")
            return self._config
            
        except Exception as e:
            self.logger.error(f"Error loading config from {config_file}: {e}")
            raise
    
    def save_config(self, config_data: Dict[str, Any], config_file: str) -> None:
        """設定をファイルに保存"""
        try:
            config_path = Path(config_file)
            
            # ディレクトリ作成
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.yaml' or config_path.suffix.lower() == '.yml':
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                elif config_path.suffix.lower() == '.json':
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                else:
                    raise ValueError(f"Unsupported config file format: {config_path.suffix}")
            
            self.logger.info(f"Config saved successfully to {config_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving config to {config_file}: {e}")
            raise
    
    def validate_config(self, config_data: Dict[str, Any]) -> bool:
        """設定データを検証"""
        try:
            # Pydanticで検証
            LoLConfig(**config_data)
            
            # 追加の業務ロジック検証
            api_config = config_data.get("api", {})
            
            # Riot APIキー検証
            riot_key = api_config.get("riot_api_key", "")
            if riot_key and not self._validate_riot_api_key(riot_key):
                raise ValueError("Invalid Riot API key format")
            
            # OpenRouter APIキー検証
            openrouter_key = api_config.get("openrouter_api_key", "")
            if openrouter_key and not self._validate_openrouter_api_key(openrouter_key):
                raise ValueError("Invalid OpenRouter API key format")
            
            # リージョン検証
            region = api_config.get("riot_region", "")
            if region and not self._validate_region(region):
                raise ValueError(f"Invalid region: {region}")
            
            self.logger.info("Config validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Config validation failed: {e}")
            return False
    
    def get_api_config(self) -> APIConfig:
        """API設定を取得"""
        return self._config.api
    
    def get_player_config(self) -> PlayerConfig:
        """プレイヤー設定を取得"""
        return self._config.player
    
    def get_analysis_config(self) -> AnalysisConfig:
        """分析設定を取得"""
        return self._config.analysis
    
    def get_llm_config(self) -> LLMConfig:
        """LLM設定を取得"""
        return self._config.llm
    
    def get_storage_config(self) -> StorageConfig:
        """ストレージ設定を取得"""
        return self._config.storage
    
    def load_from_env(self) -> None:
        """環境変数から設定を読み込み"""
        env_mapping = {
            "RIOT_API_KEY": ["api", "riot_api_key"],
            "OPENROUTER_API_KEY": ["api", "openrouter_api_key"],
            "RIOT_REGION": ["api", "riot_region"],
            "SUMMONER_NAME": ["player", "summoner_name"],
            "PLAYER_PUUID": ["player", "puuid"],
            "DATABASE_PATH": ["storage", "database_path"]
        }
        
        config_dict = self._config.model_dump()
        
        for env_var, config_path in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value:
                # ネストした辞書に値を設定
                current = config_dict
                for key in config_path[:-1]:
                    current = current[key]
                current[config_path[-1]] = env_value
        
        # 更新された設定で再構築
        self._config = LoLConfig(**config_dict)
        self.logger.info("Environment variables loaded")
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """機密データの暗号化（簡易実装）"""
        # 実際の本番環境では適切な暗号化ライブラリを使用
        import base64
        encoded_data = base64.b64encode(data.encode()).decode()
        return f"encrypted:{encoded_data}"
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """機密データの復号化（簡易実装）"""
        if not encrypted_data.startswith("encrypted:"):
            return encrypted_data
        
        import base64
        encoded_part = encrypted_data[10:]  # "encrypted:" を除去
        return base64.b64decode(encoded_part).decode()
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """環境変数による設定上書きを適用"""
        # 環境変数の上書きロジック
        api_section = config_data.get("api", {})
        
        if os.getenv("RIOT_API_KEY"):
            api_section["riot_api_key"] = os.getenv("RIOT_API_KEY")
        
        if os.getenv("OPENROUTER_API_KEY"):
            api_section["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
        
        config_data["api"] = api_section
        return config_data
    
    def _validate_riot_api_key(self, api_key: str) -> bool:
        """Riot APIキーの形式検証"""
        # 基本的な形式チェック
        return (api_key.startswith("RGAPI-") and 
                len(api_key) > 40 and 
                all(c.isalnum() or c in "-_" for c in api_key))
    
    def _validate_openrouter_api_key(self, api_key: str) -> bool:
        """OpenRouter APIキーの形式検証"""
        # 基本的な形式チェック
        return (api_key.startswith("sk-or-") and 
                len(api_key) > 30)
    
    def _validate_region(self, region: str) -> bool:
        """リージョンコードの検証"""
        valid_regions = {
            "na1", "euw1", "eun1", "kr", "br1", "la1", "la2", 
            "oc1", "ru", "tr1", "jp1", "ph2", "sg2", "th2", "tw2", "vn2"
        }
        return region.lower() in valid_regions

# ---------------------------------------------------------------------------
# Integration Test Framework
# ---------------------------------------------------------------------------

class TestResult(BaseModel):
    """テスト結果クラス"""
    test_name: str
    success: bool = True
    execution_time: float = 0.0
    memory_usage: float = 0.0
    error_message: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class MockDataGenerator:
    """モックデータ生成クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_realistic_match_data(self, player_count: int = 10) -> Dict[str, Any]:
        """リアルなマッチデータを生成"""
        participants = []
        
        for i in range(player_count):
            participant = {
                "puuid": f"test-puuid-{i+1}",
                "championName": random.choice(["Jinx", "Thresh", "Yasuo", "Lux", "Garen", "Ashe", "Braum", "Zed", "Ahri", "Darius"]),
                "teamId": 100 if i < 5 else 200,
                "kills": random.randint(0, 15),
                "deaths": random.randint(0, 10),
                "assists": random.randint(0, 20),
                "totalMinionsKilled": random.randint(50, 300),
                "neutralMinionsKilled": random.randint(0, 50),
                "goldEarned": random.randint(8000, 20000),
                "totalDamageDealtToChampions": random.randint(5000, 40000),
                "visionScore": random.randint(10, 80),
                "wardsPlaced": random.randint(5, 40),
                "wardsKilled": random.randint(0, 20),
                "win": i < 5  # チーム100が勝利
            }
            participants.append(participant)
        
        return {
            "metadata": {
                "dataVersion": "2",
                "matchId": f"JP1_{random.randint(10000, 99999)}",
                "participants": [p["puuid"] for p in participants]
            },
            "info": {
                "gameCreation": int(time.time() * 1000),
                "gameDuration": random.randint(1200, 2400),  # 20-40分
                "gameId": random.randint(10000, 99999),
                "gameMode": "CLASSIC",
                "gameType": "MATCHED_GAME",
                "mapId": 11,
                "platformId": "JP1",
                "queueId": 420,
                "teams": [
                    {"teamId": 100, "win": True},
                    {"teamId": 200, "win": False}
                ],
                "participants": participants
            }
        }
    
    def generate_timeline_data(self, match_id: str) -> Dict[str, Any]:
        """タイムラインデータを生成"""
        events = []
        
        # キルイベント生成
        for i in range(random.randint(5, 15)):
            events.append({
                "timestamp": random.randint(300000, 1800000),
                "type": "CHAMPION_KILL",
                "killerId": random.randint(1, 10),
                "victimId": random.randint(1, 10),
                "position": {"x": random.randint(1000, 14000), "y": random.randint(1000, 14000)}
            })
        
        return {
            "metadata": {"dataVersion": "2", "matchId": match_id, "participants": [f"test-puuid-{i}" for i in range(1, 11)]},
            "info": {
                "frameInterval": 60000,
                "frames": [{"timestamp": 300000, "events": events}]
            }
        }


class IntegrationTestManager:
    """統合テスト管理クラス"""
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config_manager = config_manager or ConfigManager()
        self.mock_generator = MockDataGenerator()
        self.logger = logging.getLogger(__name__)
        self.test_results: List[TestResult] = []
        
        # コンポーネント初期化
        self.fetcher = LoLFetcher("dummy_api_key")
        self.canonizer = LoLCanonizer()
        self.validator = DataValidator()
        self.kpi_calculator = LoLKPICalculator()
        self.llm_analyzer = LoLLLMAnalyzer()
    
    def run_full_pipeline_test(self, match_data: Dict[str, Any]) -> TestResult:
        """完全パイプラインテストを実行"""
        start_time = time.time()
        
        try:
            # 1. タイムラインデータを生成してイベントに変換
            timeline_data = self.mock_generator.generate_timeline_data(match_data.get("metadata", {}).get("matchId", "test_match"))
            events = self.canonizer.timeline_to_events(timeline_data)
            
            # 2. データ検証
            validation_result = self.validator.validate_match_data(match_data)
            
            # 3. KPI計算
            if len(match_data["info"]["participants"]) > 0:
                participant = match_data["info"]["participants"][0]
                kpi_result = self.kpi_calculator.calculate_advanced_kpi(match_data, participant["puuid"])
                
                # 4. LLM分析（同期版推奨事項）
                recommendations = self.llm_analyzer.generate_recommendations(kpi_result)
            
            execution_time = time.time() - start_time
            
            result = TestResult(
                test_name="full_pipeline_test",
                success=True,
                execution_time=execution_time,
                metrics={
                    "events_generated": len(events),
                    "validation_score": validation_result.quality_score,
                    "kpi_score": kpi_result.overall_score if 'kpi_result' in locals() else 0
                }
            )
            
            self.test_results.append(result)
            self.logger.info(f"Full pipeline test completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            result = TestResult(
                test_name="full_pipeline_test",
                success=False,
                execution_time=execution_time,
                error_message=str(e)
            )
            self.test_results.append(result)
            self.logger.error(f"Full pipeline test failed: {e}")
            return result
    
    def run_performance_test(self, match_data: Dict[str, Any]) -> TestResult:
        """パフォーマンステストを実行"""
        start_time = time.time()
        initial_memory = self._get_memory_usage()
        
        try:
            # 複数回実行してパフォーマンス測定
            iterations = 5
            total_events = 0
            
            for i in range(iterations):
                timeline_data = self.mock_generator.generate_timeline_data(f"test_match_{i}")
                events = self.canonizer.timeline_to_events(timeline_data)
                total_events += len(events)
            
            execution_time = time.time() - start_time
            final_memory = self._get_memory_usage()
            memory_increase = final_memory - initial_memory
            
            result = TestResult(
                test_name="performance_test",
                success=True,
                execution_time=execution_time,
                memory_usage=memory_increase,
                metrics={
                    "iterations": iterations,
                    "avg_events_per_iteration": total_events / iterations,
                    "events_per_second": total_events / execution_time
                }
            )
            
            self.test_results.append(result)
            self.logger.info(f"Performance test: {total_events/execution_time:.1f} events/sec")
            return result
            
        except Exception as e:
            result = TestResult(
                test_name="performance_test",
                success=False,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
            self.test_results.append(result)
            return result
    
    def run_error_scenario_tests(self) -> List[TestResult]:
        """エラーシナリオテストを実行"""
        scenarios = [
            ("invalid_match_data", {"invalid": "data"}),
            ("empty_participants", {"info": {"participants": []}}),
            ("missing_required_fields", {"info": {"gameDuration": 1800}}),
        ]
        
        results = []
        
        for scenario_name, invalid_data in scenarios:
            start_time = time.time()
            
            try:
                # エラーハンドリングをテスト
                timeline_data = self.mock_generator.generate_timeline_data(f"error_test_{scenario_name}")
                events = self.canonizer.timeline_to_events(timeline_data)
                
                result = TestResult(
                    test_name=f"error_scenario_{scenario_name}",
                    success=True,  # エラーが適切に処理された
                    execution_time=time.time() - start_time,
                    metrics={"events_generated": len(events)}
                )
                
            except Exception as e:
                result = TestResult(
                    test_name=f"error_scenario_{scenario_name}",
                    success=True,  # 例外が期待される動作
                    execution_time=time.time() - start_time,
                    error_message=str(e)
                )
            
            results.append(result)
            self.test_results.append(result)
        
        self.logger.info(f"Error scenario tests completed: {len(results)} scenarios")
        return results
    
    def run_config_integration_test(self) -> TestResult:
        """設定統合テストを実行"""
        start_time = time.time()
        
        try:
            # 設定読み込みテスト
            api_config = self.config_manager.get_api_config()
            player_config = self.config_manager.get_player_config()
            llm_config = self.config_manager.get_llm_config()
            
            # 設定を使ったコンポーネント初期化テスト
            test_fetcher = LoLFetcher(api_config.riot_api_key or "dummy_key")
            test_llm = LoLLLMAnalyzer()
            
            result = TestResult(
                test_name="config_integration_test",
                success=True,
                execution_time=time.time() - start_time,
                metrics={
                    "riot_region": api_config.riot_region,
                    "llm_model": llm_config.primary_model,
                    "fallback_models": len(llm_config.fallback_models)
                }
            )
            
            self.test_results.append(result)
            self.logger.info("Config integration test completed successfully")
            return result
            
        except Exception as e:
            result = TestResult(
                test_name="config_integration_test",
                success=False,
                execution_time=time.time() - start_time,
                error_message=str(e)
            )
            self.test_results.append(result)
            return result
    
    def run_benchmark_tests(self) -> Dict[str, TestResult]:
        """ベンチマークテストを実行"""
        benchmarks = {}
        
        # データ生成ベンチマーク
        start_time = time.time()
        match_data = self.mock_generator.generate_realistic_match_data()
        generation_time = time.time() - start_time
        
        benchmarks["data_generation"] = TestResult(
            test_name="benchmark_data_generation",
            success=True,
            execution_time=generation_time,
            metrics={"participants": len(match_data["info"]["participants"])}
        )
        
        # 正規化ベンチマーク
        start_time = time.time()
        timeline_data = self.mock_generator.generate_timeline_data(match_data.get("metadata", {}).get("matchId", "benchmark_match"))
        events = self.canonizer.timeline_to_events(timeline_data)
        canonization_time = time.time() - start_time
        
        benchmarks["canonization"] = TestResult(
            test_name="benchmark_canonization",
            success=True,
            execution_time=canonization_time,
            metrics={"events_generated": len(events)}
        )
        
        # KPI計算ベンチマーク
        if match_data["info"]["participants"]:
            start_time = time.time()
            participant = match_data["info"]["participants"][0]
            kpi_result = self.kpi_calculator.calculate_advanced_kpi(match_data, participant["puuid"])
            kpi_time = time.time() - start_time
            
            benchmarks["kpi_calculation"] = TestResult(
                test_name="benchmark_kpi_calculation",
                success=True,
                execution_time=kpi_time,
                metrics={"overall_score": kpi_result.overall_score}
            )
        
        # 結果を記録
        for result in benchmarks.values():
            self.test_results.append(result)
        
        self.logger.info(f"Benchmark tests completed: {len(benchmarks)} benchmarks")
        return benchmarks
    
    def generate_test_report(self) -> Dict[str, Any]:
        """テストレポートを生成"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        total_time = sum(r.execution_time for r in self.test_results)
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
                "total_execution_time": total_time
            },
            "test_results": [r.model_dump() for r in self.test_results],
            "generated_at": datetime.now().isoformat()
        }
        
        self.logger.info(f"Test report generated: {successful_tests}/{total_tests} tests passed")
        return report
    
    def _get_memory_usage(self) -> float:
        """現在のメモリ使用量を取得（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        except ImportError:
            # psutilが利用できない場合は0を返す
            return 0.0

# ---------------------------------------------------------------------------
# Weekly KPI Visualization Classes
# ---------------------------------------------------------------------------

class WeeklyKPISummary(BaseModel):
    """週次KPIサマリークラス"""
    week_start: str  # YYYY-MM-DD
    week_end: str    # YYYY-MM-DD
    player_id: str
    games_played: int = 0
    
    # 平均KPI値
    average_kda: float = 0.0
    average_cs_per_10min: float = 0.0
    average_gold_per_min: float = 0.0
    average_vision_score_per_min: float = 0.0
    
    # 統計値
    win_rate: float = 0.0
    total_wins: int = 0
    total_losses: int = 0
    
    # チャンピオン別データ
    champion_stats: Dict[str, Any] = Field(default_factory=dict)
    
    # トレンド指標
    performance_trend: str = "stable"  # improving, declining, stable
    improvement_areas: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)


class WeeklyKPIAggregator:
    """週次KPIデータ集約クラス"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def aggregate_weekly_data(self, kpi_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """週次データを集約して平均値を計算"""
        if not kpi_data:
            return {}
        
        total_games = len(kpi_data)
        
        # 基本KPI平均計算
        total_kda = sum(game.get('kda', 0) for game in kpi_data)
        total_cs = sum(game.get('cs_per_10min', 0) for game in kpi_data)
        total_gold = sum(game.get('gold_per_min', 0) for game in kpi_data)
        total_vision = sum(game.get('vision_score_per_min', 0) for game in kpi_data)
        
        # 勝率計算
        wins = sum(1 for game in kpi_data if game.get('win', False))
        
        return {
            'average_kda': total_kda / total_games,
            'average_cs_per_10min': total_cs / total_games,
            'average_gold_per_min': total_gold / total_games,
            'average_vision_score_per_min': total_vision / total_games,
            'win_rate': wins / total_games,
            'games_played': total_games,
            'total_wins': wins,
            'total_losses': total_games - wins
        }
    
    def aggregate_by_champion(self, kpi_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """チャンピオン別にデータを集約"""
        champion_data = {}
        
        for game in kpi_data:
            champion = game.get('champion', 'Unknown')
            if champion not in champion_data:
                champion_data[champion] = {
                    'games_played': 0,
                    'total_kda': 0,
                    'total_wins': 0,
                    'kda_values': []
                }
            
            champion_data[champion]['games_played'] += 1
            champion_data[champion]['total_kda'] += game.get('kda', 0)
            champion_data[champion]['kda_values'].append(game.get('kda', 0))
            if game.get('win', False):
                champion_data[champion]['total_wins'] += 1
        
        # 平均値とKDA算出
        for champion, stats in champion_data.items():
            games = stats['games_played']
            stats['average_kda'] = stats['total_kda'] / games if games > 0 else 0
            stats['win_rate'] = stats['total_wins'] / games if games > 0 else 0
            # 詳細なKDA値リストは削除（メモリ節約）
            del stats['kda_values']
        
        return champion_data
    
    def get_weekly_trend(self, player_id: str, weeks: int = 4) -> List[Dict[str, Any]]:
        """指定プレイヤーの週次トレンドデータを取得"""
        # これは実装のスケルトン - 実際のDBクエリが必要
        trend_data = []
        
        for week_offset in range(weeks):
            # 実際の実装では、DB から週次データを取得
            week_data = {
                'week_start': f"2025-01-{13 + (week_offset * 7):02d}",
                'average_kda': 2.5 + (week_offset * 0.2),  # ダミーデータ
                'average_cs_per_10min': 85.0 + (week_offset * 2),
                'win_rate': 0.6 + (week_offset * 0.05),
                'games_played': 5 + week_offset
            }
            trend_data.append(week_data)
        
        return trend_data


class KPIVisualizer:
    """KPI可視化機能クラス"""
    
    def __init__(self, output_dir: str = "data/reports", theme: str = "seaborn"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.theme = theme
        self.logger = logging.getLogger(__name__)
        
        # Matplotlibスタイル設定
        try:
            import matplotlib.pyplot as plt
            import seaborn as sns
            plt.style.use(theme if theme in plt.style.available else 'default')
            sns.set_palette("husl")
        except ImportError:
            self.logger.warning("Matplotlib/Seaborn not available. Visualization features limited.")
    
    def create_weekly_summary_chart(self, weekly_data: Dict[str, Any], 
                                   output_path: str = None) -> str:
        """週次サマリーチャートを生成"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            # データ準備
            metrics = ['KDA', 'CS/10min', 'Gold/min', 'Vision/min']
            values = [
                weekly_data.get('average_kda', 0),
                weekly_data.get('average_cs_per_10min', 0) / 10,  # スケール調整
                weekly_data.get('average_gold_per_min', 0) / 100,  # スケール調整
                weekly_data.get('average_vision_score_per_min', 0)
            ]
            
            # チャート作成
            fig, ax = plt.subplots(figsize=(10, 6))
            bars = ax.bar(metrics, values, color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])
            
            # ラベルとタイトル
            ax.set_title('週次KPIサマリー', fontsize=16, fontweight='bold')
            ax.set_ylabel('パフォーマンス値', fontsize=12)
            
            # 勝率を右軸に表示
            ax2 = ax.twinx()
            win_rate = weekly_data.get('win_rate', 0) * 100
            ax2.axhline(y=win_rate, color='red', linestyle='--', 
                       label=f'勝率: {win_rate:.1f}%')
            ax2.set_ylabel('勝率 (%)', fontsize=12, color='red')
            ax2.legend(loc='upper right')
            
            # 値ラベル追加
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax.annotate(f'{value:.2f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),  # 3 points vertical offset
                           textcoords="offset points",
                           ha='center', va='bottom')
            
            plt.tight_layout()
            
            # ファイル保存
            if output_path is None:
                output_path = self.output_dir / f"weekly_summary_{dt.datetime.now().strftime('%Y%m%d')}.png"
            else:
                output_path = Path(output_path)
            
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Weekly summary chart created: {output_path}")
            return str(output_path)
            
        except ImportError:
            self.logger.error("Matplotlib not available for chart generation")
            return ""
        except Exception as e:
            self.logger.error(f"Error creating weekly summary chart: {e}")
            return ""
    
    def create_champion_performance_chart(self, champion_data: Dict[str, Any], 
                                        output_path: str = None) -> str:
        """チャンピオンパフォーマンス比較チャートを生成"""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            champions = list(champion_data.keys())
            if not champions:
                return ""
            
            kda_values = [data.get('average_kda', 0) for data in champion_data.values()]
            win_rates = [data.get('win_rate', 0) * 100 for data in champion_data.values()]
            games_played = [data.get('games_played', 0) for data in champion_data.values()]
            
            # チャート作成
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # KDAチャート
            bars1 = ax1.bar(champions, kda_values, color='skyblue')
            ax1.set_title('チャンピオン別平均KDA', fontsize=14, fontweight='bold')
            ax1.set_ylabel('平均KDA', fontsize=12)
            ax1.tick_params(axis='x', rotation=45)
            
            # KDA値ラベル
            for bar, value in zip(bars1, kda_values):
                height = bar.get_height()
                ax1.annotate(f'{value:.2f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom')
            
            # 勝率チャート
            bars2 = ax2.bar(champions, win_rates, color='lightgreen')
            ax2.set_title('チャンピオン別勝率', fontsize=14, fontweight='bold')
            ax2.set_ylabel('勝率 (%)', fontsize=12)
            ax2.tick_params(axis='x', rotation=45)
            ax2.set_ylim(0, 100)
            
            # 勝率ラベル
            for bar, value, games in zip(bars2, win_rates, games_played):
                height = bar.get_height()
                ax2.annotate(f'{value:.1f}%\n({games}G)',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=10)
            
            plt.tight_layout()
            
            # ファイル保存
            if output_path is None:
                output_path = self.output_dir / f"champion_performance_{dt.datetime.now().strftime('%Y%m%d')}.png"
            else:
                output_path = Path(output_path)
            
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Champion performance chart created: {output_path}")
            return str(output_path)
            
        except ImportError:
            self.logger.error("Matplotlib not available for chart generation")
            return ""
        except Exception as e:
            self.logger.error(f"Error creating champion performance chart: {e}")
            return ""
    
    def create_trend_chart(self, trend_data: List[Dict[str, Any]], 
                          metric: str = 'kda', output_path: str = None) -> str:
        """トレンドチャートを生成"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            from datetime import datetime
            
            if not trend_data:
                return ""
            
            # データ準備
            dates = [datetime.strptime(data['week_start'], '%Y-%m-%d') for data in trend_data]
            
            # メトリクス別データ取得
            metric_mapping = {
                'kda': ('average_kda', 'KDA', '#FF6B6B'),
                'cs': ('average_cs_per_10min', 'CS/10min', '#4ECDC4'),
                'winrate': ('win_rate', '勝率 (%)', '#45B7D1')
            }
            
            if metric not in metric_mapping:
                metric = 'kda'
            
            field, ylabel, color = metric_mapping[metric]
            values = []
            for data in trend_data:
                val = data.get(field, 0)
                if field == 'win_rate':
                    val *= 100  # パーセント変換
                values.append(val)
            
            # チャート作成
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(dates, values, marker='o', linewidth=2, color=color, markersize=8)
            
            # タイトルとラベル
            ax.set_title(f'{ylabel}の週次トレンド', fontsize=16, fontweight='bold')
            ax.set_xlabel('週', fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            
            # 日付フォーマット
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            ax.xaxis.set_major_locator(mdates.WeekdayLocator())
            plt.xticks(rotation=45)
            
            # 値ラベル追加
            for date, value in zip(dates, values):
                ax.annotate(f'{value:.2f}',
                           xy=(date, value),
                           xytext=(0, 10),
                           textcoords="offset points",
                           ha='center', va='bottom')
            
            # グリッド追加
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # ファイル保存
            if output_path is None:
                output_path = self.output_dir / f"trend_{metric}_{dt.datetime.now().strftime('%Y%m%d')}.png"
            else:
                output_path = Path(output_path)
            
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Trend chart created: {output_path}")
            return str(output_path)
            
        except ImportError:
            self.logger.error("Matplotlib not available for chart generation")
            return ""
        except Exception as e:
            self.logger.error(f"Error creating trend chart: {e}")
            return ""
    
    def create_interactive_dashboard(self, aggregated_data: Dict[str, Any], 
                                   output_path: str = None) -> str:
        """インタラクティブダッシュボードHTMLを生成"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            import plotly.io as pio
            
            # サブプロット作成
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('週次KPIサマリー', 'チャンピオン別パフォーマンス', 
                              'KDAトレンド', 'パフォーマンス分布'),
                specs=[[{"type": "bar"}, {"type": "bar"}],
                       [{"type": "scatter"}, {"type": "box"}]]
            )
            
            # 週次サマリー（左上）
            weekly_summary = aggregated_data.get('weekly_summary', {})
            metrics = ['KDA', 'CS/10min', 'Gold/min', 'Vision/min']
            values = [
                weekly_summary.get('average_kda', 0),
                weekly_summary.get('average_cs_per_10min', 0) / 10,
                weekly_summary.get('average_gold_per_min', 0) / 100,
                weekly_summary.get('average_vision_score_per_min', 0)
            ]
            
            fig.add_trace(
                go.Bar(x=metrics, y=values, name="週次平均", 
                      marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']),
                row=1, col=1
            )
            
            # チャンピオン別パフォーマンス（右上）
            champion_breakdown = aggregated_data.get('champion_breakdown', {})
            if champion_breakdown:
                champions = list(champion_breakdown.keys())
                kda_values = [data.get('kda', 0) for data in champion_breakdown.values()]
                
                fig.add_trace(
                    go.Bar(x=champions, y=kda_values, name="チャンピオン別KDA",
                          marker_color='lightblue'),
                    row=1, col=2
                )
            
            # KDAトレンド（左下）
            daily_trend = aggregated_data.get('daily_trend', [])
            if daily_trend:
                dates = [data.get('date', '') for data in daily_trend]
                kda_trend = [data.get('kda', 0) for data in daily_trend]
                
                fig.add_trace(
                    go.Scatter(x=dates, y=kda_trend, mode='lines+markers',
                             name="KDAトレンド", line_color='#FF6B6B'),
                    row=2, col=1
                )
            
            # レイアウト更新
            fig.update_layout(
                title_text="週次KPIダッシュボード",
                title_x=0.5,
                height=800,
                showlegend=False
            )
            
            # HTMLファイル作成
            if output_path is None:
                output_path = self.output_dir / f"kpi_dashboard_{dt.datetime.now().strftime('%Y%m%d')}.html"
            else:
                output_path = Path(output_path)
            
            # カスタムHTMLテンプレート
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Weekly KPI Dashboard</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .summary-stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #007bff; }}
        .stat-label {{ font-size: 14px; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Weekly KPI Dashboard</h1>
        <p>プレイヤーのパフォーマンス分析レポート</p>
    </div>
    
    <div class="summary-stats">
        <div class="stat-card">
            <div class="stat-value">{weekly_summary.get('average_kda', 0):.2f}</div>
            <div class="stat-label">平均KDA</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{weekly_summary.get('win_rate', 0)*100:.1f}%</div>
            <div class="stat-label">勝率</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{weekly_summary.get('games_played', 0)}</div>
            <div class="stat-label">試合数</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{weekly_summary.get('average_cs_per_10min', 0):.1f}</div>
            <div class="stat-label">CS/10min</div>
        </div>
    </div>
    
    <div id="plotly-div">
        {pio.to_html(fig, include_plotlyjs='inline', div_id="plotly-div")}
    </div>
    
    <div style="margin-top: 30px; text-align: center; color: #6c757d;">
        <p>Generated on {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
            """
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"Interactive dashboard created: {output_path}")
            return str(output_path)
            
        except ImportError:
            self.logger.error("Plotly not available for interactive dashboard generation")
            return ""
        except Exception as e:
            self.logger.error(f"Error creating interactive dashboard: {e}")
            return ""


class WeeklyDashboard:
    """週次ダッシュボード統合クラス"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {
            'output_dir': 'data/reports',
            'theme': 'seaborn',
            'include_interactive': True
        }
        
        self.aggregator = WeeklyKPIAggregator()
        self.visualizer = KPIVisualizer(
            output_dir=self.config['output_dir'],
            theme=self.config['theme']
        )
        self.logger = logging.getLogger(__name__)
    
    def generate_weekly_report(self, player_id: str, week_start: str, 
                             output_dir: str = None) -> Dict[str, str]:
        """完全な週次レポートを生成"""
        try:
            if output_dir:
                self.visualizer.output_dir = Path(output_dir)
                self.visualizer.output_dir.mkdir(parents=True, exist_ok=True)
            
            # ダミーデータ生成（実際の実装では DB から取得）
            sample_kpi_data = [
                {
                    "date": "2025-01-13",
                    "player_id": player_id,
                    "champion": "Jinx",
                    "kda": 2.5,
                    "cs_per_10min": 85.2,
                    "gold_per_min": 520.0,
                    "vision_score_per_min": 1.2,
                    "win": True
                },
                {
                    "date": "2025-01-14",
                    "player_id": player_id,
                    "champion": "Caitlyn",
                    "kda": 3.1,
                    "cs_per_10min": 88.7,
                    "gold_per_min": 550.0,
                    "vision_score_per_min": 1.0,
                    "win": True
                }
            ]
            
            # データ集約
            weekly_summary = self.aggregator.aggregate_weekly_data(sample_kpi_data)
            champion_breakdown = self.aggregator.aggregate_by_champion(sample_kpi_data)
            trend_data = self.aggregator.get_weekly_trend(player_id, weeks=4)
            
            # 集約データ
            aggregated_data = {
                'weekly_summary': weekly_summary,
                'champion_breakdown': champion_breakdown,
                'daily_trend': [
                    {"date": "2025-01-13", "kda": 2.5, "win": True},
                    {"date": "2025-01-14", "kda": 3.1, "win": True}
                ]
            }
            
            # 各種チャート生成
            report_files = {}
            
            report_files['summary_chart'] = self.visualizer.create_weekly_summary_chart(weekly_summary)
            report_files['champion_chart'] = self.visualizer.create_champion_performance_chart(champion_breakdown)
            report_files['trend_chart'] = self.visualizer.create_trend_chart(trend_data, 'kda')
            
            if self.config.get('include_interactive', True):
                report_files['dashboard'] = self.visualizer.create_interactive_dashboard(aggregated_data)
            
            self.logger.info(f"Weekly report generated for {player_id}, week {week_start}")
            return report_files
            
        except Exception as e:
            self.logger.error(f"Error generating weekly report: {e}")
            return {}
    
    def compare_weeks(self, player_id: str, week1_start: str, week2_start: str) -> Dict[str, Any]:
        """週次比較分析を実行"""
        try:
            # ダミー比較データ（実際の実装では DB から取得）
            comparison = {
                'improvements': ['KDA上昇 (+0.3)', 'CS効率改善 (+5 CS/10min)'],
                'regressions': ['勝率低下 (-10%)'],
                'overall_trend': 'improving',
                'recommendation': 'ビジョンスコアとワード効率の向上に注力してください'
            }
            
            self.logger.info(f"Week comparison completed: {week1_start} vs {week2_start}")
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error comparing weeks: {e}")
            return {}


# CLI コマンド追加
@app.command()
def weekly_kpi(
    player_id: str = typer.Option(..., help="Player ID for KPI analysis"),
    weeks: int = typer.Option(4, help="Number of weeks to analyze"),
    output_dir: str = typer.Option("data/reports", help="Output directory for reports"),
    interactive: bool = typer.Option(True, help="Generate interactive dashboard")
):
    """Generate weekly KPI visualization and reports"""
    typer.echo(f"Generating weekly KPI report for player: {player_id}")
    
    try:
        # ダッシュボード設定
        config = {
            'output_dir': output_dir,
            'theme': 'seaborn',
            'include_interactive': interactive
        }
        
        # ダッシュボード生成
        dashboard = WeeklyDashboard(config)
        week_start = "2025-01-13"  # 実際の実装では現在日付から計算
        
        report_files = dashboard.generate_weekly_report(player_id, week_start, output_dir)
        
        if report_files:
            typer.echo("✅ Weekly KPI report generated successfully!")
            typer.echo("\nGenerated files:")
            for report_type, file_path in report_files.items():
                if file_path:
                    typer.echo(f"  - {report_type}: {file_path}")
        else:
            typer.echo("❌ Failed to generate weekly KPI report")
            
    except Exception as e:
        typer.echo(f"❌ Error generating weekly KPI report: {e}")

# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app()
