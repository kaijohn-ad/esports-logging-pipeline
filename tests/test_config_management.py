"""設定管理機能のテスト

APIキー、プレイヤー設定、分析設定などを
安全かつ柔軟に管理する機能をテストします。
"""

import pytest
import os
import tempfile
import yaml
import json
from pathlib import Path
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLFetcher


class TestConfigManagement:
    """設定管理機能のテストクラス"""
    
    @pytest.fixture
    def sample_config_data(self):
        """サンプル設定データ"""
        return {
            "api": {
                "riot_api_key": "RGAPI-test-key-12345",
                "openrouter_api_key": "sk-or-test-key-67890",
                "riot_region": "jp1",
                "rate_limit": {
                    "requests_per_second": 20,
                    "requests_per_minute": 100
                }
            },
            "player": {
                "summoner_name": "TestSummoner",
                "puuid": "test-puuid-12345",
                "default_region": "jp1",
                "tracked_champions": ["Jinx", "Caitlyn", "Ashe"]
            },
            "analysis": {
                "kpi_weights": {
                    "kda_weight": 10,
                    "cs_weight": 2,
                    "vision_weight": 5,
                    "damage_weight": 20
                },
                "fetch_settings": {
                    "match_count": 20,
                    "queue_type": "ranked",
                    "fetch_timeline": True
                }
            },
            "llm": {
                "primary_model": "anthropic/claude-3.5-sonnet",
                "fallback_models": ["openai/gpt-4-turbo", "openai/gpt-3.5-turbo"],
                "max_tokens": 1000,
                "temperature": 0.7
            },
            "storage": {
                "database_path": "data/lol_matches.db",
                "cache_enabled": True,
                "cache_ttl": 3600
            }
        }
    
    @pytest.fixture
    def temp_config_file(self, sample_config_data):
        """一時的な設定ファイル"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config_data, f)
            temp_path = f.name
        
        yield temp_path
        
        # クリーンアップ
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def config_manager(self):
        """ConfigManagerのインスタンス"""
        from log_pipeline import ConfigManager
        # 存在しないパスで初期化してデフォルト設定を使用
        return ConfigManager("non_existent_config.yaml")
    
    def test_config_manager_creation(self, config_manager):
        """ConfigManagerクラスの作成テスト"""
        assert config_manager is not None
        assert hasattr(config_manager, '_config')
        assert hasattr(config_manager, 'logger')
    
    def test_lol_config_creation(self):
        """LoLConfigクラスの作成テスト"""
        from log_pipeline import LoLConfig
        
        config = LoLConfig()
        assert config.api.riot_region == "jp1"
        assert config.llm.primary_model == "anthropic/claude-3.5-sonnet"
        assert config.storage.cache_enabled is True
    
    def test_api_config_creation(self):
        """APIConfigクラスの作成テスト"""
        from log_pipeline import APIConfig
        
        api_config = APIConfig(
            riot_api_key="RGAPI-test-key",
            riot_region="na1"
        )
        assert api_config.riot_api_key == "RGAPI-test-key"
        assert api_config.riot_region == "na1"
        assert api_config.rate_limit["requests_per_second"] == 20
    
    def test_load_config(self, config_manager, temp_config_file):
        """設定ファイル読み込み機能のテスト"""
        config = config_manager.load_config(temp_config_file)
        
        assert config.api.riot_api_key == "RGAPI-test-key-12345"
        assert config.player.summoner_name == "TestSummoner"
        assert config.analysis.kpi_weights["kda_weight"] == 10
        assert config.llm.primary_model == "anthropic/claude-3.5-sonnet"
    
    def test_save_config(self, config_manager, sample_config_data):
        """設定ファイル保存機能のテスト"""
        with tempfile.NamedTemporaryFile(suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            config_manager.save_config(sample_config_data, temp_path)
            
            # 保存されたファイルを確認
            assert os.path.exists(temp_path)
            
            # 内容を確認
            with open(temp_path, 'r') as f:
                loaded_data = yaml.safe_load(f)
            
            assert loaded_data["api"]["riot_api_key"] == "RGAPI-test-key-12345"
            assert loaded_data["player"]["summoner_name"] == "TestSummoner"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_validate_config_valid(self, config_manager, sample_config_data):
        """有効な設定データの検証テスト"""
        # テスト用に有効なAPIキーを設定
        sample_config_data["api"]["riot_api_key"] = "RGAPI-" + "a" * 40
        sample_config_data["api"]["openrouter_api_key"] = "sk-or-" + "b" * 30
        
        is_valid = config_manager.validate_config(sample_config_data)
        assert is_valid is True
    
    def test_validate_config_invalid_riot_key(self, config_manager, sample_config_data):
        """無効なRiot APIキーの検証テスト"""
        sample_config_data["api"]["riot_api_key"] = "invalid-key"
        
        is_valid = config_manager.validate_config(sample_config_data)
        assert is_valid is False
    
    def test_validate_config_invalid_region(self, config_manager, sample_config_data):
        """無効なリージョンの検証テスト"""
        sample_config_data["api"]["riot_region"] = "invalid_region"
        
        is_valid = config_manager.validate_config(sample_config_data)
        assert is_valid is False
    
    def test_get_api_config(self, config_manager):
        """API設定取得機能のテスト"""
        api_config = config_manager.get_api_config()
        
        assert hasattr(api_config, 'riot_api_key')
        assert hasattr(api_config, 'openrouter_api_key')
        assert hasattr(api_config, 'riot_region')
        assert api_config.riot_region == "jp1"  # デフォルト値
    
    def test_get_player_config(self, config_manager):
        """プレイヤー設定取得機能のテスト"""
        player_config = config_manager.get_player_config()
        
        assert hasattr(player_config, 'summoner_name')
        assert hasattr(player_config, 'puuid')
        assert hasattr(player_config, 'tracked_champions')
        assert player_config.default_region == "jp1"
    
    def test_environment_variables(self, config_manager):
        """環境変数サポートのテスト"""
        # 環境変数をモック
        with patch.dict(os.environ, {
            'RIOT_API_KEY': 'RGAPI-env-test-key',
            'SUMMONER_NAME': 'EnvTestSummoner'
        }):
            config_manager.load_from_env()
            
            api_config = config_manager.get_api_config()
            player_config = config_manager.get_player_config()
            
            assert api_config.riot_api_key == 'RGAPI-env-test-key'
            assert player_config.summoner_name == 'EnvTestSummoner'
    
    def test_config_encryption(self, config_manager):
        """設定暗号化機能のテスト"""
        test_data = "sensitive_api_key_12345"
        
        # 暗号化
        encrypted = config_manager.encrypt_sensitive_data(test_data)
        assert encrypted.startswith("encrypted:")
        assert encrypted != test_data
        
        # 復号化
        decrypted = config_manager.decrypt_sensitive_data(encrypted)
        assert decrypted == test_data
    
    def test_config_file_not_found(self, config_manager):
        """存在しない設定ファイルのエラーテスト"""
        with pytest.raises(FileNotFoundError):
            config_manager.load_config("non_existent_file.yaml")


class TestConfigValidation:
    """設定検証機能のテスト"""
    
    def test_riot_api_key_validation_future(self):
        """Riot APIキー検証の具体的テスト（将来実装予定）"""
        # 実装後に以下のような検証をテストする予定
        # - APIキー形式の妥当性（RGAPI-で始まる等）
        # - APIキーの長さ検証
        # - 無効なAPIキーの検出
        pytest.skip("ConfigManager implementation pending")
    
    def test_openrouter_api_key_validation_future(self):
        """OpenRouter APIキー検証の具体的テスト（将来実装予定）"""
        # 実装後に以下のような検証をテストする予定
        # - APIキー形式の妥当性（sk-or-で始まる等）
        # - APIキーの長さ検証
        # - 無効なAPIキーの検出
        pytest.skip("ConfigManager implementation pending")
    
    def test_summoner_name_validation_future(self):
        """サマナー名検証の具体的テスト（将来実装予定）"""
        # 実装後に以下のような検証をテストする予定
        # - サマナー名の長さ制限
        # - 使用可能文字の検証
        # - 重複チェック
        pytest.skip("ConfigManager implementation pending")
    
    def test_region_validation_future(self):
        """リージョン検証の具体的テスト（将来実装予定）"""
        # 実装後に以下のような検証をテストする予定
        # - 有効なリージョンコードのチェック
        # - 大文字小文字の正規化
        # - 廃止されたリージョンの検出
        pytest.skip("ConfigManager implementation pending")


class TestConfigIntegration:
    """設定統合機能のテスト"""
    
    def test_fetcher_config_integration_future(self):
        """Fetcher設定統合の具体的テスト（将来実装予定）"""
        # 実装後に以下のような統合をテストする予定
        # - LoLFetcherへの設定自動適用
        # - APIキーの自動設定
        # - レート制限設定の適用
        pytest.skip("ConfigManager implementation pending")
    
    def test_kpi_calculator_config_integration_future(self):
        """KPI計算機設定統合の具体的テスト（将来実装予定）"""
        # 実装後に以下のような統合をテストする予定
        # - KPI重み付け設定の適用
        # - 分析閾値の自動設定
        # - カスタム設定の反映
        pytest.skip("ConfigManager implementation pending")
    
    def test_llm_analyzer_config_integration_future(self):
        """LLMアナライザー設定統合の具体的テスト（将来実装予定）"""
        # 実装後に以下のような統合をテストする予定
        # - OpenRouter設定の自動適用
        # - モデル設定の反映
        # - フォールバック設定の適用
        pytest.skip("ConfigManager implementation pending")
    
    def test_config_hot_reload_future(self):
        """設定ホットリロードの具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - 設定ファイル変更の検出
        # - 動的な設定反映
        # - 設定変更の通知機能
        pytest.skip("ConfigManager implementation pending")
    
    def test_config_backup_restore_future(self):
        """設定バックアップ・復元の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - 自動バックアップ作成
        # - 設定復元機能
        # - バージョン管理
        pytest.skip("ConfigManager implementation pending") 