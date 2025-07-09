"""
VALORANT Kill Event Processing と SQLite Storage の統合テスト

Task 2: Verify VALORANT Kill Event Processing and SQLite Storage
の要件に基づいて、エンドツーエンドのテストを実施する
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
import logging

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from collectors.valorant_fetcher import ValorantFetcher
from canonizer.valorant_canonizer import ValorantCanonizer
from storage.sqlite_store import SQLiteStore


class TestValorantKillEventIntegration:
    """VALORANT Kill Event Processing 統合テストクラス"""

    @pytest.fixture
    def sample_valorant_match_data(self):
        """テスト用のVALORANTマッチデータ"""
        return {
            "status": 200,
            "data": {
                "metadata": {
                    "matchid": "integration_test_match_456",
                    "map": "Haven",
                    "game_version": "release-09.01",
                    "game_length": 2100000,  # 35分
                    "game_start": 1640995200,
                    "rounds_played": 15,
                    "mode": "Competitive",
                    "queue": "competitive",
                    "region": "ap",
                    "cluster": "ap"
                },
                "players": {
                    "all_players": [
                        {
                            "puuid": "integration_puuid_1",
                            "name": "IntegrationPlayer",
                            "tag": "INT",
                            "team": "Red",
                            "character": "Sage",
                            "stats": {
                                "kills": 20,
                                "deaths": 12,
                                "assists": 8,
                                "score": 4200,
                                "headshots": 12,
                                "bodyshots": 15,
                                "legshots": 5,
                                "damage": {
                                    "made": 3500,
                                    "received": 2800
                                },
                                "first_bloods": 4,
                                "first_deaths": 2
                            }
                        },
                        {
                            "puuid": "integration_puuid_2",
                            "name": "OpponentPlayer",
                            "tag": "OPP",
                            "team": "Blue",
                            "character": "Jett",
                            "stats": {
                                "kills": 18,
                                "deaths": 15,
                                "assists": 6,
                                "score": 3800,
                                "headshots": 10,
                                "bodyshots": 13,
                                "legshots": 2,
                                "damage": {
                                    "made": 3200,
                                    "received": 3100
                                },
                                "first_bloods": 2,
                                "first_deaths": 3
                            }
                        }
                    ]
                },
                "teams": {
                    "red": {"has_won": True, "rounds_won": 13, "rounds_lost": 2},
                    "blue": {"has_won": False, "rounds_won": 2, "rounds_lost": 13}
                },
                "rounds": [
                    {
                        "round_num": 1,
                        "round_result": "Team Won",
                        "winning_team": "Red",
                        "plant_events": [],
                        "defuse_events": [],
                        "player_stats": [
                            {
                                "player_puuid": "integration_puuid_1",
                                "kills": 3,
                                "damage": 450,
                                "score": 350
                            },
                            {
                                "player_puuid": "integration_puuid_2",
                                "kills": 1,
                                "damage": 200,
                                "score": 150
                            }
                        ]
                    },
                    {
                        "round_num": 2,
                        "round_result": "Eliminated",
                        "winning_team": "Blue",
                        "plant_events": [],
                        "defuse_events": [],
                        "player_stats": [
                            {
                                "player_puuid": "integration_puuid_1",
                                "kills": 1,
                                "damage": 250,
                                "score": 200
                            },
                            {
                                "player_puuid": "integration_puuid_2",
                                "kills": 4,
                                "damage": 600,
                                "score": 500
                            }
                        ]
                    }
                ]
            }
        }

    @pytest.fixture
    def temp_db_path(self):
        """テスト用の一時的なSQLiteデータベースパス"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        yield temp_path
        # クリーンアップ
        if temp_path.exists():
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_end_to_end_valorant_kill_event_processing(self, sample_valorant_match_data, temp_db_path):
        """エンドツーエンドのVALORANTキルイベント処理テスト"""
        # Given: モックされたValorantFetcherとSQLiteStore
        with patch('collectors.valorant_fetcher.ValorantFetcher.fetch_match_details') as mock_fetch:
            mock_fetch.return_value = sample_valorant_match_data
            
            # 1. ValorantFetcherでデータを取得
            fetcher = ValorantFetcher(region="ap")
            async with fetcher:
                match_data = await fetcher.fetch_match_details("integration_test_match_456")
            
            # Then: データが正常に取得される
            assert match_data["status"] == 200
            assert match_data["data"]["metadata"]["matchid"] == "integration_test_match_456"
            assert len(match_data["data"]["players"]["all_players"]) == 2
            
            # 2. ValorantCanonizerでデータを正規化
            events = ValorantCanonizer.match_to_events(match_data)
            
            # Then: イベントが生成される
            assert len(events) > 0
            
            # round_killsイベントが含まれることを確認
            round_kills_events = [e for e in events if e.event == "round_kills"]
            assert len(round_kills_events) == 4  # 2ラウンド x 2プレイヤー
            
            # 3. round_killsイベントをkillイベントに変換
            kill_events = ValorantCanonizer.convert_round_kills_to_kill_events(events)
            
            # Then: killイベントが正しく生成される
            expected_kills = 3 + 1 + 1 + 4  # ラウンド1: 3+1キル, ラウンド2: 1+4キル
            assert len(kill_events) == expected_kills
            
            # 4. SQLiteStoreでデータベースに保存
            store = SQLiteStore(temp_db_path)
            store.init()
            
            # マッチデータを保存
            match_metadata = {
                "id": match_data["data"]["metadata"]["matchid"],
                "title": f"VALORANT Match on {match_data['data']['metadata']['map']}",
                "patch": match_data["data"]["metadata"]["game_version"],
                "timestamp": str(match_data["data"]["metadata"]["game_start"])
            }
            store.store_match(match_metadata)
            
            # 全イベント（正規化されたイベント + killイベント）を保存
            all_events = events + kill_events
            for event in all_events:
                store.store_event(match_metadata["id"], event)
            
            # 5. データベースの内容を検証
            stored_match = store.get_match(match_metadata["id"])
            assert stored_match is not None
            assert stored_match["id"] == match_metadata["id"]
            assert stored_match["title"] == match_metadata["title"]
            
            # 保存されたイベントを取得
            stored_events = store.get_events_for_match(match_metadata["id"])
            assert len(stored_events) == len(all_events)
            
            # killイベントが正しく保存されていることを確認
            stored_kill_events = [e for e in stored_events if e.event == "kill"]
            assert len(stored_kill_events) == expected_kills
            
            # 最初のkillイベントの詳細を確認
            first_kill = stored_kill_events[0]
            assert first_kill.event == "kill"
            assert first_kill.actor == "IntegrationPlayer#INT"
            assert first_kill.meta["round_num"] == 1
            assert first_kill.meta["kill_number"] == 1
            assert first_kill.meta["total_kills_in_round"] == 3

    @pytest.mark.asyncio
    async def test_error_handling_in_valorant_pipeline(self, temp_db_path):
        """VALORANTパイプラインでのエラーハンドリングテスト"""
        # Given: エラーを発生させるモックAPI
        with patch('collectors.valorant_fetcher.ValorantFetcher.fetch_match_details') as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")
            
            # When: エラーが発生する状況でパイプラインを実行
            fetcher = ValorantFetcher(region="ap")
            
            # Then: 適切にエラーがハンドリングされる
            with pytest.raises(Exception):
                async with fetcher:
                    await fetcher.fetch_match_details("error_match")

    def test_database_schema_for_kill_events(self, temp_db_path):
        """killイベント用のデータベーススキーマテスト"""
        # Given: SQLiteStore
        store = SQLiteStore(temp_db_path)
        store.init()
        
        # When: データベース構造を確認
        from storage.sqlite_store import get_db_connection
        with get_db_connection(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # event テーブルの存在を確認
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event'")
            table_exists = cursor.fetchone()
            assert table_exists is not None
            
            # event テーブルの構造を確認
            cursor.execute("PRAGMA table_info(event)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            expected_columns = ['id', 'match_id', 'ts', 'event', 'actor', 'target', 'meta']
            for col in expected_columns:
                assert col in column_names

    def test_valorant_canonizer_kill_event_metadata(self, sample_valorant_match_data):
        """ValorantCanonizerでkillイベントのメタデータが正しく設定されることをテスト"""
        # Given: サンプルマッチデータ
        events = ValorantCanonizer.match_to_events(sample_valorant_match_data)
        
        # When: killイベントに変換
        kill_events = ValorantCanonizer.convert_round_kills_to_kill_events(events)
        
        # Then: メタデータが適切に設定される
        for kill_event in kill_events:
            assert kill_event.event == "kill"
            assert "round_num" in kill_event.meta
            assert "kill_number" in kill_event.meta
            assert "total_kills_in_round" in kill_event.meta
            assert "puuid" in kill_event.meta
            assert kill_event.meta["round_num"] in [1, 2]
            assert kill_event.meta["kill_number"] >= 1
            assert kill_event.meta["total_kills_in_round"] >= kill_event.meta["kill_number"]

    def test_logging_configuration(self):
        """ロギング設定テスト"""
        # Given: ValorantFetcher
        fetcher = ValorantFetcher(region="ap")
        
        # Then: ロガーが正しく設定される
        assert hasattr(fetcher, 'logger')
        assert fetcher.logger.name == 'collectors.valorant_fetcher'
        
        # ログレベルが設定されている
        assert fetcher.logger.level <= logging.INFO

    @pytest.mark.asyncio
    async def test_full_pipeline_with_multiple_matches(self, temp_db_path):
        """複数マッチでのフルパイプラインテスト"""
        # Given: 複数のマッチデータ
        match_ids = ["match_001", "match_002"]
        
        with patch('collectors.valorant_fetcher.ValorantFetcher.fetch_match_details') as mock_fetch:
            # 異なるマッチデータを返すよう設定
            def mock_fetch_side_effect(match_id):
                base_data = {
                    "status": 200,
                    "data": {
                        "metadata": {
                            "matchid": match_id,
                            "map": "Bind" if match_id == "match_001" else "Split",
                            "game_version": "release-09.01",
                            "game_length": 1800000,
                            "game_start": 1640995200,
                            "rounds_played": 13,
                            "mode": "Competitive",
                            "queue": "competitive",
                            "region": "ap"
                        },
                        "players": {"all_players": []},
                        "teams": {},
                        "rounds": []
                    }
                }
                return base_data
            
            mock_fetch.side_effect = mock_fetch_side_effect
            
            # When: 複数マッチを処理
            store = SQLiteStore(temp_db_path)
            store.init()
            
            fetcher = ValorantFetcher(region="ap")
            async with fetcher:
                for match_id in match_ids:
                    match_data = await fetcher.fetch_match_details(match_id)
                    events = ValorantCanonizer.match_to_events(match_data)
                    kill_events = ValorantCanonizer.convert_round_kills_to_kill_events(events)
                    
                    # マッチ保存
                    match_metadata = {
                        "id": match_id,
                        "title": f"Match {match_id}",
                        "patch": match_data["data"]["metadata"]["game_version"],
                        "timestamp": str(match_data["data"]["metadata"]["game_start"])
                    }
                    store.store_match(match_metadata)
                    
                    # イベント保存
                    all_events = events + kill_events
                    for event in all_events:
                        store.store_event(match_id, event)
            
            # Then: 複数マッチが正しく保存される
            recent_matches = store.get_recent_matches(limit=10)
            stored_match_ids = [match["id"] for match in recent_matches]
            assert "match_001" in stored_match_ids
            assert "match_002" in stored_match_ids