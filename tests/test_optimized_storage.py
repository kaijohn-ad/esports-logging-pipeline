#!/usr/bin/env python3
"""
最適化されたSQLiteストレージシステムのテストファイル

データベースパフォーマンス最適化とスケーラビリティ向上機能の包括的なテスト
"""

import unittest
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.optimized_sqlite_store import (
    OptimizedSQLiteStore, 
    DatabaseShardConfig,
    CacheType,
    ConsistentHashRing,
    CacheManager
)
from src.canonizer.event import Event


class TestConsistentHashRing(unittest.TestCase):
    """一貫性ハッシュリングのテスト"""
    
    def setUp(self):
        self.nodes = ["shard1", "shard2", "shard3"]
        self.hash_ring = ConsistentHashRing(self.nodes)
    
    def test_node_assignment(self):
        """ノード割り当てのテスト"""
        key = "test_match_id"
        node = self.hash_ring.get_node(key)
        self.assertIn(node, self.nodes)
        
        # 同じキーは同じノードに割り当てられる
        self.assertEqual(node, self.hash_ring.get_node(key))
    
    def test_add_node(self):
        """ノード追加のテスト"""
        self.hash_ring.add_node("shard4")
        self.assertIn("shard4", self.hash_ring.nodes)
        
        # 新しいノードが使用される
        for _ in range(100):
            key = f"test_key_{_}"
            node = self.hash_ring.get_node(key)
            self.assertIn(node, ["shard1", "shard2", "shard3", "shard4"])
    
    def test_remove_node(self):
        """ノード削除のテスト"""
        self.hash_ring.remove_node("shard2")
        self.assertNotIn("shard2", self.hash_ring.nodes)
        
        # 削除されたノードは使用されない
        for _ in range(100):
            key = f"test_key_{_}"
            node = self.hash_ring.get_node(key)
            self.assertNotEqual(node, "shard2")


class TestCacheManager(unittest.TestCase):
    """キャッシュマネージャーのテスト"""
    
    def setUp(self):
        self.cache_manager = CacheManager(CacheType.MEMORY)
    
    def test_memory_cache_basic_operations(self):
        """メモリキャッシュの基本操作テスト"""
        # キャッシュに保存
        self.cache_manager.set("test_key", {"data": "test_value"})
        
        # キャッシュから取得
        result = self.cache_manager.get("test_key")
        self.assertEqual(result, {"data": "test_value"})
        
        # 存在しないキーの取得
        result = self.cache_manager.get("nonexistent_key")
        self.assertIsNone(result)
    
    def test_cache_invalidation(self):
        """キャッシュ無効化のテスト"""
        self.cache_manager.set("test_key", {"data": "test_value"})
        
        # キャッシュが存在することを確認
        result = self.cache_manager.get("test_key")
        self.assertIsNotNone(result)
        
        # キャッシュを無効化
        self.cache_manager.invalidate("test_key")
        
        # キャッシュが削除されたことを確認
        result = self.cache_manager.get("test_key")
        self.assertIsNone(result)
    
    def test_cache_stats(self):
        """キャッシュ統計のテスト"""
        # 初期状態
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats["hits"], 0)
        self.assertEqual(stats["misses"], 0)
        self.assertEqual(stats["hit_rate"], 0)
        
        # キャッシュミス
        self.cache_manager.get("nonexistent_key")
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats["misses"], 1)
        
        # キャッシュヒット
        self.cache_manager.set("test_key", "test_value")
        self.cache_manager.get("test_key")
        stats = self.cache_manager.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["hit_rate"], 0.5)  # 1 hit / 2 total


class TestOptimizedSQLiteStore(unittest.TestCase):
    """最適化されたSQLiteストレージのテスト"""
    
    def setUp(self):
        """テストセットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.store = OptimizedSQLiteStore(self.db_path)
        self.store.init()
    
    def tearDown(self):
        """テストクリーンアップ"""
        self.store.close()
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_basic_match_operations(self):
        """基本的な試合データ操作のテスト"""
        match_data = {
            "id": "test_match_1",
            "title": "Test Match",
            "patch": "14.1",
            "timestamp": "2025-01-21T10:00:00Z"
        }
        
        # 試合データを保存
        self.store.store_match(match_data)
        
        # 試合データを取得
        retrieved_match = self.store.get_match("test_match_1")
        self.assertEqual(retrieved_match["id"], "test_match_1")
        self.assertEqual(retrieved_match["title"], "Test Match")
        self.assertEqual(retrieved_match["patch"], "14.1")
        self.assertEqual(retrieved_match["timestamp"], "2025-01-21T10:00:00Z")
    
    def test_basic_event_operations(self):
        """基本的なイベントデータ操作のテスト"""
        # 試合データを先に保存
        match_data = {
            "id": "test_match_1",
            "title": "Test Match",
            "patch": "14.1",
            "timestamp": "2025-01-21T10:00:00Z"
        }
        self.store.store_match(match_data)
        
        # イベントデータを作成
        event = Event(
            timestamp=1234567890.0,
            event="KILL",
            actor="Player1",
            target="Player2",
            meta={"weapon": "sword"}
        )
        
        # イベントを保存
        self.store.store_event("test_match_1", event)
        
        # イベントを取得
        events = self.store._get_events_single_db("test_match_1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, "KILL")
        self.assertEqual(events[0].actor, "Player1")
        self.assertEqual(events[0].target, "Player2")
    
    def test_caching_functionality(self):
        """キャッシュ機能のテスト"""
        match_data = {
            "id": "test_match_cache",
            "title": "Cached Match",
            "patch": "14.1",
            "timestamp": "2025-01-21T10:00:00Z"
        }
        
        # 試合データを保存（キャッシュに保存される）
        self.store.store_match(match_data)
        
        # 初回取得（データベースアクセス）
        start_time = time.time()
        result1 = self.store.get_match("test_match_cache")
        first_access_time = time.time() - start_time
        
        # 2回目取得（キャッシュから）
        start_time = time.time()
        result2 = self.store.get_match("test_match_cache")
        second_access_time = time.time() - start_time
        
        # 結果は同じ
        self.assertEqual(result1, result2)
        
        # キャッシュ統計を確認
        stats = self.store.cache_manager.get_stats()
        self.assertGreater(stats["hits"], 0)
    
    def test_performance_metrics(self):
        """パフォーマンスメトリクスのテスト"""
        match_data = {
            "id": "test_match_performance",
            "title": "Performance Test Match",
            "patch": "14.1",
            "timestamp": "2025-01-21T10:00:00Z"
        }
        
        # 操作を実行
        self.store.store_match(match_data)
        self.store.get_match("test_match_performance")
        
        # パフォーマンス統計を取得
        stats = self.store.get_performance_stats()
        self.assertGreater(stats["total_queries"], 0)
        self.assertIn("avg_execution_time", stats)
        self.assertIn("cache_stats", stats)
    
    def test_backup_and_restore(self):
        """バックアップとリストア機能のテスト"""
        # テストデータを作成
        match_data = {
            "id": "test_match_backup",
            "title": "Backup Test Match",
            "patch": "14.1",
            "timestamp": "2025-01-21T10:00:00Z"
        }
        self.store.store_match(match_data)
        
        # バックアップを作成
        backup_path = Path(self.temp_dir) / "backup.db"
        success = self.store.backup_database(backup_path)
        self.assertTrue(success)
        self.assertTrue(backup_path.exists())
        
        # 元のデータを削除
        self.store.db_path.unlink()
        
        # リストアを実行
        success = self.store.restore_database(backup_path)
        self.assertTrue(success)
        self.assertTrue(self.store.db_path.exists())
        
        # データが復元されているか確認
        retrieved_match = self.store.get_match("test_match_backup")
        self.assertEqual(retrieved_match["id"], "test_match_backup")
    
    def test_database_optimization(self):
        """データベース最適化のテスト"""
        # テストデータを作成
        for i in range(100):
            match_data = {
                "id": f"test_match_{i}",
                "title": f"Test Match {i}",
                "patch": "14.1",
                "timestamp": f"2025-01-21T{i:02d}:00:00Z"
            }
            self.store.store_match(match_data)
        
        # 最適化を実行
        results = self.store.optimize_database()
        
        # 結果を確認
        self.assertIn(str(self.store.db_path), results)
        db_result = results[str(self.store.db_path)]
        self.assertTrue(db_result["vacuum_completed"])
        self.assertTrue(db_result["analyze_completed"])
        self.assertGreater(db_result["match_indexes"], 0)
        self.assertGreater(db_result["event_indexes"], 0)


class TestShardedStorage(unittest.TestCase):
    """シャーディング機能のテスト"""
    
    def setUp(self):
        """シャーディングテストのセットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.main_db_path = Path(self.temp_dir) / "main.db"
        
        # シャード設定
        self.shard_configs = [
            DatabaseShardConfig("shard1", Path(self.temp_dir) / "shard1.db"),
            DatabaseShardConfig("shard2", Path(self.temp_dir) / "shard2.db"),
            DatabaseShardConfig("shard3", Path(self.temp_dir) / "shard3.db")
        ]
        
        # シャーディング有効でストレージを初期化
        self.store = OptimizedSQLiteStore(
            self.main_db_path,
            enable_sharding=True,
            shard_configs=self.shard_configs
        )
        self.store.init()
    
    def tearDown(self):
        """テストクリーンアップ"""
        self.store.close()
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_shard_initialization(self):
        """シャード初期化のテスト"""
        # 全てのシャードが作成されていることを確認
        for shard_config in self.shard_configs:
            self.assertTrue(shard_config.db_path.exists())
    
    def test_data_distribution(self):
        """データ分散のテスト"""
        # 複数の試合データを作成
        matches = []
        for i in range(100):
            match_data = {
                "id": f"match_{i}",
                "title": f"Test Match {i}",
                "patch": "14.1",
                "timestamp": f"2025-01-21T{i:02d}:00:00Z"
            }
            matches.append(match_data)
            self.store.store_match(match_data)
        
        # データが複数のシャードに分散されているか確認
        shard_data_counts = {}
        for shard_config in self.shard_configs:
            with self.store._get_connection(shard_config.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM match")
                count = cur.fetchone()[0]
                shard_data_counts[shard_config.shard_id] = count
        
        # 最低2つのシャードにデータが分散されているか確認
        non_empty_shards = sum(1 for count in shard_data_counts.values() if count > 0)
        self.assertGreaterEqual(non_empty_shards, 2)
    
    def test_parallel_event_retrieval(self):
        """並列イベント取得のテスト"""
        # テストデータを作成
        match_id = "parallel_test_match"
        match_data = {
            "id": match_id,
            "title": "Parallel Test Match",
            "patch": "14.1",
            "timestamp": "2025-01-21T10:00:00Z"
        }
        self.store.store_match(match_data)
        
        # 複数のイベントを作成
        events = []
        for i in range(10):
            event = Event(
                timestamp=1234567890.0 + i,
                event=f"EVENT_{i}",
                actor=f"Player{i}",
                target=f"Target{i}",
                meta={"sequence": i}
            )
            events.append(event)
            self.store.store_event(match_id, event)
        
        # 並列でイベントを取得
        retrieved_events = self.store.get_events_for_match_parallel(match_id)
        
        # 結果を確認
        self.assertEqual(len(retrieved_events), 10)
        # タイムスタンプ順にソートされているか確認
        timestamps = [event.timestamp for event in retrieved_events]
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_backup_with_sharding(self):
        """シャーディング環境でのバックアップテスト"""
        # テストデータを作成
        for i in range(10):
            match_data = {
                "id": f"shard_backup_match_{i}",
                "title": f"Shard Backup Test Match {i}",
                "patch": "14.1",
                "timestamp": f"2025-01-21T{i:02d}:00:00Z"
            }
            self.store.store_match(match_data)
        
        # バックアップを作成
        backup_path = Path(self.temp_dir) / "shard_backup.db"
        success = self.store.backup_database(backup_path)
        self.assertTrue(success)
        
        # メインデータベースのバックアップが作成されているか確認
        self.assertTrue(backup_path.exists())
        
        # シャードのバックアップが作成されているか確認
        for shard_config in self.shard_configs:
            shard_backup_path = backup_path.parent / f"{backup_path.stem}_{shard_config.shard_id}.db"
            # シャードにデータがある場合のみバックアップが作成される
            if shard_config.db_path.exists():
                with self.store._get_connection(shard_config.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM match")
                    count = cur.fetchone()[0]
                    if count > 0:
                        self.assertTrue(shard_backup_path.exists())


class TestPerformanceBenchmark(unittest.TestCase):
    """パフォーマンスベンチマークテスト"""
    
    def setUp(self):
        """ベンチマークテストのセットアップ"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "benchmark.db"
        
        # 最適化されたストレージとベーシックストレージを比較
        self.optimized_store = OptimizedSQLiteStore(self.db_path)
        self.optimized_store.init()
    
    def tearDown(self):
        """テストクリーンアップ"""
        self.optimized_store.close()
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_bulk_insert_performance(self):
        """バルク挿入のパフォーマンステスト"""
        num_records = 1000
        
        # 大量のデータを挿入
        start_time = time.time()
        for i in range(num_records):
            match_data = {
                "id": f"bulk_match_{i}",
                "title": f"Bulk Test Match {i}",
                "patch": "14.1",
                "timestamp": f"2025-01-21T{i%24:02d}:00:00Z"
            }
            self.optimized_store.store_match(match_data)
        
        insertion_time = time.time() - start_time
        
        # パフォーマンス統計を取得
        stats = self.optimized_store.get_performance_stats()
        
        # 結果を出力
        print(f"\nバルク挿入パフォーマンス:")
        print(f"  レコード数: {num_records}")
        print(f"  総時間: {insertion_time:.2f}秒")
        print(f"  平均挿入時間: {insertion_time/num_records*1000:.2f}ms/レコード")
        print(f"  平均クエリ実行時間: {stats['avg_execution_time']*1000:.2f}ms")
        
        # 基本的な性能要件を確認
        self.assertLess(insertion_time, 30.0)  # 30秒以内で1000レコード挿入
        self.assertLess(stats['avg_execution_time'], 0.1)  # 平均100ms以下
    
    def test_concurrent_access_performance(self):
        """同時アクセスのパフォーマンステスト"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # データを準備
        for i in range(100):
            match_data = {
                "id": f"concurrent_match_{i}",
                "title": f"Concurrent Test Match {i}",
                "patch": "14.1",
                "timestamp": f"2025-01-21T{i%24:02d}:00:00Z"
            }
            self.optimized_store.store_match(match_data)
        
        # 並列読み込みテスト
        def read_match(match_id):
            return self.optimized_store.get_match(f"concurrent_match_{match_id}")
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_match, i) for i in range(100)]
            results = [future.result() for future in as_completed(futures)]
        
        concurrent_time = time.time() - start_time
        
        # 結果を確認
        self.assertEqual(len(results), 100)
        self.assertTrue(all(result is not None for result in results))
        
        print(f"\n同時アクセスパフォーマンス:")
        print(f"  並列読み込み時間: {concurrent_time:.2f}秒")
        print(f"  平均読み込み時間: {concurrent_time/100*1000:.2f}ms/レコード")
        
        # キャッシュ効果を確認
        cache_stats = self.optimized_store.cache_manager.get_stats()
        print(f"  キャッシュヒット率: {cache_stats['hit_rate']:.2%}")
        
        # 基本的な性能要件を確認
        self.assertLess(concurrent_time, 5.0)  # 5秒以内で100レコード読み込み


if __name__ == "__main__":
    # テストの実行
    unittest.main(verbosity=2)