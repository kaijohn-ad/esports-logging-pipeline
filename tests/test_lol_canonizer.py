"""LoLCanonizer拡張機能のテスト

より多くのイベントタイプとメタデータ強化機能をテストします。
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from log_pipeline import LoLCanonizer, Event
from riotwatcher import ApiError


class TestLoLCanonizerExpanded:
    """LoLCanonizer拡張機能のテストクラス"""
    
    @pytest.fixture
    def sample_timeline_data(self):
        """拡張されたタイムラインデータのサンプル"""
        return {
            "info": {
                "frames": [
                    {
                        "timestamp": 120000,  # 2分
                        "events": [
                            # キル イベント
                            {
                                "type": "CHAMPION_KILL",
                                "timestamp": 125000,
                                "killerId": 1,
                                "victimId": 6,
                                "assistingParticipantIds": [2, 3],
                                "position": {"x": 8500, "y": 4200}
                            },
                            # スキルレベルアップ
                            {
                                "type": "SKILL_LEVEL_UP",
                                "timestamp": 126000,
                                "participantId": 1,
                                "skillSlot": 1,
                                "levelUpType": "NORMAL"
                            },
                            # アイテム購入
                            {
                                "type": "ITEM_PURCHASED",
                                "timestamp": 127000,
                                "participantId": 1,
                                "itemId": 1001
                            },
                            # アイテム売却
                            {
                                "type": "ITEM_SOLD",
                                "timestamp": 128000,
                                "participantId": 1,
                                "itemId": 1001
                            },
                            # ワード設置
                            {
                                "type": "WARD_PLACED",
                                "timestamp": 129000,
                                "creatorId": 1,
                                "wardType": "YELLOW_TRINKET",
                                "position": {"x": 9000, "y": 4500}
                            },
                            # ワード破壊
                            {
                                "type": "WARD_KILL",
                                "timestamp": 130000,
                                "killerId": 6,
                                "wardType": "YELLOW_TRINKET",
                                "position": {"x": 9000, "y": 4500}
                            },
                            # 建物破壊
                            {
                                "type": "BUILDING_KILL",
                                "timestamp": 131000,
                                "killerId": 1,
                                "buildingType": "TOWER_TURRET",
                                "teamId": 200,
                                "position": {"x": 10500, "y": 1200}
                            },
                            # モンスター討伐
                            {
                                "type": "MONSTER_KILL",
                                "timestamp": 132000,
                                "killerId": 1,
                                "monsterType": "DRAGON",
                                "monsterSubType": "FIRE_DRAGON",
                                "position": {"x": 9800, "y": 4000}
                            }
                        ]
                    }
                ]
            }
        }
    
    def test_champion_kill_canonization(self):
        """チャンピオンキルの正規化テスト"""
        timeline_data = {
            "info": {
                "frames": [{
                    "timestamp": 120000,
                    "events": [{
                        "type": "CHAMPION_KILL",
                        "timestamp": 125000,
                        "killerId": 1,
                        "victimId": 6,
                        "assistingParticipantIds": [2, 3],
                        "position": {"x": 8500, "y": 4200}
                    }]
                }]
            }
        }
        
        events = LoLCanonizer.timeline_to_events(timeline_data)
        
        # キルイベントが正しく生成されることを確認
        kill_events = [e for e in events if e.event == "kill"]
        assert len(kill_events) == 1
        assert kill_events[0].actor == "1"
        assert kill_events[0].target == "6"
        assert kill_events[0].timestamp == 125.0
        assert kill_events[0].meta["assists"] == [2, 3]
        assert kill_events[0].meta["position"] == {"x": 8500, "y": 4200}
    
    def test_skill_levelup_canonization(self, sample_timeline_data):
        """スキルレベルアップの正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # スキルレベルアップイベントが生成されることを確認
        skill_events = [e for e in events if e.event == "skill_levelup"]
        assert len(skill_events) == 1
        assert skill_events[0].actor == "1"
        assert skill_events[0].target is None
        assert skill_events[0].timestamp == 126.0
        assert skill_events[0].meta["skillSlot"] == 1
        assert skill_events[0].meta["levelUpType"] == "NORMAL"
    
    def test_item_purchase_canonization(self, sample_timeline_data):
        """アイテム購入の正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # アイテム購入イベントが生成されることを確認
        item_buy_events = [e for e in events if e.event == "item_buy"]
        assert len(item_buy_events) == 1
        assert item_buy_events[0].actor == "1"
        assert item_buy_events[0].target is None
        assert item_buy_events[0].timestamp == 127.0
        assert item_buy_events[0].meta["itemId"] == 1001
    
    def test_item_sold_canonization(self, sample_timeline_data):
        """アイテム売却の正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # アイテム売却イベントが生成されることを確認
        item_sell_events = [e for e in events if e.event == "item_sell"]
        assert len(item_sell_events) == 1
        assert item_sell_events[0].actor == "1"
        assert item_sell_events[0].target is None
        assert item_sell_events[0].timestamp == 128.0
        assert item_sell_events[0].meta["itemId"] == 1001
    
    def test_ward_placed_canonization(self, sample_timeline_data):
        """ワード設置の正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # ワード設置イベントが生成されることを確認
        ward_place_events = [e for e in events if e.event == "ward_place"]
        assert len(ward_place_events) == 1
        assert ward_place_events[0].actor == "1"
        assert ward_place_events[0].target is None
        assert ward_place_events[0].timestamp == 129.0
        assert ward_place_events[0].meta["wardType"] == "YELLOW_TRINKET"
        assert ward_place_events[0].meta["position"] == {"x": 9000, "y": 4500}
    
    def test_ward_kill_canonization(self, sample_timeline_data):
        """ワード破壊の正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # ワード破壊イベントが生成されることを確認
        ward_destroy_events = [e for e in events if e.event == "ward_destroy"]
        assert len(ward_destroy_events) == 1
        assert ward_destroy_events[0].actor == "6"
        assert ward_destroy_events[0].target is None
        assert ward_destroy_events[0].timestamp == 130.0
        assert ward_destroy_events[0].meta["wardType"] == "YELLOW_TRINKET"
        assert ward_destroy_events[0].meta["position"] == {"x": 9000, "y": 4500}
    
    def test_building_kill_canonization(self, sample_timeline_data):
        """建物破壊の正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # 建物破壊イベントが生成されることを確認
        objective_destroy_events = [e for e in events if e.event == "objective_destroy"]
        assert len(objective_destroy_events) == 1
        assert objective_destroy_events[0].actor == "1"
        assert objective_destroy_events[0].target is None
        assert objective_destroy_events[0].timestamp == 131.0
        assert objective_destroy_events[0].meta["buildingType"] == "TOWER_TURRET"
        assert objective_destroy_events[0].meta["teamId"] == 200
        assert objective_destroy_events[0].meta["position"] == {"x": 10500, "y": 1200}
    
    def test_monster_kill_canonization(self, sample_timeline_data):
        """モンスター討伐の正規化テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # モンスター討伐イベントが生成されることを確認
        monster_kill_events = [e for e in events if e.event == "monster_kill"]
        assert len(monster_kill_events) == 1
        assert monster_kill_events[0].actor == "1"
        assert monster_kill_events[0].target is None
        assert monster_kill_events[0].timestamp == 132.0
        assert monster_kill_events[0].meta["monsterType"] == "DRAGON"
        assert monster_kill_events[0].meta["monsterSubType"] == "FIRE_DRAGON"
        assert monster_kill_events[0].meta["position"] == {"x": 9800, "y": 4000}
    
    def test_enhanced_event_schema_not_implemented(self):
        """拡張Eventスキーマのテスト（未実装）"""
        # 現在のEventクラスには position, team_id, match_context がない
        event = Event(timestamp=120.0, event="test", actor="player1")
        
        assert not hasattr(event, 'position')
        assert not hasattr(event, 'team_id') 
        assert not hasattr(event, 'match_context')
    
    def test_canonizer_metadata_extraction(self, sample_timeline_data):
        """メタデータ抽出機能のテスト"""
        # 位置情報がメタデータに正しく抽出されていることを確認
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # 位置情報を持つイベントを検証
        events_with_position = [e for e in events if e.meta.get("position") is not None]
        assert len(events_with_position) >= 1  # キル、ワード、建物、モンスターイベントが含まれる
        
        # キルイベントの位置情報を検証
        kill_events = [e for e in events if e.event == "kill"]
        assert kill_events[0].meta["position"] == {"x": 8500, "y": 4200}
    
    def test_all_event_types_comprehensive(self, sample_timeline_data):
        """全イベントタイプの包括的テスト"""
        events = LoLCanonizer.timeline_to_events(sample_timeline_data)
        
        # 期待されるイベントタイプがすべて生成されることを確認
        event_types = {e.event for e in events}
        expected_types = {
            "kill", "skill_levelup", "item_buy", "item_sell",
            "ward_place", "ward_destroy", "objective_destroy", "monster_kill"
        }
        
        assert event_types == expected_types
        assert len(events) == 8  # 全8イベント 