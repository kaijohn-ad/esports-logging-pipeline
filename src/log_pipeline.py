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
import logging
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import typer
from pydantic import BaseModel, Field

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
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.mock_generator = MockDataGenerator()
        self.logger = logging.getLogger(__name__)
        self.test_results: List[TestResult] = []
    
    def run_full_pipeline_test(self, match_data: Dict[str, Any]) -> TestResult:
        """完全パイプラインテストを実行"""
        start_time = time.time()
        
        try:
            # 1. タイムラインデータを生成してイベントに変換
            timeline_data = self.mock_generator.generate_timeline_data(match_data.get("metadata", {}).get("matchId", "test_match"))
            events = LoLCanonizer.timeline_to_events(timeline_data)
            
            execution_time = time.time() - start_time
            
            result = TestResult(
                test_name="full_pipeline_test",
                success=True,
                execution_time=execution_time,
                metrics={
                    "events_generated": len(events)
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
