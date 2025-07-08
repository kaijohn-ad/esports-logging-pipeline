"""OpenRouter統合LLMアナライザーのテスト

KPIデータを基にしたLoL特化分析、改善提案、
チャンピオン分析をLLMで実行する機能をテストします。
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from typing import Dict, Any, List
import json

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLFetcher, Event, KPIResult


class TestLoLLLMAnalyzer:
    """OpenRouter LLMアナライザーのテストクラス"""
    
    @pytest.fixture
    def sample_kpi_result(self):
        """サンプルKPIデータ"""
        return KPIResult(
            player_id="test_player",
            champion="Jinx",
            game_duration=1800.0,
            kda=3.5,
            cs_per_10min=85.2,
            gold_per_min=450.0,
            damage_per_gold=1.75,
            vision_score_per_min=1.8,
            ward_efficiency=0.9,
            objective_contribution=50.0,
            first_blood_contribution=True,
            strengths=["優秀なKDA - キルデス管理が上手", "高いダメージ効率 - ゴールドの有効活用"],
            weaknesses=["CS効率改善が必要 - ラストヒット練習を推奨"],
            overall_score=78.5
        )
    
    @pytest.fixture
    def sample_openrouter_response(self):
        """サンプルOpenRouterレスポンス"""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "analysis": {
                            "performance_summary": "全体的に良好なパフォーマンス。KDAは優秀だが、CSに改善の余地あり。",
                            "key_strengths": [
                                "キルデス管理が優秀（KDA 3.5）",
                                "ダメージ効率が高い（1.75）",
                                "ビジョン貢献が良好"
                            ],
                            "improvement_areas": [
                                "CS効率の改善（目標: 90+ CS/10min）",
                                "ワード効率の向上"
                            ]
                        },
                        "recommendations": [
                            "ラストヒット練習を重点的に行う",
                            "ミニマップ確認頻度を上げる",
                            "序盤のファーミング優先度を高める"
                        ],
                        "champion_specific": {
                            "champion": "Jinx",
                            "role_analysis": "ADCとして標準的なパフォーマンス",
                            "build_suggestions": "クリティカル特化ビルドを推奨",
                            "positioning_tips": "後方からの安全な立ち位置を意識"
                        }
                    })
                }
            }],
            "usage": {
                "prompt_tokens": 450,
                "completion_tokens": 380,
                "total_tokens": 830
            }
        }
    
    @pytest.fixture
    def llm_analyzer(self):
        """LLMアナライザーのインスタンス"""
        from log_pipeline import LoLLLMAnalyzer
        return LoLLLMAnalyzer()
    
    @pytest.fixture
    def openrouter_client(self):
        """OpenRouterクライアントのインスタンス"""
        from log_pipeline import OpenRouterClient
        return OpenRouterClient()
    
    def test_lol_llm_analyzer_creation(self, llm_analyzer):
        """LoLLLMAnalyzerクラスの作成テスト"""
        assert llm_analyzer is not None
        assert hasattr(llm_analyzer, 'client')
        assert hasattr(llm_analyzer, 'logger')
    
    def test_openrouter_client_creation(self, openrouter_client):
        """OpenRouterClientクラスの作成テスト"""
        assert openrouter_client is not None
        assert openrouter_client.api_key == "dummy_key"
        assert openrouter_client.primary_model == "anthropic/claude-3.5-sonnet"
        assert len(openrouter_client.fallback_models) > 0
    
    def test_analysis_result_creation(self):
        """AnalysisResultクラスの作成テスト"""
        from log_pipeline import AnalysisResult
        
        result = AnalysisResult(
            player_id="test",
            champion="Jinx",
            performance_summary="テスト要約",
            key_strengths=["強み1"],
            recommendations=["推奨1"]
        )
        
        assert result.player_id == "test"
        assert result.champion == "Jinx" 
        assert result.performance_summary == "テスト要約"
    
    @pytest.mark.asyncio
    async def test_analyze_performance(self, llm_analyzer, sample_kpi_result):
        """パフォーマンス分析機能のテスト"""
        result = await llm_analyzer.analyze_performance(sample_kpi_result)
        
        assert result.player_id == "test_player"
        assert result.champion == "Jinx"
        assert result.performance_summary != ""
        assert len(result.key_strengths) > 0
        assert result.analysis_time > 0
    
    def test_generate_recommendations(self, llm_analyzer, sample_kpi_result):
        """改善提案生成機能のテスト"""
        recommendations = llm_analyzer.generate_recommendations(sample_kpi_result)
        
        # CS/10min が85.2なので、CS改善提案は含まれない
        assert isinstance(recommendations, list)
        
        # KDAが3.5と良好なので、KDA改善提案は含まれない
        kda_improvement = any("デス" in rec for rec in recommendations)
        assert not kda_improvement
    
    @pytest.mark.asyncio  
    async def test_champion_analysis(self, llm_analyzer, sample_kpi_result):
        """チャンピオン特化分析機能のテスト"""
        result = await llm_analyzer.analyze_champion_performance(sample_kpi_result)
        
        assert "role_analysis" in result
        assert "build_suggestions" in result
        assert "positioning_tips" in result
        assert "Jinx" in result["role_analysis"]
    
    @pytest.mark.asyncio
    async def test_openrouter_request(self, openrouter_client):
        """OpenRouterリクエスト機能のテスト"""
        response = await openrouter_client.request("test prompt")
        
        assert "choices" in response
        assert "usage" in response
        assert response["usage"]["total_tokens"] > 0
    
    def test_fallback_model_setting(self, llm_analyzer):
        """フォールバックモデル機能のテスト"""
        new_models = ["claude-3-sonnet", "gpt-4"] 
        llm_analyzer.set_fallback_models(new_models)
        
        assert llm_analyzer.client.fallback_models == new_models
    
    def test_cost_tracking(self, llm_analyzer):
        """コスト追跡機能のテスト"""
        stats = llm_analyzer.get_usage_stats()
        
        assert "requests" in stats
        assert "total_tokens" in stats
        assert "total_cost" in stats
        assert "errors" in stats


class TestLoLLLMAnalyzerFunctionality:
    """LLMアナライザーの具体的なテスト（実装後に使用）"""
    
    def test_performance_analysis_future(self):
        """パフォーマンス分析の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - KPIデータの構造化分析
        # - 強み・弱みの詳細解析
        # - 数値に基づく客観的評価
        # - ロール別パフォーマンス比較
        pytest.skip("LoLLLMAnalyzer implementation pending")
    
    def test_recommendation_generation_future(self):
        """改善提案生成の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - 個人化された改善提案
        # - 優先度付きアクションプラン
        # - 短期・長期目標設定
        # - 具体的練習方法の提案
        pytest.skip("LoLLLMAnalyzer implementation pending")
    
    def test_champion_specific_analysis_future(self):
        """チャンピオン特化分析の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - チャンピオン固有のKPI評価
        # - ロール別期待値との比較
        # - ビルド・スキル順序の提案
        # - マッチアップ分析
        pytest.skip("LoLLLMAnalyzer implementation pending")
    
    def test_openrouter_integration_future(self):
        """OpenRouter統合の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - 複数モデルでの並列分析
        # - フォールバック機能
        # - レート制限対応
        # - コスト最適化
        pytest.skip("LoLLLMAnalyzer implementation pending")
    
    def test_error_handling_future(self):
        """エラーハンドリングの具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - API障害時の処理
        # - 不正レスポンスの処理
        # - タイムアウト処理
        # - リトライ機能
        pytest.skip("LoLLLMAnalyzer implementation pending")
    
    def test_prompt_optimization_future(self):
        """プロンプト最適化の具体的テスト（将来実装予定）"""
        # 実装後に以下のような機能をテストする予定
        # - LoL特化プロンプトテンプレート
        # - 動的プロンプト生成
        # - トークン使用量最適化
        # - 文脈に応じた調整
        pytest.skip("LoLLLMAnalyzer implementation pending") 