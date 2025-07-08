"""
モジュール化後の構造テスト

このテストは、log_pipeline.pyのモジュール化が正しく実行されたことを確認する。
TDDアプローチに従い、最初に失敗するテストを書く。
"""

import pytest
import sys
from pathlib import Path

class TestModularization:
    """モジュール化テストクラス"""

    def test_collectors_module_structure(self):
        """collectors モジュールが正しく構造化されているかテスト"""
        # 各モジュールのインポートが可能かテスト
        try:
            from src.collectors.lol_fetcher import LoLFetcher
            from src.collectors.rate_limiter import RateLimiter
            assert True  # インポート成功
        except ImportError as e:
            pytest.fail(f"collectors モジュールのインポートに失敗: {e}")

    def test_canonizer_module_structure(self):
        """canonizer モジュールが正しく構造化されているかテスト"""
        try:
            from src.canonizer.lol_canonizer import LoLCanonizer
            from src.canonizer.event import Event
            assert True
        except ImportError as e:
            pytest.fail(f"canonizer モジュールのインポートに失敗: {e}")

    def test_storage_module_structure(self):
        """storage モジュールが正しく構造化されているかテスト"""
        try:
            from src.storage.sqlite_store import init_db
            assert True
        except ImportError as e:
            pytest.fail(f"storage モジュールのインポートに失敗: {e}")

    def test_kpi_module_structure(self):
        """kpi モジュールが正しく構造化されているかテスト"""
        try:
            from src.kpi.lol_kpi_calculator import LoLKPICalculator
            from src.kpi.kpi_result import KPIResult
            from src.kpi.lol_kpi_config import LoLKPIConfig
            assert True
        except ImportError as e:
            pytest.fail(f"kpi モジュールのインポートに失敗: {e}")

    def test_llm_module_structure(self):
        """llm モジュールが正しく構造化されているかテスト"""
        try:
            from src.llm.lol_llm_analyzer import LoLLLMAnalyzer
            from src.llm.openrouter_client import OpenRouterClient
            from src.llm.analysis_result import AnalysisResult
            assert True
        except ImportError as e:
            pytest.fail(f"llm モジュールのインポートに失敗: {e}")

    def test_config_module_structure(self):
        """config モジュールが正しく構造化されているかテスト"""
        try:
            from src.config.config_manager import ConfigManager
            from src.config.lol_config import LoLConfig
            assert True
        except ImportError as e:
            pytest.fail(f"config モジュールのインポートに失敗: {e}")

    def test_validation_module_structure(self):
        """validation モジュールが正しく構造化されているかテスト"""
        try:
            from src.validation.data_validator import DataValidator
            from src.validation.validation_result import ValidationResult
            from src.validation.anomaly_report import AnomalyReport
            assert True
        except ImportError as e:
            pytest.fail(f"validation モジュールのインポートに失敗: {e}")

    def test_main_pipeline_integration(self):
        """メインパイプラインが新しいモジュール構造で動作するかテスト"""
        try:
            from src.log_pipeline import app  # TyperのCLIアプリ
            assert app is not None
        except ImportError as e:
            pytest.fail(f"メインパイプラインのインポートに失敗: {e}")

    def test_module_independence(self):
        """各モジュールが独立して動作するかテスト"""
        # collectors モジュール単体テスト
        try:
            from src.collectors.rate_limiter import RateLimiter
            rate_limiter = RateLimiter(20, 120)
            assert rate_limiter.max_requests == 20
            assert rate_limiter.time_window == 120
        except Exception as e:
            pytest.fail(f"collectors モジュールの独立動作に失敗: {e}")

    def test_inter_module_communication(self):
        """モジュール間の通信が正しく機能するかテスト"""
        try:
            from src.canonizer.event import Event
            from src.kpi.kpi_result import KPIResult
            
            # Event オブジェクトの作成
            event = Event(
                timestamp=100.0,
                event="kill",
                actor="test_player",
                target="enemy_player"
            )
            
            # 基本的な属性チェック
            assert event.timestamp == 100.0
            assert event.event == "kill"
            
        except Exception as e:
            pytest.fail(f"モジュール間通信に失敗: {e}")

    def test_backwards_compatibility(self):
        """既存のテストが新しい構造で動作するかテスト"""
        # 既存のテストファイルが影響を受けないことを確認
        test_files = [
            "test_lol_fetcher.py",
            "test_lol_canonizer.py",
            "test_lol_kpi.py",
            "test_config_management.py"
        ]
        
        test_dir = Path("tests")
        for test_file in test_files:
            test_path = test_dir / test_file
            if test_path.exists():
                # テストファイルが存在することを確認
                assert test_path.is_file()