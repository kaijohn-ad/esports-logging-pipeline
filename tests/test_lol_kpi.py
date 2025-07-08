"""LoL特有KPI計算機能のテスト

CS/10min、ビジョンスコア、オブジェクト貢献度など、
LoLに特化したKPI計算機能をテストします。
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, Any, List

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLFetcher, Event


class TestLoLKPICalculator:
    """LoL KPI計算機能のテストクラス"""
    
    @pytest.fixture
    def sample_match_data_with_kpi(self):
        """KPI計算用のサンプルマッチデータ"""
        return {
            "info": {
                "gameDuration": 1800,  # 30分
                "participants": [
                    {
                        "puuid": "player1",
                        "championName": "Jinx",
                        "teamId": 100,
                        "kills": 12,
                        "deaths": 4,
                        "assists": 8,
                        "totalMinionsKilled": 250,
                        "neutralMinionsKilled": 30,
                        "goldEarned": 18000,
                        "totalDamageDealtToChampions": 35000,
                        "visionScore": 45,
                        "wardsPlaced": 15,
                        "wardsKilled": 8,
                        "firstBloodKill": True,
                        "firstTowerKill": True,
                        "turretKills": 3,
                        "inhibitorKills": 1,
                        "dragonKills": 2,
                        "baronKills": 1
                    },
                    {
                        "puuid": "player2", 
                        "championName": "Thresh",
                        "teamId": 100,
                        "kills": 2,
                        "deaths": 6,
                        "assists": 18,
                        "totalMinionsKilled": 45,
                        "neutralMinionsKilled": 5,
                        "goldEarned": 12000,
                        "totalDamageDealtToChampions": 8000,
                        "visionScore": 85,
                        "wardsPlaced": 35,
                        "wardsKilled": 15,
                        "firstBloodAssist": True
                    }
                ]
            }
        }
    
    @pytest.fixture
    def sample_events_for_kpi(self):
        """KPI計算用のサンプルイベントデータ"""
        return [
            Event(timestamp=300.0, event="kill", actor="player1", target="enemy1", meta={"position": {"x": 5000, "y": 5000}}),
            Event(timestamp=600.0, event="ward_place", actor="player1", target=None, meta={"wardType": "YELLOW_TRINKET"}),
            Event(timestamp=900.0, event="objective_destroy", actor="player1", target=None, meta={"buildingType": "TOWER_TURRET"}),
            Event(timestamp=1200.0, event="monster_kill", actor="player1", target=None, meta={"monsterType": "DRAGON"}),
            Event(timestamp=1500.0, event="ward_destroy", actor="player1", target=None, meta={"wardType": "YELLOW_TRINKET"}),
        ]
    
    @pytest.fixture
    def kpi_calculator(self):
        """KPI計算機のインスタンス"""
        from log_pipeline import LoLKPICalculator
        return LoLKPICalculator()
    
    def test_lol_kpi_calculator_creation(self, kpi_calculator):
        """LoLKPICalculatorクラスの作成テスト"""
        assert kpi_calculator is not None
        assert hasattr(kpi_calculator, 'logger')
    
    def test_calculate_basic_kpi_player1(self, kpi_calculator, sample_match_data_with_kpi):
        """基本KPI計算テスト - プレイヤー1（ADC）"""
        result = kpi_calculator.calculate_basic_kpi(sample_match_data_with_kpi, "player1")
        
        assert result.player_id == "player1"
        assert result.champion == "Jinx"
        assert result.game_duration == 1800
        
        # KDA: (12 + 8) / 4 = 5.0
        assert result.kda == 5.0
        
        # CS/10min: (250 + 30) / (1800/600) = 280/3 = 93.33
        assert abs(result.cs_per_10min - 93.33) < 0.1
        
        # Gold/min: 18000 / 30 = 600
        assert result.gold_per_min == 600.0
        
        # Damage per gold: 35000 / 18000 ≈ 1.94
        assert abs(result.damage_per_gold - 1.944) < 0.01
    
    def test_calculate_basic_kpi_player2(self, kpi_calculator, sample_match_data_with_kpi):
        """基本KPI計算テスト - プレイヤー2（サポート）"""
        result = kpi_calculator.calculate_basic_kpi(sample_match_data_with_kpi, "player2")
        
        assert result.player_id == "player2"
        assert result.champion == "Thresh"
        
        # KDA: (2 + 18) / 6 = 3.33
        assert abs(result.kda - 3.33) < 0.01
        
        # CS/10min: (45 + 5) / 3 = 16.67 (サポートなので低い)
        assert abs(result.cs_per_10min - 16.67) < 0.1
    
    def test_calculate_advanced_kpi(self, kpi_calculator, sample_match_data_with_kpi):
        """上級KPI計算テスト"""
        result = kpi_calculator.calculate_advanced_kpi(sample_match_data_with_kpi, "player1")
        
        # Vision score per min: 45 / 30 = 1.5
        assert result.vision_score_per_min == 1.5
        
        # Ward efficiency: (15 + 8) / 30 = 0.77
        assert abs(result.ward_efficiency - 0.77) < 0.01
        
        # First blood contribution
        assert result.first_blood_contribution is True
        
        # Overall score (0-100)
        assert 0 <= result.overall_score <= 100
    
    def test_calculate_cs_per_10min(self, kpi_calculator):
        """CS/10min計算の詳細テスト"""
        # 30分で280CS
        cs_rate = kpi_calculator.calculate_cs_per_10min(250, 30, 1800)
        assert abs(cs_rate - 93.33) < 0.1
        
        # ゼロ除算テスト
        cs_rate = kpi_calculator.calculate_cs_per_10min(100, 20, 0)
        assert cs_rate == 0.0
    
    def test_calculate_vision_score_efficiency(self, kpi_calculator):
        """ビジョンスコア効率計算テスト"""
        efficiency = kpi_calculator.calculate_vision_score_efficiency(45, 15, 8, 1800)
        assert efficiency == 1.5  # 45 / 30min
        
        # ゼロ除算テスト
        efficiency = kpi_calculator.calculate_vision_score_efficiency(30, 10, 5, 0)
        assert efficiency == 0.0
    
    def test_calculate_objective_contribution(self, kpi_calculator, sample_events_for_kpi):
        """オブジェクト貢献度計算テスト"""
        score = kpi_calculator.calculate_objective_contribution(sample_events_for_kpi, "player1")
        
        # TOWER_TURRET: 10, DRAGON: 20
        expected_score = 10 + 20
        assert score == expected_score
    
    def test_calculate_damage_per_gold(self, kpi_calculator):
        """ダメージ/ゴールド効率計算テスト"""
        efficiency = kpi_calculator.calculate_damage_per_gold(35000, 18000)
        assert abs(efficiency - 1.944) < 0.01
        
        # ゼロ除算テスト
        efficiency = kpi_calculator.calculate_damage_per_gold(10000, 0)
        assert efficiency == 0.0
    
    def test_player_not_found_error(self, kpi_calculator, sample_match_data_with_kpi):
        """存在しないプレイヤーIDのエラーテスト"""
        with pytest.raises(ValueError, match="Player nonexistent not found"):
            kpi_calculator.calculate_basic_kpi(sample_match_data_with_kpi, "nonexistent")


class TestLoLKPIFunctionality:
    """LoL KPI計算機能の具体的なテスト（実装後に使用）"""
    
    def test_cs_per_10min_calculation_future(self):
        """CS/10min計算の具体的テスト（将来実装予定）"""
        # 実装後に以下のような計算をテストする予定
        # CS 250 + jungle 30 = 280 total
        # 30分（1800秒）= 280 / (1800/600) = 93.33 CS/10min
        pytest.skip("LoLKPICalculator implementation pending")
    
    def test_kda_calculation_future(self):
        """KDA計算の具体的テスト（将来実装予定）"""
        # 実装後に以下のような計算をテストする予定
        # (12 kills + 8 assists) / 4 deaths = 5.0 KDA
        pytest.skip("LoLKPICalculator implementation pending")
    
    def test_vision_score_efficiency_future(self):
        """ビジョンスコア効率の具体的テスト（将来実装予定）"""
        # 実装後に以下のような計算をテストする予定
        # vision_score / (game_duration_minutes) = ビジョン効率
        # ward_efficiency = (wards_placed + wards_killed) / game_duration_minutes
        pytest.skip("LoLKPICalculator implementation pending")
    
    def test_objective_contribution_scoring_future(self):
        """オブジェクト貢献度スコアリングの具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - タワー破壊貢献度
        # - ドラゴン・バロン貢献度
        # - ファーストブラッド・ファーストタワー
        # - 重み付けスコア計算
        pytest.skip("LoLKPICalculator implementation pending")
    
    def test_comprehensive_kpi_report_future(self):
        """包括的KPIレポート生成の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - 全KPIの統合レポート
        # - 強み・弱み分析
        # - ロール別比較
        # - 改善提案
        pytest.skip("LoLKPICalculator implementation pending") 