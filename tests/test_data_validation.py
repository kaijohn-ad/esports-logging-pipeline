"""データ検証機能のテスト

マッチデータの完全性、タイムラインの整合性、異常データ検出機能をテストします。
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, Any, List

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLFetcher, Event, DataValidator, ValidationResult, AnomalyReport


class TestDataValidation:
    """データ検証機能のテストクラス"""
    
    @pytest.fixture
    def validator(self):
        """テスト用のDataValidatorインスタンス"""
        return DataValidator()
    
    @pytest.fixture
    def sample_valid_match_data(self):
        """有効なマッチデータのサンプル"""
        return {
            "metadata": {
                "matchId": "JP1_123456789",
                "participants": ["puuid1", "puuid2", "puuid3", "puuid4", "puuid5",
                               "puuid6", "puuid7", "puuid8", "puuid9", "puuid10"]
            },
            "info": {
                "gameCreation": 1640995200000,
                "gameDuration": 1800,
                "gameMode": "CLASSIC",
                "participants": [
                    {"puuid": "puuid1", "summonerName": "Player1", "championName": "Jinx"},
                    {"puuid": "puuid2", "summonerName": "Player2", "championName": "Caitlyn"},
                    {"puuid": "puuid3", "summonerName": "Player3", "championName": "Leona"},
                    {"puuid": "puuid4", "summonerName": "Player4", "championName": "Thresh"},
                    {"puuid": "puuid5", "summonerName": "Player5", "championName": "Graves"},
                    {"puuid": "puuid6", "summonerName": "Player6", "championName": "Yasuo"},
                    {"puuid": "puuid7", "summonerName": "Player7", "championName": "Zed"},
                    {"puuid": "puuid8", "summonerName": "Player8", "championName": "Alistar"},
                    {"puuid": "puuid9", "summonerName": "Player9", "championName": "Braum"},
                    {"puuid": "puuid10", "summonerName": "Player10", "championName": "Kindred"}
                ],
                "teams": [
                    {
                        "teamId": 100,
                        "win": True
                    },
                    {
                        "teamId": 200,
                        "win": False
                    }
                ]
            }
        }
    
    @pytest.fixture
    def sample_invalid_match_data(self):
        """無効なマッチデータのサンプル"""
        return {
            "metadata": {
                "matchId": "INVALID_ID",
                "participants": ["puuid1"]  # 不正: 10人未満
            },
            "info": {
                "gameCreation": None,  # 不正: Null値
                "gameDuration": -100,  # 不正: 負の値
                "gameMode": "UNKNOWN",
                "participants": [],  # 不正: 空リスト
                "teams": []  # 不正: 空リスト
            }
        }
    
    @pytest.fixture
    def sample_timeline_data(self):
        """タイムラインデータのサンプル"""
        return {
            "info": {
                "frames": [
                    {
                        "timestamp": 60000,
                        "events": [
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 65000,
                                "killerId": 1,
                                "victimId": 6
                            }
                        ]
                    },
                    {
                        "timestamp": 120000,
                        "events": [
                            {
                                "type": "CHAMPION_KILL", 
                                "timestamp": 50000,  # 不正: 前のフレームより古いタイムスタンプ
                                "killerId": 2,
                                "victimId": 7
                            }
                        ]
                    }
                ]
            }
        }
    
    def test_data_validator_class_exists(self, validator):
        """DataValidatorクラスが実装されていることのテスト"""
        assert isinstance(validator, DataValidator)
        assert hasattr(validator, 'validate_match_completeness')
        assert hasattr(validator, 'validate_timeline_consistency')
        assert hasattr(validator, 'detect_anomalies')
    
    def test_validation_result_class_exists(self):
        """ValidationResultクラスが実装されていることのテスト"""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.quality_score == 1.0
    
    def test_anomaly_report_class_exists(self):
        """AnomalyReportクラスが実装されていることのテスト"""
        report = AnomalyReport(
            event_id="test",
            anomaly_type="test_type",
            severity="low",
            description="Test description"
        )
        assert report.event_id == "test"
        assert report.anomaly_type == "test_type"
        assert report.severity == "low"
    
    def test_validate_valid_match_data(self, validator, sample_valid_match_data):
        """有効なマッチデータの検証テスト"""
        result = validator.validate_match_completeness(sample_valid_match_data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.quality_score > 0.5
    
    def test_validate_invalid_match_data(self, validator, sample_invalid_match_data):
        """無効なマッチデータの検証テスト"""
        result = validator.validate_match_completeness(sample_invalid_match_data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert result.error_count > 0
        assert len(result.errors) > 0
        assert result.quality_score < 1.0
    
    def test_validate_timeline_consistency(self, validator, sample_timeline_data):
        """タイムライン整合性検証テスト"""
        result = validator.validate_timeline_consistency(sample_timeline_data)
        
        assert isinstance(result, ValidationResult)
        # サンプルデータには整合性の問題があるので、警告が出るはず
        assert result.warning_count > 0 or result.error_count > 0
    
    def test_detect_anomalies_empty_events(self, validator):
        """空のイベントリストの異常検出テスト"""
        anomalies = validator.detect_anomalies([])
        
        assert isinstance(anomalies, list)
        assert len(anomalies) == 0
    
    def test_detect_anomalies_timestamp_order(self, validator):
        """タイムスタンプ順序異常の検出テスト"""
        events = [
            Event(timestamp=100.0, event="kill", actor="1", target="2"),
            Event(timestamp=50.0, event="kill", actor="3", target="4")  # 時系列逆転
        ]
        
        anomalies = validator.detect_anomalies(events)
        
        assert len(anomalies) > 0
        assert any(a.anomaly_type == "timestamp_order" for a in anomalies)
    
    def test_detect_anomalies_high_kill_frequency(self, validator):
        """異常なキル頻度の検出テスト"""
        # 51個のキルイベントを作成（異常として検出されるべき）
        events = [
            Event(timestamp=float(i), event="kill", actor="1", target="2")
            for i in range(51)
        ]
        
        anomalies = validator.detect_anomalies(events)
        
        assert len(anomalies) > 0
        assert any(a.anomaly_type == "frequency_anomaly" for a in anomalies)
        assert any("kills" in a.description for a in anomalies)


class TestDataValidationEdgeCases:
    """データ検証のエッジケーステスト"""
    
    @pytest.fixture
    def validator(self):
        """テスト用のDataValidatorインスタンス"""
        return DataValidator()
    
    def test_validate_match_data_not_dict(self, validator):
        """辞書以外のマッチデータ検証テスト"""
        result = validator.validate_match_completeness("not a dict")
        
        assert result.is_valid is False
        assert "must be a dictionary" in result.errors[0]
    
    def test_validate_match_data_missing_sections(self, validator):
        """セクション欠落のマッチデータ検証テスト"""
        incomplete_data = {"metadata": {}}
        result = validator.validate_match_completeness(incomplete_data)
        
        assert result.is_valid is False
        assert result.error_count > 0
    
    def test_validate_timeline_no_frames(self, validator):
        """フレームなしのタイムライン検証テスト"""
        timeline_data = {"info": {"frames": []}}
        result = validator.validate_timeline_consistency(timeline_data)
        
        assert result.is_valid is False
        assert "No timeline frames found" in result.errors
    
    def test_quality_score_calculation(self, validator):
        """品質スコア計算のテスト"""
        # 多くのエラーがあるデータ
        bad_data = {
            "metadata": {},  # matchId missing
            "info": {
                "gameDuration": -1,  # negative duration
                "participants": [],  # wrong count
                "teams": []  # wrong count
            }
        }
        
        result = validator.validate_match_completeness(bad_data)
        
        assert result.quality_score <= 0.5  # 品質スコアが0.5以下であることを確認
        assert result.error_count >= 4  # 複数のエラーがあることを確認 