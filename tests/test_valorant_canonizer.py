"""ValorantCanonizer機能のテスト

TDD（テスト駆動開発）に基づき、ValorantCanonizerクラスの
データ正規化機能をテストします。
"""

import pytest
from unittest.mock import Mock, patch
import json

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from canonizer.valorant_canonizer import ValorantCanonizer
from canonizer.event import Event


class TestValorantCanonizer:
    """ValorantCanonizer機能のテストクラス"""
    
    @pytest.fixture
    def sample_match_data(self):
        """テスト用のマッチデータ"""
        return {
            "data": {
                "metadata": {
                    "matchid": "test_match_123",
                    "map": "Bind",
                    "game_version": "release-08.11",
                    "game_length": 1800000,  # 30分をms
                    "game_start": 1640995200,
                    "rounds_played": 13,
                    "mode": "Competitive",
                    "queue": "competitive",
                    "region": "ap",
                    "cluster": "ap"
                },
                "players": {
                    "all_players": [
                        {
                            "puuid": "test_puuid_1",
                            "name": "TestPlayer",
                            "tag": "TST",
                            "team": "Red",
                            "character": "Sage",
                            "stats": {
                                "kills": 15,
                                "deaths": 8,
                                "assists": 5,
                                "score": 3250,
                                "headshots": 8,
                                "bodyshots": 12,
                                "legshots": 3,
                                "damage": {
                                    "made": 2800,
                                    "received": 1900
                                },
                                "first_bloods": 3,
                                "first_deaths": 1
                            }
                        },
                        {
                            "puuid": "test_puuid_2",
                            "name": "Enemy",
                            "tag": "ENM",
                            "team": "Blue",
                            "character": "Jett",
                            "stats": {
                                "kills": 12,
                                "deaths": 10,
                                "assists": 3,
                                "score": 2900,
                                "headshots": 6,
                                "bodyshots": 8,
                                "legshots": 2,
                                "damage": {
                                    "made": 2400,
                                    "received": 2200
                                },
                                "first_bloods": 1,
                                "first_deaths": 2
                            }
                        }
                    ]
                },
                "teams": {
                    "red": {
                        "has_won": True,
                        "rounds_won": 13,
                        "rounds_lost": 5
                    },
                    "blue": {
                        "has_won": False,
                        "rounds_won": 5,
                        "rounds_lost": 13
                    }
                },
                "rounds": [
                    {
                        "round_num": 1,
                        "round_result": "Team Won",
                        "winning_team": "Red",
                        "plant_events": [
                            {
                                "player_display_name": "TestPlayer#TST",
                                "plant_location": "A Site",
                                "planted_by": {
                                    "puuid": "test_puuid_1",
                                    "display_name": "TestPlayer#TST"
                                }
                            }
                        ],
                        "defuse_events": [],
                        "player_stats": [
                            {
                                "player_puuid": "test_puuid_1",
                                "kills": 2,
                                "damage": 350,
                                "score": 250
                            },
                            {
                                "player_puuid": "test_puuid_2",
                                "kills": 1,
                                "damage": 200,
                                "score": 150
                            }
                        ]
                    },
                    {
                        "round_num": 2,
                        "round_result": "Defused",
                        "winning_team": "Blue",
                        "plant_events": [],
                        "defuse_events": [
                            {
                                "player_display_name": "Enemy#ENM",
                                "defuse_location": "B Site",
                                "defused_by": {
                                    "puuid": "test_puuid_2",
                                    "display_name": "Enemy#ENM"
                                }
                            }
                        ],
                        "player_stats": [
                            {
                                "player_puuid": "test_puuid_1",
                                "kills": 0,
                                "damage": 150,
                                "score": 100
                            },
                            {
                                "player_puuid": "test_puuid_2",
                                "kills": 3,
                                "damage": 400,
                                "score": 350
                            }
                        ]
                    }
                ]
            }
        }
    
    @pytest.fixture
    def sample_player_stats(self):
        """テスト用のプレイヤー統計データ"""
        return {
            "data": {
                "puuid": "test_puuid_1",
                "region": "ap",
                "account_level": 150,
                "card": {
                    "small": "small_card_url",
                    "large": "large_card_url",
                    "wide": "wide_card_url",
                    "id": "card_id"
                },
                "last_update": "2025-01-18",
                "last_update_raw": 1705555200,
                "competitive": {
                    "current_data": {
                        "currenttier": 15,
                        "currenttierpatched": "Immortal 1",
                        "ranking_in_tier": 25,
                        "mmr_change_to_last_game": 18,
                        "elo": 1850
                    }
                },
                "unrated": {
                    "current_data": {
                        "matches": 50,
                        "wins": 32,
                        "losses": 18
                    }
                }
            }
        }
    
    @pytest.fixture
    def sample_rank_data(self):
        """テスト用のランクデータ"""
        return {
            "data": {
                "name": "TestPlayer",
                "tag": "TST",
                "current_data": {
                    "currenttier": 15,
                    "currenttierpatched": "Immortal 1",
                    "ranking_in_tier": 25,
                    "mmr_change_to_last_game": 18,
                    "elo": 1850,
                    "games_needed_for_rating": 0
                }
            }
        }
    
    def test_match_to_events_basic_structure(self, sample_match_data):
        """マッチデータから基本イベント構造への変換テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: イベントが生成される
        assert len(events) > 0
        assert all(isinstance(event, Event) for event in events)
    
    def test_match_start_event_creation(self, sample_match_data):
        """マッチ開始イベントの作成テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: マッチ開始イベントが含まれる
        match_start_events = [e for e in events if e.event == "match_start"]
        assert len(match_start_events) == 1
        
        start_event = match_start_events[0]
        assert start_event.timestamp == 0.0
        assert start_event.actor == "system"
        assert start_event.target is None
        assert start_event.meta["map"] == "Bind"
        assert start_event.meta["mode"] == "Competitive"
        assert start_event.meta["region"] == "ap"
    
    def test_agent_select_events_creation(self, sample_match_data):
        """エージェント選択イベントの作成テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: エージェント選択イベントが含まれる
        agent_select_events = [e for e in events if e.event == "agent_select"]
        assert len(agent_select_events) == 2  # 2プレイヤー分
        
        # 最初のプレイヤーのエージェント選択イベント
        player1_event = next(e for e in agent_select_events if e.actor == "TestPlayer#TST")
        assert player1_event.timestamp == 0.0
        assert player1_event.target is None
        assert player1_event.meta["agent"] == "Sage"
        assert player1_event.meta["team"] == "Red"
        assert player1_event.meta["puuid"] == "test_puuid_1"
    
    def test_round_events_creation(self, sample_match_data):
        """ラウンドイベントの作成テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: ラウンド関連イベントが含まれる
        round_start_events = [e for e in events if e.event == "round_start"]
        round_end_events = [e for e in events if e.event == "round_end"]
        
        assert len(round_start_events) == 2  # 2ラウンド分
        assert len(round_end_events) == 2
        
        # 最初のラウンド開始イベント
        first_round_start = round_start_events[0]
        assert first_round_start.timestamp == 0.0  # ラウンド1は0秒から
        assert first_round_start.actor == "system"
        assert first_round_start.meta["round_num"] == 1
        assert first_round_start.meta["round_result"] == "Team Won"
    
    def test_bomb_plant_events_creation(self, sample_match_data):
        """爆弾設置イベントの作成テスト"""
        # Given: サンプルマッチデータ（プラントイベント含む）
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: 爆弾設置イベントが含まれる
        plant_events = [e for e in events if e.event == "bomb_plant"]
        assert len(plant_events) == 1
        
        plant_event = plant_events[0]
        assert plant_event.timestamp == 30.0  # ラウンド開始から30秒後と推定
        assert plant_event.actor == "TestPlayer#TST"
        assert plant_event.target is None
        assert plant_event.meta["round_num"] == 1
        assert plant_event.meta["plant_location"] == "A Site"
    
    def test_bomb_defuse_events_creation(self, sample_match_data):
        """爆弾解除イベントの作成テスト"""
        # Given: サンプルマッチデータ（デフューズイベント含む）
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: 爆弾解除イベントが含まれる
        defuse_events = [e for e in events if e.event == "bomb_defuse"]
        assert len(defuse_events) == 1
        
        defuse_event = defuse_events[0]
        assert defuse_event.timestamp == 180.0  # ラウンド2開始（120秒）+ 60秒
        assert defuse_event.actor == "Enemy#ENM"
        assert defuse_event.target is None
        assert defuse_event.meta["round_num"] == 2
        assert defuse_event.meta["defuse_location"] == "B Site"
    
    def test_round_kills_events_creation(self, sample_match_data):
        """ラウンドキルイベントの作成テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: ラウンドキルイベントが含まれる
        round_kills_events = [e for e in events if e.event == "round_kills"]
        
        # キルがあるラウンドのみイベントが作成される
        assert len(round_kills_events) == 3  # ラウンド1で2プレイヤー、ラウンド2で1プレイヤー
        
        # ラウンド1のTestPlayerのキルイベント
        player1_r1_kills = next(e for e in round_kills_events 
                               if e.actor == "TestPlayer#TST" and e.meta["round_num"] == 1)
        assert player1_r1_kills.meta["kills"] == 2
        assert player1_r1_kills.meta["damage"] == 350
        assert player1_r1_kills.meta["score"] == 250
    
    def test_match_performance_events_creation(self, sample_match_data):
        """マッチパフォーマンスイベントの作成テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: マッチパフォーマンスイベントが含まれる
        performance_events = [e for e in events if e.event == "match_performance"]
        assert len(performance_events) == 2  # 2プレイヤー分
        
        # TestPlayerのパフォーマンス
        player1_performance = next(e for e in performance_events if e.actor == "TestPlayer#TST")
        assert player1_performance.timestamp == 1800.0  # ゲーム時間
        assert player1_performance.meta["puuid"] == "test_puuid_1"
        assert player1_performance.meta["agent"] == "Sage"
        assert player1_performance.meta["team"] == "Red"
        assert player1_performance.meta["kills"] == 15
        assert player1_performance.meta["deaths"] == 8
        assert player1_performance.meta["assists"] == 5
        assert player1_performance.meta["headshots"] == 8
        assert player1_performance.meta["damage_made"] == 2800
    
    def test_match_end_event_creation(self, sample_match_data):
        """マッチ終了イベントの作成テスト"""
        # Given: サンプルマッチデータ
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(sample_match_data)
        
        # Then: マッチ終了イベントが含まれる
        match_end_events = [e for e in events if e.event == "match_end"]
        assert len(match_end_events) == 1
        
        end_event = match_end_events[0]
        assert end_event.timestamp == 1800.0  # ゲーム時間
        assert end_event.actor == "system"
        assert end_event.target is None
        assert end_event.meta["match_id"] == "test_match_123"
        assert end_event.meta["map"] == "Bind"
        assert end_event.meta["rounds_played"] == 13
        assert end_event.meta["game_length"] == 1800.0
    
    def test_player_stats_to_events(self, sample_player_stats):
        """プレイヤー統計データのイベント変換テスト"""
        # Given: プレイヤー統計データ
        player_name = "TestPlayer#TST"
        
        # When: イベントに変換
        events = ValorantCanonizer.player_stats_to_events(sample_player_stats, player_name)
        
        # Then: 適切なイベントが生成される
        assert len(events) > 0
        
        # 基本統計イベント
        player_stats_events = [e for e in events if e.event == "player_stats"]
        assert len(player_stats_events) == 1
        
        stats_event = player_stats_events[0]
        assert stats_event.actor == player_name
        assert stats_event.meta["puuid"] == "test_puuid_1"
        assert stats_event.meta["region"] == "ap"
        assert stats_event.meta["account_level"] == 150
        
        # モード別統計イベント
        mode_stats_events = [e for e in events if e.event == "mode_stats"]
        assert len(mode_stats_events) == 2  # competitive, unrated
        
        competitive_event = next(e for e in mode_stats_events if e.meta["mode"] == "competitive")
        assert competitive_event.actor == player_name
        assert "current_data" in competitive_event.meta["stats"]
    
    def test_rank_data_to_events(self, sample_rank_data):
        """ランクデータのイベント変換テスト"""
        # Given: ランクデータ
        player_name = "TestPlayer#TST"
        
        # When: イベントに変換
        events = ValorantCanonizer.rank_data_to_events(sample_rank_data, player_name)
        
        # Then: ランク情報イベントが生成される
        assert len(events) == 1
        
        rank_event = events[0]
        assert rank_event.event == "rank_info"
        assert rank_event.actor == player_name
        assert rank_event.meta["name"] == "TestPlayer"
        assert rank_event.meta["tag"] == "TST"
        assert rank_event.meta["current_tier"] == 15
        assert rank_event.meta["current_tier_patched"] == "Immortal 1"
        assert rank_event.meta["ranking_in_tier"] == 25
        assert rank_event.meta["mmr_change"] == 18
        assert rank_event.meta["elo"] == 1850
    
    def test_filter_player_events(self, sample_match_data):
        """プレイヤー特定イベントのフィルタリングテスト"""
        # Given: マッチイベント
        events = ValorantCanonizer.match_to_events(sample_match_data)
        player_name = "TestPlayer#TST"
        
        # When: 特定プレイヤーのイベントをフィルタリング
        filtered_events = ValorantCanonizer.filter_player_events(events, player_name)
        
        # Then: 該当プレイヤーとシステムイベントのみが残る
        assert len(filtered_events) > 0
        
        for event in filtered_events:
            # プレイヤーに関連するイベントかシステムイベントであること
            is_player_related = (
                event.actor == player_name or
                event.target == player_name or
                event.meta.get("puuid") == "test_puuid_1" or
                event.event in ["match_start", "match_end", "round_start", "round_end"]
            )
            assert is_player_related
    
    def test_calculate_performance_metrics(self, sample_match_data):
        """パフォーマンス指標計算テスト"""
        # Given: マッチイベント
        events = ValorantCanonizer.match_to_events(sample_match_data)
        player_name = "TestPlayer#TST"
        
        # When: パフォーマンス指標を計算
        metrics = ValorantCanonizer.calculate_performance_metrics(events, player_name)
        
        # Then: 正しい指標が計算される
        assert metrics["total_kills"] == 15
        assert metrics["total_deaths"] == 8
        assert metrics["total_assists"] == 5
        assert metrics["first_bloods"] == 3
        assert metrics["first_deaths"] == 1
        assert metrics["kda_ratio"] == 2.5  # (15 + 5) / 8
        assert metrics["headshot_percentage"] == 34.78  # 8 / (8+12+3) * 100
        assert metrics["average_damage_per_round"] == 1400.0  # 2800 / 2
        assert metrics["total_rounds"] == 2  # round_endイベントの数
    
    def test_empty_data_handling(self):
        """空のデータ処理テスト"""
        # Given: 空のマッチデータ
        empty_data = {}
        
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(empty_data)
        
        # Then: 空のリストが返される
        assert events == []
    
    def test_missing_data_fields_handling(self):
        """データフィールド欠損時の処理テスト"""
        # Given: 不完全なマッチデータ
        incomplete_data = {
            "data": {
                "metadata": {"map": "Haven"},  # 他のフィールドが欠損
                "players": {"all_players": []},
                "rounds": []
            }
        }
        
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(incomplete_data)
        
        # Then: エラーなくイベントが生成される（最小限）
        assert len(events) >= 0  # 最低限のイベントは生成される
        
        # マッチ終了イベントは生成される
        match_end_events = [e for e in events if e.event == "match_end"]
        assert len(match_end_events) == 1


class TestValorantCanonizerEdgeCases:
    """ValorantCanonizer のエッジケーステスト"""
    
    def test_no_rounds_data(self):
        """ラウンドデータなしの場合のテスト"""
        # Given: ラウンドデータがないマッチデータ
        data_without_rounds = {
            "data": {
                "metadata": {"map": "Split", "game_length": 1200000},
                "players": {"all_players": []},
                "rounds": []
            }
        }
        
        # When: イベントに変換
        events = ValorantCanonizer.match_to_events(data_without_rounds)
        
        # Then: ラウンド関連イベントがない
        round_events = [e for e in events if e.event.startswith("round_")]
        assert len(round_events) == 0
    
    def test_player_stats_empty_data(self):
        """プレイヤー統計データが空の場合のテスト"""
        # Given: 空のプレイヤー統計データ
        empty_stats = {"data": {}}
        
        # When: イベントに変換
        events = ValorantCanonizer.player_stats_to_events(empty_stats, "TestPlayer")
        
        # Then: 基本統計イベントのみ生成
        assert len(events) == 1
        assert events[0].event == "player_stats"
    
    def test_rank_data_missing_current_data(self):
        """現在のランクデータが欠損している場合のテスト"""
        # Given: current_dataが欠損したランクデータ
        incomplete_rank_data = {
            "data": {
                "name": "TestPlayer",
                "tag": "TST"
                # current_data が欠損
            }
        }
        
        # When: イベントに変換
        events = ValorantCanonizer.rank_data_to_events(incomplete_rank_data, "TestPlayer#TST")
        
        # Then: イベントは生成されるが、ランク情報は欠損
        assert len(events) == 1
        rank_event = events[0]
        assert rank_event.meta["current_tier"] is None
        assert rank_event.meta["elo"] is None