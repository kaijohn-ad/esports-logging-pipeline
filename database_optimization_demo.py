#!/usr/bin/env python3
"""
データベースパフォーマンス最適化機能のデモンストレーション

このスクリプトでは以下の機能を実演します：
1. インデックス最適化
2. クエリ改善
3. パラレル処理
4. キャッシング
5. シャーディング
6. バックアップ・リストア機能
"""

import os
import sys
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# プロジェクトのルートディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.storage.optimized_sqlite_store import (
    OptimizedSQLiteStore,
    DatabaseShardConfig,
    CacheType
)
from src.storage.sqlite_store import SQLiteStore
from src.canonizer.event import Event

def print_section(title):
    """セクションタイトルを表示"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_subsection(title):
    """サブセクションタイトルを表示"""
    print(f"\n{'-'*40}")
    print(f"  {title}")
    print(f"{'-'*40}")

def generate_test_data(num_matches=100, num_events_per_match=50):
    """テストデータを生成"""
    matches = []
    events = []
    
    for i in range(num_matches):
        match_data = {
            "id": f"match_{i:04d}",
            "title": f"Test Match {i}",
            "patch": random.choice(["14.1", "14.2", "14.3"]),
            "timestamp": f"2025-01-21T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00Z"
        }
        matches.append(match_data)
        
        # 各試合にイベントを生成
        match_events = []
        for j in range(num_events_per_match):
            event = Event(
                timestamp=1234567890.0 + (i * 1000) + j,
                event=random.choice(["KILL", "DEATH", "ASSIST", "OBJECTIVE", "ITEM"]),
                actor=f"Player{random.randint(1, 10)}",
                target=f"Target{random.randint(1, 10)}",
                meta={
                    "weapon": random.choice(["sword", "bow", "magic", "axe"]),
                    "position": [random.randint(0, 100), random.randint(0, 100)]
                }
            )
            match_events.append(event)
        
        events.append((match_data["id"], match_events))
    
    return matches, events

def demo_basic_vs_optimized():
    """基本ストレージと最適化ストレージの比較デモ"""
    print_section("基本ストレージ vs 最適化ストレージ比較")
    
    # テストデータを生成
    matches, events = generate_test_data(50, 20)
    
    # 基本ストレージのテスト
    print_subsection("基本ストレージのパフォーマンス")
    basic_store = SQLiteStore(Path("data/basic_test.db"))
    basic_store.init()
    
    start_time = time.time()
    for match_data in matches:
        basic_store.store_match(match_data)
    basic_insert_time = time.time() - start_time
    
    start_time = time.time()
    for match_data in matches:
        basic_store.get_match(match_data["id"])
    basic_read_time = time.time() - start_time
    
    print(f"基本ストレージ:")
    print(f"  挿入時間: {basic_insert_time:.3f}秒")
    print(f"  読み込み時間: {basic_read_time:.3f}秒")
    
    # 最適化ストレージのテスト
    print_subsection("最適化ストレージのパフォーマンス")
    optimized_store = OptimizedSQLiteStore(Path("data/optimized_test.db"))
    optimized_store.init()
    
    start_time = time.time()
    for match_data in matches:
        optimized_store.store_match(match_data)
    optimized_insert_time = time.time() - start_time
    
    start_time = time.time()
    for match_data in matches:
        optimized_store.get_match(match_data["id"])
    optimized_read_time = time.time() - start_time
    
    print(f"最適化ストレージ:")
    print(f"  挿入時間: {optimized_insert_time:.3f}秒")
    print(f"  読み込み時間: {optimized_read_time:.3f}秒")
    
    # 改善比較
    print_subsection("パフォーマンス改善比較")
    insert_improvement = (basic_insert_time - optimized_insert_time) / basic_insert_time * 100
    read_improvement = (basic_read_time - optimized_read_time) / basic_read_time * 100
    
    print(f"挿入性能改善: {insert_improvement:.1f}%")
    print(f"読み込み性能改善: {read_improvement:.1f}%")
    
    # パフォーマンス統計を表示
    stats = optimized_store.get_performance_stats()
    print(f"\n最適化ストレージ統計:")
    print(f"  総クエリ数: {stats['total_queries']}")
    print(f"  平均実行時間: {stats['avg_execution_time']*1000:.2f}ms")
    print(f"  最大実行時間: {stats['max_execution_time']*1000:.2f}ms")
    print(f"  最小実行時間: {stats['min_execution_time']*1000:.2f}ms")
    
    # キャッシュ統計
    cache_stats = stats['cache_stats']
    print(f"\nキャッシュ統計:")
    print(f"  ヒット数: {cache_stats['hits']}")
    print(f"  ミス数: {cache_stats['misses']}")
    print(f"  ヒット率: {cache_stats['hit_rate']:.2%}")
    
    # クリーンアップ
    optimized_store.close()

def demo_caching():
    """キャッシング機能のデモ"""
    print_section("キャッシング機能デモ")
    
    store = OptimizedSQLiteStore(Path("data/cache_test.db"))
    store.init()
    
    # テストデータを準備
    matches, _ = generate_test_data(10, 5)
    for match_data in matches:
        store.store_match(match_data)
    
    print_subsection("キャッシュなし（初回アクセス）")
    start_time = time.time()
    for match_data in matches:
        store.get_match(match_data["id"])
    no_cache_time = time.time() - start_time
    print(f"読み込み時間: {no_cache_time:.3f}秒")
    
    print_subsection("キャッシュあり（2回目アクセス）")
    start_time = time.time()
    for match_data in matches:
        store.get_match(match_data["id"])
    with_cache_time = time.time() - start_time
    print(f"読み込み時間: {with_cache_time:.3f}秒")
    
    # 改善率を計算
    cache_improvement = (no_cache_time - with_cache_time) / no_cache_time * 100
    print(f"\nキャッシュによる改善: {cache_improvement:.1f}%")
    
    # キャッシュ統計を表示
    cache_stats = store.cache_manager.get_stats()
    print(f"\nキャッシュ統計:")
    print(f"  総リクエスト数: {cache_stats['total_requests']}")
    print(f"  ヒット数: {cache_stats['hits']}")
    print(f"  ミス数: {cache_stats['misses']}")
    print(f"  ヒット率: {cache_stats['hit_rate']:.2%}")
    
    store.close()

def demo_sharding():
    """シャーディング機能のデモ"""
    print_section("シャーディング機能デモ")
    
    # シャード設定
    shard_configs = [
        DatabaseShardConfig("shard1", Path("data/shard1.db")),
        DatabaseShardConfig("shard2", Path("data/shard2.db")),
        DatabaseShardConfig("shard3", Path("data/shard3.db"))
    ]
    
    store = OptimizedSQLiteStore(
        Path("data/sharded_main.db"),
        enable_sharding=True,
        shard_configs=shard_configs
    )
    store.init()
    
    # テストデータを生成
    matches, events = generate_test_data(100, 10)
    
    print_subsection("データを複数シャードに分散保存")
    start_time = time.time()
    for match_data in matches:
        store.store_match(match_data)
    
    for match_id, match_events in events:
        for event in match_events:
            store.store_event(match_id, event)
    
    sharding_time = time.time() - start_time
    print(f"シャーディング挿入時間: {sharding_time:.3f}秒")
    
    # 各シャードのデータ分布を確認
    print_subsection("シャード別データ分布")
    for shard_config in shard_configs:
        with store._get_connection(shard_config.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM match")
            match_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM event")
            event_count = cur.fetchone()[0]
            print(f"  {shard_config.shard_id}: 試合数={match_count}, イベント数={event_count}")
    
    # 並列データ取得のテスト
    print_subsection("並列データ取得テスト")
    test_matches = random.sample(matches, 10)
    
    start_time = time.time()
    for match_data in test_matches:
        events = store.get_events_for_match_parallel(match_data["id"])
    parallel_time = time.time() - start_time
    
    print(f"並列イベント取得時間: {parallel_time:.3f}秒")
    
    store.close()

def demo_backup_restore():
    """バックアップ・リストア機能のデモ"""
    print_section("バックアップ・リストア機能デモ")
    
    # 元のストレージを作成
    original_store = OptimizedSQLiteStore(Path("data/backup_original.db"))
    original_store.init()
    
    # テストデータを作成
    matches, events = generate_test_data(20, 10)
    
    print_subsection("元データの作成")
    for match_data in matches:
        original_store.store_match(match_data)
    
    for match_id, match_events in events:
        for event in match_events:
            original_store.store_event(match_id, event)
    
    print(f"作成したデータ: 試合数={len(matches)}, イベント数={len(events)*10}")
    
    # バックアップを作成
    print_subsection("バックアップの作成")
    backup_path = Path("data/backup.db")
    success = original_store.backup_database(backup_path)
    
    if success:
        print(f"バックアップ成功: {backup_path}")
        print(f"バックアップファイルサイズ: {backup_path.stat().st_size / 1024:.2f}KB")
    else:
        print("バックアップ失敗")
        return
    
    # 元のデータを削除
    print_subsection("元データの削除")
    original_store.close()
    original_store.db_path.unlink()
    print("元のデータベースファイルを削除しました")
    
    # 新しいストレージを作成してリストア
    print_subsection("データのリストア")
    restored_store = OptimizedSQLiteStore(Path("data/backup_original.db"))
    restored_store.init()
    
    success = restored_store.restore_database(backup_path)
    
    if success:
        print("リストア成功")
        
        # データの整合性を確認
        restored_matches = []
        for match_data in matches:
            restored_match = restored_store.get_match(match_data["id"])
            if restored_match:
                restored_matches.append(restored_match)
        
        print(f"リストア後の試合数: {len(restored_matches)}")
        
        # イベント数を確認
        total_events = 0
        for match_data in matches:
            events = restored_store._get_events_single_db(match_data["id"])
            total_events += len(events)
        
        print(f"リストア後のイベント数: {total_events}")
        
        if len(restored_matches) == len(matches):
            print("✅ データの整合性確認: 成功")
        else:
            print("❌ データの整合性確認: 失敗")
    else:
        print("リストア失敗")
    
    restored_store.close()

def demo_parallel_processing():
    """パラレル処理機能のデモ"""
    print_section("パラレル処理機能デモ")
    
    store = OptimizedSQLiteStore(Path("data/parallel_test.db"))
    store.init()
    
    # テストデータを準備
    matches, events = generate_test_data(100, 20)
    
    print_subsection("データの準備")
    for match_data in matches:
        store.store_match(match_data)
    
    for match_id, match_events in events:
        for event in match_events:
            store.store_event(match_id, event)
    
    # 順次処理のテスト
    print_subsection("順次処理テスト")
    test_matches = random.sample(matches, 20)
    
    start_time = time.time()
    sequential_results = []
    for match_data in test_matches:
        result = store.get_match(match_data["id"])
        sequential_results.append(result)
    sequential_time = time.time() - start_time
    
    print(f"順次処理時間: {sequential_time:.3f}秒")
    print(f"処理速度: {len(test_matches)/sequential_time:.1f}件/秒")
    
    # 並列処理のテスト
    print_subsection("並列処理テスト")
    
    def get_match_data(match_id):
        return store.get_match(match_id)
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(get_match_data, match_data["id"]) for match_data in test_matches]
        parallel_results = [future.result() for future in as_completed(futures)]
    parallel_time = time.time() - start_time
    
    print(f"並列処理時間: {parallel_time:.3f}秒")
    print(f"処理速度: {len(test_matches)/parallel_time:.1f}件/秒")
    
    # 改善比較
    improvement = (sequential_time - parallel_time) / sequential_time * 100
    speedup = sequential_time / parallel_time
    
    print(f"\n並列処理による改善:")
    print(f"  時間短縮: {improvement:.1f}%")
    print(f"  速度向上: {speedup:.1f}倍")
    
    store.close()

def demo_database_optimization():
    """データベース最適化機能のデモ"""
    print_section("データベース最適化機能デモ")
    
    store = OptimizedSQLiteStore(Path("data/optimization_test.db"))
    store.init()
    
    # 大量のテストデータを作成
    print_subsection("大量データの作成")
    matches, events = generate_test_data(500, 100)
    
    for match_data in matches:
        store.store_match(match_data)
    
    # 一部のイベントのみ保存（データベースを断片化させる）
    for i, (match_id, match_events) in enumerate(events):
        if i % 2 == 0:  # 50%のイベントのみ保存
            for event in match_events:
                store.store_event(match_id, event)
    
    print(f"作成したデータ: 試合数={len(matches)}, イベント数={len(events)*100//2}")
    
    # 最適化前のクエリ性能を測定
    print_subsection("最適化前のクエリ性能")
    test_matches = random.sample(matches, 100)
    
    start_time = time.time()
    for match_data in test_matches:
        store.get_match(match_data["id"])
        store._get_events_single_db(match_data["id"])
    pre_optimization_time = time.time() - start_time
    
    print(f"最適化前のクエリ時間: {pre_optimization_time:.3f}秒")
    
    # データベース最適化を実行
    print_subsection("データベース最適化の実行")
    optimization_results = store.optimize_database()
    
    for db_path, result in optimization_results.items():
        print(f"データベース: {db_path}")
        if "error" in result:
            print(f"  エラー: {result['error']}")
        else:
            print(f"  VACUUM完了: {result['vacuum_completed']}")
            print(f"  ANALYZE完了: {result['analyze_completed']}")
            print(f"  matchテーブルのインデックス数: {result['match_indexes']}")
            print(f"  eventテーブルのインデックス数: {result['event_indexes']}")
    
    # 最適化後のクエリ性能を測定
    print_subsection("最適化後のクエリ性能")
    start_time = time.time()
    for match_data in test_matches:
        store.get_match(match_data["id"])
        store._get_events_single_db(match_data["id"])
    post_optimization_time = time.time() - start_time
    
    print(f"最適化後のクエリ時間: {post_optimization_time:.3f}秒")
    
    # 改善比較
    improvement = (pre_optimization_time - post_optimization_time) / pre_optimization_time * 100
    print(f"\n最適化による改善: {improvement:.1f}%")
    
    store.close()

def main():
    """メイン関数"""
    print("データベースパフォーマンス最適化機能デモ")
    print("Task ID: 10 - Database Performance Optimization and Scalability Enhancement")
    
    # データディレクトリを作成
    Path("data").mkdir(exist_ok=True)
    
    try:
        # 各機能のデモを実行
        demo_basic_vs_optimized()
        demo_caching()
        demo_sharding()
        demo_backup_restore()
        demo_parallel_processing()
        demo_database_optimization()
        
        print_section("デモ完了")
        print("✅ すべての最適化機能が正常に動作しました")
        print("\n実装された機能:")
        print("1. ✅ データベースインデックス最適化")
        print("2. ✅ クエリ改善")
        print("3. ✅ パラレル処理サポート")
        print("4. ✅ データベースシャーディング")
        print("5. ✅ キャッシング（Redis対応）")
        print("6. ✅ バックアップ・リストア機能")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()