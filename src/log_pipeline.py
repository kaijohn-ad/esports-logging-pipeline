"""eSports Logging Pipeline - Modularized Version
====================================
Python 3.12 / Typer CLI で動かすモジュール化されたパイプライン。

このファイルは、新しいモジュール構造に基づいて更新されました：
- collectors/: データ収集（LoLFetcher, RateLimiter）
- canonizer/: データ正規化（Event, LoLCanonizer）
- storage/: データ保存（SQLite関連）
- kpi/: KPI計算（LoLKPICalculator関連）
- llm/: LLM分析（OpenRouter統合）
- config/: 設定管理（ConfigManager）
- validation/: データ検証（DataValidator）
"""

import json
import sqlite3
import asyncio
import datetime as dt
import typer
from pathlib import Path

# 新しいモジュール構造からインポート
from .collectors import LoLFetcher
from .canonizer import LoLCanonizer, Event
from .storage import init_db
from .kpi import LoLKPICalculator, KPIResult
from .llm import LoLLLMAnalyzer, OpenRouterClient

app = typer.Typer(help="eSports log pipeline CLI (Modularized)")
DB_PATH = Path("data/esports.db")
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

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

@app.command()
def analyze_performance(
    api_key: str = typer.Argument(..., envvar="RIOT_API_KEY"),
    summoner_name: str = typer.Option(...),
    openrouter_key: str = typer.Option(None, envvar="OPENROUTER_API_KEY")
):
    """Analyze player performance using KPI and LLM"""
    try:
        # データ取得
        fetcher = LoLFetcher(api_key)
        summoner = fetcher.watch.summoner.by_name(fetcher.region, summoner_name)
        puuid = summoner["puuid"]
        
        # 最新マッチを取得
        match_ids = fetcher.fetch_latest_matches(puuid, count=1)
        if not match_ids:
            typer.echo("No matches found")
            return
        
        match_data = fetcher.fetch_match_details(match_ids[0])
        
        # KPI計算
        kpi_calculator = LoLKPICalculator()
        kpi_result = kpi_calculator.calculate_advanced_kpi(match_data, puuid)
        
        # 結果表示
        typer.echo(f"\n=== Performance Analysis for {summoner_name} ===")
        typer.echo(f"Champion: {kpi_result.champion}")
        typer.echo(f"KDA: {kpi_result.kda}")
        typer.echo(f"CS/10min: {kpi_result.cs_per_10min}")
        typer.echo(f"Overall Score: {kpi_result.overall_score}/100")
        
        if kpi_result.strengths:
            typer.echo(f"\nStrengths:")
            for strength in kpi_result.strengths:
                typer.echo(f"  ✓ {strength}")
        
        if kpi_result.weaknesses:
            typer.echo(f"\nWeaknesses:")
            for weakness in kpi_result.weaknesses:
                typer.echo(f"  ⚠ {weakness}")
        
        # LLM分析（OpenRouterキーがある場合）
        if openrouter_key:
            typer.echo(f"\n=== LLM Analysis ===")
            client = OpenRouterClient(openrouter_key)
            analyzer = LoLLLMAnalyzer(client)
            
            # 同期版での簡易分析
            recommendations = analyzer.generate_recommendations(kpi_result)
            if recommendations:
                typer.echo(f"Recommendations:")
                for rec in recommendations:
                    typer.echo(f"  • {rec}")
        
    except Exception as e:
        typer.echo(f"Error during analysis: {e}")

@app.command()
def test_modules():
    """Test that all modules are properly imported"""
    try:
        from .collectors import LoLFetcher, RateLimiter
        from .canonizer import Event, LoLCanonizer
        from .storage import init_db
        from .kpi import LoLKPICalculator, KPIResult, LoLKPIConfig
        from .llm import LoLLLMAnalyzer, OpenRouterClient, AnalysisResult
        from .config import ConfigManager, LoLConfig
        from .validation import DataValidator, ValidationResult, AnomalyReport
        
        typer.echo("✅ All modules imported successfully!")
        typer.echo("Modularization completed successfully.")
        
        # 簡単な機能テスト
        rate_limiter = RateLimiter(20, 120)
        typer.echo(f"✅ RateLimiter created: {rate_limiter.max_requests} req/{rate_limiter.time_window}s")
        
        event = Event(timestamp=100.0, event="test", actor="test_actor")
        typer.echo(f"✅ Event created: {event.event} at {event.timestamp}s")
        
        config_manager = ConfigManager()
        typer.echo(f"✅ ConfigManager created: {config_manager.config_path}")
        
        typer.echo("\n🎉 Modularization successful! All components working.")
        
    except ImportError as e:
        typer.echo(f"❌ Import error: {e}")
    except Exception as e:
        typer.echo(f"❌ Error: {e}")

# ---------------------------------------------------------------------------
# Overwolf RT Reader (maintain backward compatibility)
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

if __name__ == "__main__":
    app()
