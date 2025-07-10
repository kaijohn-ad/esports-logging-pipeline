"""
Task 7: Automatic Scheduling for Player Data Collection and Analysis
スケジューラー機能のテストファイル
"""

import asyncio
import pytest
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from src.scheduler.scheduler_manager import SchedulerManager, SchedulerJobResult
from src.scheduler.data_collector import AutoDataCollector, DataCollectionResult
from src.scheduler.trend_analyzer import TrendAnalyzer, TrendAnalysisResult
from src.scheduler.notification_manager import NotificationManager, NotificationResult
from src.config.lol_config import LoLConfig


class TestSchedulerManager:
    """スケジューラーマネージャーのテストクラス"""
    
    @pytest.fixture
    def mock_config(self):
        """テスト用設定を作成"""
        config = LoLConfig()
        config.scheduler.enabled = True
        config.scheduler.data_collection_interval = "daily"
        config.scheduler.analysis_interval = "weekly"
        config.scheduler.tracked_players = [
            {"name": "TestPlayer1", "puuid": "test-puuid-1"},
            {"name": "TestPlayer2", "puuid": "test-puuid-2"}
        ]
        config.scheduler.notifications_enabled = True
        config.scheduler.notification_channels = ["console", "file"]
        return config
    
    @pytest.fixture
    def scheduler_manager(self, mock_config):
        """スケジューラーマネージャーを作成"""
        return SchedulerManager(mock_config)
    
    def test_scheduler_initialization(self, scheduler_manager):
        """スケジューラーの初期化テスト"""
        assert scheduler_manager.config.scheduler.enabled
        assert len(scheduler_manager.config.scheduler.tracked_players) == 2
        assert scheduler_manager.scheduler is not None
        assert scheduler_manager.data_collector is not None
        assert scheduler_manager.trend_analyzer is not None
        assert scheduler_manager.notification_manager is not None
    
    def test_scheduler_status_disabled(self):
        """スケジューラー無効時のステータステスト"""
        config = LoLConfig()
        config.scheduler.enabled = False
        
        scheduler_manager = SchedulerManager(config)
        status = scheduler_manager.get_status()
        
        assert not status["enabled"]
        assert not status["scheduler_running"]
        assert status["tracked_players"] == 0
    
    def test_scheduler_job_result(self):
        """スケジューラージョブ結果クラスのテスト"""
        job_result = SchedulerJobResult("test_job", "テストジョブ")
        
        assert job_result.job_id == "test_job"
        assert job_result.job_type == "テストジョブ"
        assert job_result.success
        assert job_result.end_time is None
        
        # 完了テスト
        test_data = {"test": "data"}
        job_result.complete(test_data)
        
        assert job_result.end_time is not None
        assert job_result.result_data == test_data
        
        # 失敗テスト
        job_result.fail("テストエラー")
        
        assert not job_result.success
        assert job_result.error_message == "テストエラー"
    
    @pytest.mark.asyncio
    async def test_manual_job_execution(self, scheduler_manager):
        """手動ジョブ実行のテスト"""
        with patch.object(scheduler_manager.data_collector, 'collect_all_players_data') as mock_collect:
            # モックの設定
            mock_result = DataCollectionResult()
            mock_result.players_processed = 2
            mock_result.collected_matches = 10
            mock_result.collected_events = 100
            mock_collect.return_value = mock_result
            
            # 手動実行
            result = await scheduler_manager.run_job_manually("data_collection")
            
            assert result["success"]
            assert "正常に完了" in result["message"]
            mock_collect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_invalid_job_id(self, scheduler_manager):
        """無効なジョブIDのテスト"""
        with pytest.raises(ValueError, match="不明なジョブID"):
            await scheduler_manager.run_job_manually("invalid_job")
    
    def test_player_config_update(self, scheduler_manager):
        """プレイヤー設定更新のテスト"""
        new_players = [{"name": "NewPlayer", "puuid": "new-puuid"}]
        
        scheduler_manager.update_player_config(new_players)
        
        assert len(scheduler_manager.config.scheduler.tracked_players) == 1
        assert scheduler_manager.config.scheduler.tracked_players[0]["name"] == "NewPlayer"
    
    def test_job_history_management(self, scheduler_manager):
        """ジョブ履歴管理のテスト"""
        # 複数のジョブ結果を追加
        for i in range(5):
            job_result = SchedulerJobResult(f"job_{i}", f"テストジョブ{i}")
            job_result.complete({"test": i})
            scheduler_manager._add_job_to_history(job_result)
        
        history = scheduler_manager.get_job_history()
        assert len(history) == 5
        
        # 最新のジョブが最後に来ることを確認
        assert history[-1]["job_id"] == "job_4"
    
    def test_performance_metrics(self, scheduler_manager):
        """パフォーマンスメトリクスのテスト"""
        # 成功ジョブ
        success_job = SchedulerJobResult("success_job", "成功ジョブ")
        success_job.complete({"result": "success"})
        scheduler_manager._add_job_to_history(success_job)
        
        # 失敗ジョブ
        failed_job = SchedulerJobResult("failed_job", "失敗ジョブ")
        failed_job.fail("テストエラー")
        scheduler_manager._add_job_to_history(failed_job)
        
        metrics = scheduler_manager.get_performance_metrics()
        
        assert metrics["total_jobs"] == 2
        assert metrics["success_rate"] == 50.0
        assert "成功ジョブ" in metrics["job_type_stats"]
        assert "失敗ジョブ" in metrics["job_type_stats"]


class TestDataCollector:
    """データ収集クラスのテストクラス"""
    
    @pytest.fixture
    def temp_db_path(self):
        """テスト用一時DBパスを作成"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def mock_config(self):
        """テスト用設定を作成"""
        config = LoLConfig()
        config.api.riot_api_key = "test_key"
        config.scheduler.tracked_players = [
            {"name": "TestPlayer", "puuid": "test-puuid"}
        ]
        return config
    
    @pytest.fixture
    def data_collector(self, mock_config, temp_db_path):
        """データ収集クラスを作成"""
        return AutoDataCollector(mock_config, temp_db_path)
    
    def test_data_collector_initialization(self, data_collector):
        """データ収集クラスの初期化テスト"""
        assert data_collector.config is not None
        assert data_collector.fetcher is not None
        assert data_collector.canonizer is not None
        assert data_collector.db_path.exists()
    
    def test_data_collection_result(self):
        """データ収集結果クラスのテスト"""
        result = DataCollectionResult()
        
        assert result.success
        assert result.collected_matches == 0
        assert result.collected_events == 0
        assert len(result.errors) == 0
        
        # エラー追加テスト
        result.add_error("テストエラー")
        
        assert not result.success
        assert len(result.errors) == 1
        assert result.errors[0] == "テストエラー"
        
        # 完了テスト
        result.complete()
        
        assert result.end_time is not None
        duration = result.get_duration()
        assert isinstance(duration, timedelta)
    
    def test_match_already_processed(self, data_collector):
        """既存マッチ処理済みチェックのテスト"""
        # 存在しないマッチ
        assert not data_collector._is_match_already_processed("non_existent_match")
        
        # TODO: 実際のデータベースエントリーでのテストを追加
    
    def test_collection_stats(self, data_collector):
        """収集統計情報のテスト"""
        stats = data_collector.get_collection_stats()
        
        assert "total_matches" in stats
        assert "total_events" in stats
        assert "event_counts" in stats
        assert "tracked_players" in stats
        
        # 初期状態では0
        assert stats["total_matches"] == 0
        assert stats["total_events"] == 0


class TestTrendAnalyzer:
    """トレンド分析クラスのテストクラス"""
    
    @pytest.fixture
    def temp_db_path(self):
        """テスト用一時DBパスを作成"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # クリーンアップ
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def mock_config(self):
        """テスト用設定を作成"""
        config = LoLConfig()
        config.scheduler.tracked_players = [
            {"name": "TestPlayer", "puuid": "test-puuid"}
        ]
        return config
    
    @pytest.fixture
    def trend_analyzer(self, mock_config, temp_db_path):
        """トレンド分析クラスを作成"""
        return TrendAnalyzer(mock_config, temp_db_path)
    
    def test_trend_analyzer_initialization(self, trend_analyzer):
        """トレンド分析クラスの初期化テスト"""
        assert trend_analyzer.config is not None
        assert trend_analyzer.kpi_calculator is not None
        assert trend_analyzer.TREND_THRESHOLD == 0.1
        assert trend_analyzer.STABLE_THRESHOLD == 0.05
    
    def test_trend_analysis_result(self):
        """トレンド分析結果クラスのテスト"""
        result = TrendAnalysisResult(
            player_id="test-puuid",
            player_name="TestPlayer",
            analysis_period="Past 4 weeks",
            trend_data=[]
        )
        
        assert result.player_id == "test-puuid"
        assert result.player_name == "TestPlayer"
        assert result.overall_trend == "stable"
        assert result.performance_score == 0.0
        assert isinstance(result.improving_metrics, list)
        assert isinstance(result.declining_metrics, list)
        
        # 辞書変換テスト
        result_dict = result.to_dict()
        assert "player_id" in result_dict
        assert "trend_data" in result_dict
        assert "overall_trend" in result_dict
    
    def test_analyze_all_players_empty(self, trend_analyzer):
        """プレイヤー分析（空データ）のテスト"""
        results = trend_analyzer.analyze_all_players()
        
        # データが空の場合、各プレイヤーの結果は空になる
        assert len(results) == 1  # 1人のプレイヤーが設定されている
        assert results[0].player_name == "TestPlayer"
        assert len(results[0].trend_data) == 0
    
    def test_summary_report_empty(self, trend_analyzer):
        """サマリーレポート（空データ）のテスト"""
        summary = trend_analyzer.get_summary_report([])
        
        assert summary["total_players"] == 0
        assert summary["improving_players"] == 0
        assert summary["declining_players"] == 0
        assert summary["stable_players"] == 0
        assert summary["average_performance_score"] == 0.0
        assert len(summary["top_performers"]) == 0
        assert len(summary["needs_attention"]) == 0


class TestNotificationManager:
    """通知管理クラスのテストクラス"""
    
    @pytest.fixture
    def mock_config(self):
        """テスト用設定を作成"""
        config = LoLConfig()
        config.scheduler.notification_channels = ["console", "file"]
        return config
    
    @pytest.fixture
    def notification_manager(self, mock_config):
        """通知管理クラスを作成"""
        return NotificationManager(mock_config)
    
    def test_notification_manager_initialization(self, notification_manager):
        """通知管理クラスの初期化テスト"""
        assert notification_manager.config is not None
        assert notification_manager.reports_dir.exists()
        assert "data_collection" in notification_manager.templates
        assert "trend_analysis" in notification_manager.templates
        assert "scheduler_error" in notification_manager.templates
    
    def test_notification_result(self):
        """通知結果クラスのテスト"""
        result = NotificationResult()
        
        assert result.success
        assert len(result.messages) == 0
        assert len(result.channels_used) == 0
        assert len(result.errors) == 0
        
        # 成功メッセージ追加
        result.add_success("console", "コンソール通知成功")
        
        assert "console" in result.channels_used
        assert len(result.messages) == 1
        
        # エラーメッセージ追加
        result.add_error("email", "メール送信失敗")
        
        assert not result.success
        assert len(result.errors) == 1
    
    def test_console_notification(self, notification_manager):
        """コンソール通知のテスト"""
        test_data = {
            "date": "2025-01-21 10:00",
            "duration": "0:01:30",
            "players_processed": 2,
            "collected_matches": 10,
            "collected_events": 100,
            "error_count": 0,
            "details": "テスト通知"
        }
        
        # コンソール通知は例外が発生しないことを確認
        try:
            notification_manager._notify_console(test_data, "data_collection")
        except Exception as e:
            pytest.fail(f"コンソール通知でエラー: {e}")
    
    def test_file_notification(self, notification_manager):
        """ファイル通知のテスト"""
        test_data = {
            "date": "2025-01-21 10:00",
            "duration": "0:01:30",
            "players_processed": 2,
            "collected_matches": 10,
            "collected_events": 100,
            "error_count": 0,
            "details": "テスト通知"
        }
        
        # ファイル通知実行
        notification_manager._notify_file(test_data, "data_collection")
        
        # ファイルが作成されたことを確認
        reports_dir = notification_manager.reports_dir
        report_files = list(reports_dir.glob("data_collection_*.txt"))
        assert len(report_files) >= 1
        
        # ファイル内容確認
        with open(report_files[0], 'r', encoding='utf-8') as f:
            content = f.read()
            assert "データ収集が完了しました" in content
            assert "テスト通知" in content
    
    def test_format_collection_details(self, notification_manager):
        """収集詳細フォーマットのテスト"""
        # 成功ケース
        result = DataCollectionResult()
        result.success = True
        result.players_failed = 0
        
        details = notification_manager._format_collection_details(result)
        assert "✅ 収集処理が正常に完了しました" in details
        
        # エラーケース
        result.success = False
        result.players_failed = 1
        result.add_error("テストエラー")
        
        details = notification_manager._format_collection_details(result)
        assert "❌ 収集処理中にエラーが発生しました" in details
        assert "⚠️ 1名のプレイヤーで処理に失敗しました" in details
        assert "テストエラー" in details
    
    def test_test_notifications(self, notification_manager):
        """通知テスト機能のテスト"""
        result = notification_manager.test_notifications()
        
        # consoleとfileチャンネルが設定されているのでテスト成功
        assert result.success
        assert len(result.channels_used) == 2
        assert "console" in result.channels_used
        assert "file" in result.channels_used


@pytest.mark.integration
class TestSchedulerIntegration:
    """スケジューラー統合テストクラス"""
    
    @pytest.fixture
    def integration_config(self):
        """統合テスト用設定"""
        config = LoLConfig()
        config.scheduler.enabled = True
        config.scheduler.tracked_players = [
            {"name": "TestPlayer", "puuid": "test-puuid"}
        ]
        config.scheduler.notifications_enabled = True
        config.scheduler.notification_channels = ["console", "file"]
        return config
    
    @pytest.mark.skipif(not os.getenv("INTEGRATION_TEST"), reason="Integration test disabled")
    def test_full_scheduler_workflow(self, integration_config):
        """完全なスケジューラーワークフローのテスト"""
        scheduler_manager = SchedulerManager(integration_config)
        
        # スケジューラーが正常に初期化されることを確認
        assert scheduler_manager.config.scheduler.enabled
        assert len(scheduler_manager.config.scheduler.tracked_players) == 1
        
        # ステータス確認
        status = scheduler_manager.get_status()
        assert status["enabled"]
        assert status["tracked_players"] == 1
        
        # 通知テスト
        notification_result = scheduler_manager.notification_manager.test_notifications()
        assert notification_result.success
        
        # パフォーマンスメトリクスの初期状態
        metrics = scheduler_manager.get_performance_metrics()
        assert "message" in metrics  # 履歴がない場合


if __name__ == "__main__":
    pytest.main([__file__, "-v"])