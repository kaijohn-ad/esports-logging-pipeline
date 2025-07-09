"""
スケジューラーマネージャー

APSchedulerを使用して自動データ収集・分析を管理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from .data_collector import AutoDataCollector, DataCollectionResult
from .trend_analyzer import TrendAnalyzer, TrendAnalysisResult
from .notification_manager import NotificationManager
from ..config.lol_config import LoLConfig


class SchedulerJobResult:
    """スケジューラージョブ結果クラス"""
    
    def __init__(self, job_id: str, job_type: str):
        self.job_id = job_id
        self.job_type = job_type
        self.success = True
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.result_data: Optional[Dict[str, Any]] = None
        
    def complete(self, result_data: Dict[str, Any] = None):
        """ジョブ完了を記録"""
        self.end_time = datetime.now()
        self.result_data = result_data or {}
        
    def fail(self, error_message: str):
        """ジョブ失敗を記録"""
        self.success = False
        self.error_message = error_message
        self.end_time = datetime.now()
        
    def get_duration(self) -> timedelta:
        """実行時間を取得"""
        end_time = self.end_time or datetime.now()
        return end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "success": self.success,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.get_duration().total_seconds(),
            "error_message": self.error_message,
            "result_data": self.result_data
        }


class SchedulerManager:
    """スケジューラーマネージャークラス"""
    
    def __init__(self, config: LoLConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # コンポーネントの初期化
        self.data_collector = AutoDataCollector(config)
        self.trend_analyzer = TrendAnalyzer(config)
        self.notification_manager = NotificationManager(config)
        
        # スケジューラー設定
        self.scheduler = AsyncIOScheduler(
            jobstores={'default': MemoryJobStore()},
            executors={'default': AsyncIOExecutor()},
            job_defaults={'coalesce': False, 'max_instances': 1}
        )
        
        # ジョブ結果履歴
        self.job_history: List[SchedulerJobResult] = []
        self.max_history_size = 100
        
        # 実行中のジョブ
        self.running_jobs: Dict[str, SchedulerJobResult] = {}
        
        # スケジューラーイベントリスナー設定
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
    
    def start(self):
        """スケジューラーを開始"""
        if not self.config.scheduler.enabled:
            self.logger.info("スケジューラーは無効化されています")
            return
        
        try:
            # 既存ジョブをクリア
            self.scheduler.remove_all_jobs()
            
            # データ収集ジョブを追加
            self._add_data_collection_job()
            
            # トレンド分析ジョブを追加
            self._add_trend_analysis_job()
            
            # データクリーンアップジョブを追加
            self._add_cleanup_job()
            
            # スケジューラー開始
            self.scheduler.start()
            
            self.logger.info("スケジューラーが開始されました")
            self.logger.info(f"追跡プレイヤー数: {len(self.config.scheduler.tracked_players)}")
            
            # 起動通知
            self._send_startup_notification()
            
        except Exception as e:
            self.logger.error(f"スケジューラー開始エラー: {e}")
            raise
    
    def stop(self):
        """スケジューラーを停止"""
        try:
            self.scheduler.shutdown(wait=False)
            self.logger.info("スケジューラーが停止されました")
        except Exception as e:
            self.logger.error(f"スケジューラー停止エラー: {e}")
    
    def _add_data_collection_job(self):
        """データ収集ジョブを追加"""
        # カスタムCron表現がある場合
        if self.config.scheduler.data_collection_cron:
            trigger = CronTrigger.from_crontab(self.config.scheduler.data_collection_cron)
        else:
            # 事前定義された間隔
            interval = self.config.scheduler.data_collection_interval
            trigger = self._create_interval_trigger(interval)
        
        self.scheduler.add_job(
            self._run_data_collection,
            trigger=trigger,
            id="data_collection",
            name="プレイヤーデータ収集",
            replace_existing=True,
            max_instances=1
        )
        
        self.logger.info(f"データ収集ジョブ追加: {self.config.scheduler.data_collection_interval}")
    
    def _add_trend_analysis_job(self):
        """トレンド分析ジョブを追加"""
        if not self.config.scheduler.trend_analysis_enabled:
            return
        
        # カスタムCron表現がある場合
        if self.config.scheduler.analysis_cron:
            trigger = CronTrigger.from_crontab(self.config.scheduler.analysis_cron)
        else:
            # 事前定義された間隔
            interval = self.config.scheduler.analysis_interval
            trigger = self._create_interval_trigger(interval)
        
        self.scheduler.add_job(
            self._run_trend_analysis,
            trigger=trigger,
            id="trend_analysis",
            name="トレンド分析",
            replace_existing=True,
            max_instances=1
        )
        
        self.logger.info(f"トレンド分析ジョブ追加: {self.config.scheduler.analysis_interval}")
    
    def _add_cleanup_job(self):
        """データクリーンアップジョブを追加"""
        # 毎日深夜2時にクリーンアップ実行
        self.scheduler.add_job(
            self._run_cleanup,
            trigger=CronTrigger(hour=2, minute=0),
            id="data_cleanup",
            name="データクリーンアップ",
            replace_existing=True,
            max_instances=1
        )
        
        self.logger.info("データクリーンアップジョブ追加: 毎日02:00")
    
    def _create_interval_trigger(self, interval: str) -> IntervalTrigger:
        """間隔文字列からトリガーを作成"""
        if interval == "daily":
            return IntervalTrigger(days=1)
        elif interval == "weekly":
            return IntervalTrigger(weeks=1)
        elif interval == "monthly":
            return IntervalTrigger(days=30)
        else:
            self.logger.warning(f"不明な間隔: {interval}, dailyに設定")
            return IntervalTrigger(days=1)
    
    async def _run_data_collection(self):
        """データ収集ジョブを実行"""
        job_result = SchedulerJobResult("data_collection", "データ収集")
        self.running_jobs["data_collection"] = job_result
        
        try:
            self.logger.info("データ収集ジョブを開始")
            
            # データ収集実行
            collection_result = await self.data_collector.collect_all_players_data()
            
            # 結果を記録
            job_result.complete(collection_result.to_dict())
            
            # 通知送信
            if self.config.scheduler.notifications_enabled:
                notification_result = self.notification_manager.notify_data_collection_complete(collection_result)
                job_result.result_data["notification_result"] = notification_result.to_dict()
            
            self.logger.info(f"データ収集ジョブ完了: {collection_result.players_processed}名処理, "
                           f"{collection_result.collected_matches}マッチ収集")
            
        except Exception as e:
            error_msg = f"データ収集ジョブエラー: {str(e)}"
            self.logger.error(error_msg)
            job_result.fail(error_msg)
            
            # エラー通知
            if self.config.scheduler.notifications_enabled:
                self.notification_manager.notify_scheduler_error(
                    error_msg, "data_collection", str(e)
                )
        
        finally:
            self.running_jobs.pop("data_collection", None)
            self._add_job_to_history(job_result)
    
    async def _run_trend_analysis(self):
        """トレンド分析ジョブを実行"""
        job_result = SchedulerJobResult("trend_analysis", "トレンド分析")
        self.running_jobs["trend_analysis"] = job_result
        
        try:
            self.logger.info("トレンド分析ジョブを開始")
            
            # トレンド分析実行
            trend_results = self.trend_analyzer.analyze_all_players(
                weeks=self.config.scheduler.trend_analysis_weeks
            )
            
            # サマリー作成
            summary = self.trend_analyzer.get_summary_report(trend_results)
            
            # 結果を記録
            job_result.complete({
                "trend_results": [r.to_dict() for r in trend_results],
                "summary": summary
            })
            
            # 通知送信
            if self.config.scheduler.notifications_enabled:
                notification_result = self.notification_manager.notify_trend_analysis_complete(
                    trend_results, summary
                )
                job_result.result_data["notification_result"] = notification_result.to_dict()
            
            self.logger.info(f"トレンド分析ジョブ完了: {len(trend_results)}名分析")
            
        except Exception as e:
            error_msg = f"トレンド分析ジョブエラー: {str(e)}"
            self.logger.error(error_msg)
            job_result.fail(error_msg)
            
            # エラー通知
            if self.config.scheduler.notifications_enabled:
                self.notification_manager.notify_scheduler_error(
                    error_msg, "trend_analysis", str(e)
                )
        
        finally:
            self.running_jobs.pop("trend_analysis", None)
            self._add_job_to_history(job_result)
    
    async def _run_cleanup(self):
        """データクリーンアップジョブを実行"""
        job_result = SchedulerJobResult("data_cleanup", "データクリーンアップ")
        self.running_jobs["data_cleanup"] = job_result
        
        try:
            self.logger.info("データクリーンアップジョブを開始")
            
            # データクリーンアップ実行
            self.data_collector.cleanup_old_data()
            
            # ジョブ履歴もクリーンアップ
            self._cleanup_job_history()
            
            job_result.complete({"message": "データクリーンアップ完了"})
            
            self.logger.info("データクリーンアップジョブ完了")
            
        except Exception as e:
            error_msg = f"データクリーンアップジョブエラー: {str(e)}"
            self.logger.error(error_msg)
            job_result.fail(error_msg)
            
            # エラー通知
            if self.config.scheduler.notifications_enabled:
                self.notification_manager.notify_scheduler_error(
                    error_msg, "data_cleanup", str(e)
                )
        
        finally:
            self.running_jobs.pop("data_cleanup", None)
            self._add_job_to_history(job_result)
    
    def _add_job_to_history(self, job_result: SchedulerJobResult):
        """ジョブ結果を履歴に追加"""
        self.job_history.append(job_result)
        
        # 履歴サイズ制限
        if len(self.job_history) > self.max_history_size:
            self.job_history = self.job_history[-self.max_history_size:]
    
    def _cleanup_job_history(self):
        """古いジョブ履歴をクリーンアップ"""
        cutoff_date = datetime.now() - timedelta(days=30)
        self.job_history = [
            job for job in self.job_history 
            if job.start_time > cutoff_date
        ]
    
    def _job_executed_listener(self, event):
        """ジョブ実行イベントリスナー"""
        if event.exception:
            self.logger.error(f"ジョブ実行エラー [{event.job_id}]: {event.exception}")
        else:
            self.logger.debug(f"ジョブ実行完了 [{event.job_id}]")
    
    def _send_startup_notification(self):
        """起動通知を送信"""
        if not self.config.scheduler.notifications_enabled:
            return
        
        try:
            message = f"スケジューラーが開始されました - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.notification_manager.notify_scheduler_error(
                message, "scheduler_startup", "システム起動"
            )
        except Exception as e:
            self.logger.error(f"起動通知送信エラー: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """スケジューラーのステータスを取得"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        
        return {
            "scheduler_running": self.scheduler.running,
            "enabled": self.config.scheduler.enabled,
            "jobs": jobs,
            "running_jobs": list(self.running_jobs.keys()),
            "tracked_players": len(self.config.scheduler.tracked_players),
            "job_history_count": len(self.job_history),
            "last_collection_stats": self.data_collector.get_collection_stats()
        }
    
    def get_job_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """ジョブ履歴を取得"""
        return [job.to_dict() for job in self.job_history[-limit:]]
    
    async def run_job_manually(self, job_id: str) -> Dict[str, Any]:
        """ジョブを手動実行"""
        if job_id not in ["data_collection", "trend_analysis", "data_cleanup"]:
            raise ValueError(f"不明なジョブID: {job_id}")
        
        if job_id in self.running_jobs:
            return {"success": False, "message": f"ジョブ {job_id} は既に実行中です"}
        
        try:
            self.logger.info(f"ジョブ {job_id} を手動実行開始")
            
            if job_id == "data_collection":
                await self._run_data_collection()
            elif job_id == "trend_analysis":
                await self._run_trend_analysis()
            elif job_id == "data_cleanup":
                await self._run_cleanup()
            
            return {"success": True, "message": f"ジョブ {job_id} が正常に完了しました"}
            
        except Exception as e:
            error_msg = f"ジョブ {job_id} の手動実行エラー: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "message": error_msg}
    
    def update_player_config(self, players: List[Dict[str, str]]):
        """追跡プレイヤー設定を更新"""
        self.config.scheduler.tracked_players = players
        self.logger.info(f"追跡プレイヤー設定更新: {len(players)}名")
    
    def save_job_history(self, filepath: str = None):
        """ジョブ履歴をファイルに保存"""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"data/reports/job_history_{timestamp}.json"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        history_data = {
            "export_time": datetime.now().isoformat(),
            "total_jobs": len(self.job_history),
            "job_history": [job.to_dict() for job in self.job_history]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"ジョブ履歴保存: {filepath}")
        return filepath
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """パフォーマンスメトリクスを取得"""
        if not self.job_history:
            return {"message": "ジョブ履歴がありません"}
        
        # 成功率計算
        successful_jobs = sum(1 for job in self.job_history if job.success)
        success_rate = successful_jobs / len(self.job_history) * 100
        
        # 平均実行時間計算
        completed_jobs = [job for job in self.job_history if job.end_time]
        avg_duration = sum(job.get_duration().total_seconds() for job in completed_jobs) / len(completed_jobs) if completed_jobs else 0
        
        # ジョブ種別ごとの統計
        job_stats = {}
        for job in self.job_history:
            if job.job_type not in job_stats:
                job_stats[job.job_type] = {"total": 0, "success": 0, "avg_duration": 0}
            
            job_stats[job.job_type]["total"] += 1
            if job.success:
                job_stats[job.job_type]["success"] += 1
            
            if job.end_time:
                job_stats[job.job_type]["avg_duration"] += job.get_duration().total_seconds()
        
        # 平均実行時間を計算
        for stats in job_stats.values():
            if stats["total"] > 0:
                stats["avg_duration"] = stats["avg_duration"] / stats["total"]
                stats["success_rate"] = stats["success"] / stats["total"] * 100
        
        return {
            "total_jobs": len(self.job_history),
            "success_rate": success_rate,
            "average_duration_seconds": avg_duration,
            "job_type_stats": job_stats,
            "last_30_days_jobs": len([job for job in self.job_history if job.start_time > datetime.now() - timedelta(days=30)])
        }