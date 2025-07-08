"""LoLマッチ詳細情報取得機能のテスト

プレイヤー情報、チーム情報、ランクデータの取得機能をテストします。
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLFetcher
from riotwatcher import ApiError


class TestLoLMatchDetails:
    """LoLマッチ詳細情報取得機能のテストクラス"""
    
    @pytest.fixture
    def fetcher(self):
        """テスト用のLoLFetcherインスタンス"""
        return LoLFetcher("test_api_key", region="jp1")
    
    @pytest.fixture
    def sample_match_data(self):
        """サンプルマッチデータ"""
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
                    {
                        "puuid": "puuid1",
                        "summonerName": "TestPlayer1",
                        "championName": "Jinx",
                        "teamId": 100,
                        "kills": 10,
                        "deaths": 3,
                        "assists": 5,
                        "totalMinionsKilled": 180,
                        "neutralMinionsKilled": 20,
                        "goldEarned": 15000,
                        "totalDamageDealtToChampions": 25000,
                        "visionScore": 25
                    }
                ],
                "teams": [
                    {
                        "teamId": 100,
                        "win": True,
                        "objectives": {
                            "baron": {"kills": 1},
                            "dragon": {"kills": 3},
                            "tower": {"kills": 8},
                            "inhibitor": {"kills": 2},
                            "riftHerald": {"kills": 1}
                        }
                    }
                ]
            }
        }
    
    def test_fetch_match_with_player_info_exists(self, fetcher):
        """プレイヤー情報付きマッチ取得機能の存在テスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'fetch_match_with_player_info')
        assert callable(getattr(fetcher, 'fetch_match_with_player_info'))
    
    def test_extract_player_performance_exists(self, fetcher):
        """プレイヤーパフォーマンス抽出機能の存在テスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'extract_player_performance')
        assert callable(getattr(fetcher, 'extract_player_performance'))
    
    def test_extract_team_performance_exists(self, fetcher):
        """チームパフォーマンス抽出機能の存在テスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'extract_team_performance')
        assert callable(getattr(fetcher, 'extract_team_performance'))
    
    def test_fetch_summoner_by_puuid_exists(self, fetcher):
        """PUUID によるサマナー情報取得機能の存在テスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'fetch_summoner_by_puuid')
        assert callable(getattr(fetcher, 'fetch_summoner_by_puuid'))
    
    def test_batch_fetch_player_ranks_exists(self, fetcher):
        """プレイヤーランク情報バッチ取得機能の存在テスト"""
        # メソッドが実装されていることを確認
        assert hasattr(fetcher, 'batch_fetch_player_ranks')
        assert callable(getattr(fetcher, 'batch_fetch_player_ranks'))
    
    def test_extract_player_performance_functionality(self, fetcher, sample_match_data):
        """プレイヤーパフォーマンス抽出機能のテスト"""
        performance = fetcher.extract_player_performance(sample_match_data, "puuid1")
        
        assert performance is not None
        assert performance["puuid"] == "puuid1"
        assert performance["championName"] == "Jinx"
        assert performance["kills"] == 10
        assert performance["deaths"] == 3
        assert performance["assists"] == 5
        assert performance["kda"] == 5.0  # (10 + 5) / 3
        assert performance["cs"] == 200  # 180 + 20
        assert performance["goldEarned"] == 15000
        assert performance["visionScore"] == 25
    
    def test_extract_team_performance_functionality(self, fetcher, sample_match_data):
        """チームパフォーマンス抽出機能のテスト"""
        team_performance = fetcher.extract_team_performance(sample_match_data, 100)
        
        assert team_performance is not None
        assert team_performance["teamId"] == 100
        assert team_performance["win"] is True
        assert team_performance["baron"] == 1
        assert team_performance["dragon"] == 3
        assert team_performance["tower"] == 8
        assert team_performance["inhibitor"] == 2
        assert team_performance["riftHerald"] == 1
    
    def test_calculate_kda_normal(self, fetcher):
        """KDA計算（通常ケース）のテスト"""
        kda = fetcher._calculate_kda(10, 3, 5)
        assert kda == 5.0
    
    def test_calculate_kda_perfect(self, fetcher):
        """KDA計算（デス0ケース）のテスト"""
        kda = fetcher._calculate_kda(10, 0, 5)
        assert kda == 15.0  # Perfect KDA
    
    def test_extract_player_performance_not_found(self, fetcher, sample_match_data):
        """存在しないプレイヤーのパフォーマンス抽出テスト"""
        performance = fetcher.extract_player_performance(sample_match_data, "nonexistent_puuid")
        assert performance is None
    
    def test_extract_team_performance_not_found(self, fetcher, sample_match_data):
        """存在しないチームのパフォーマンス抽出テスト"""
        team_performance = fetcher.extract_team_performance(sample_match_data, 999)
        assert team_performance is None 