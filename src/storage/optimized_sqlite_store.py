"""
最適化されたSQLiteストレージモジュール

データベースパフォーマンス最適化とスケーラビリティ向上機能を含む
- インデックス最適化
- クエリ改善
- パラレル処理サポート
- キャッシング（Redis）
- バックアップ・リストア機能
"""

import sqlite3
import json
import time
import threading
import hashlib
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
import logging

# Redisのインポートを追加（オプション）
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheType(Enum):
    """キャッシュタイプの定義"""
    MEMORY = "memory"
    REDIS = "redis"


@dataclass
class QueryPerformanceMetrics:
    """クエリパフォーマンスメトリクス"""
    query: str
    execution_time: float
    rows_affected: int
    timestamp: datetime


@dataclass
class DatabaseShardConfig:
    """データベースシャード設定"""
    shard_id: str
    db_path: Path
    weight: float = 1.0
    active: bool = True


class ConsistentHashRing:
    """一貫性ハッシュリング実装"""
    
    def __init__(self, nodes: List[str], replicas: int = 100):
        self.nodes = nodes
        self.replicas = replicas
        self.ring = {}
        self._build_ring()
    
    def _build_ring(self):
        """ハッシュリングを構築"""
        self.ring.clear()
        for node in self.nodes:
            for i in range(self.replicas):
                key = hashlib.md5(f"{node}:{i}".encode()).hexdigest()
                self.ring[key] = node
    
    def get_node(self, key: str) -> str:
        """キーに対応するノードを取得"""
        if not self.ring:
            raise ValueError("Hash ring is empty")
        
        hash_key = hashlib.md5(key.encode()).hexdigest()
        
        # リング上で最も近いノードを見つける
        keys = sorted(self.ring.keys())
        for ring_key in keys:
            if hash_key <= ring_key:
                return self.ring[ring_key]
        
        # リング上の最初のノードを返す
        return self.ring[keys[0]]
    
    def add_node(self, node: str):
        """ノードを追加"""
        if node not in self.nodes:
            self.nodes.append(node)
            self._build_ring()
    
    def remove_node(self, node: str):
        """ノードを削除"""
        if node in self.nodes:
            self.nodes.remove(node)
            self._build_ring()


class CacheManager:
    """キャッシュマネージャー"""
    
    def __init__(self, cache_type: CacheType = CacheType.MEMORY, 
                 redis_host: str = "localhost", redis_port: int = 6379):
        self.cache_type = cache_type
        self.memory_cache = {}
        self.cache_stats = {"hits": 0, "misses": 0}
        self.redis_client = None
        
        if cache_type == CacheType.REDIS and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
                self.redis_client.ping()
                logger.info("Redis接続が確立されました")
            except Exception as e:
                logger.warning(f"Redis接続に失敗しました: {e}")
                self.cache_type = CacheType.MEMORY
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュからデータを取得"""
        try:
            if self.cache_type == CacheType.REDIS and self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    self.cache_stats["hits"] += 1
                    return json.loads(value)
            else:
                if key in self.memory_cache:
                    self.cache_stats["hits"] += 1
                    return self.memory_cache[key]
            
            self.cache_stats["misses"] += 1
            return None
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: int = 3600):
        """キャッシュにデータを保存"""
        try:
            if self.cache_type == CacheType.REDIS and self.redis_client:
                self.redis_client.setex(key, expire, json.dumps(value))
            else:
                self.memory_cache[key] = value
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
    
    def invalidate(self, key: str):
        """キャッシュを無効化"""
        try:
            if self.cache_type == CacheType.REDIS and self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_cache.pop(key, None)
        except Exception as e:
            logger.error(f"キャッシュ無効化エラー: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = self.cache_stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


class OptimizedSQLiteStore:
    """最適化されたSQLiteストレージクラス"""
    
    def __init__(self, db_path: Path, 
                 enable_sharding: bool = False,
                 shard_configs: Optional[List[DatabaseShardConfig]] = None,
                 cache_type: CacheType = CacheType.MEMORY,
                 max_connections: int = 10):
        """
        最適化されたSQLiteストレージを初期化
        
        Args:
            db_path: メインデータベースファイルのパス
            enable_sharding: シャーディングを有効にするかどうか
            shard_configs: シャード設定のリスト
            cache_type: キャッシュタイプ
            max_connections: 最大接続数
        """
        self.db_path = db_path
        self.enable_sharding = enable_sharding
        self.shard_configs = shard_configs or []
        self.cache_manager = CacheManager(cache_type)
        self.max_connections = max_connections
        self.connection_pool = ThreadPoolExecutor(max_workers=max_connections)
        self.performance_metrics = []
        self.hash_ring = None
        
        # シャーディングが有効な場合、ハッシュリングを初期化
        if self.enable_sharding and self.shard_configs:
            shard_ids = [config.shard_id for config in self.shard_configs if config.active]
            self.hash_ring = ConsistentHashRing(shard_ids)
    
    def init(self):
        """データベースを初期化（インデックス最適化を含む）"""
        self._init_main_db()
        if self.enable_sharding:
            self._init_shards()
    
    def _init_main_db(self):
        """メインデータベースを初期化"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection(self.db_path) as conn:
            cur = conn.cursor()
            
            # テーブル作成
            cur.execute("""
            CREATE TABLE IF NOT EXISTS match (
                id       TEXT PRIMARY KEY,
                title    TEXT,
                patch    TEXT,
                ts       TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            cur.execute("""
            CREATE TABLE IF NOT EXISTS event (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT,
                ts       REAL,
                event    TEXT,
                actor    TEXT,
                target   TEXT,
                meta     TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            # パフォーマンスメトリクステーブル
            cur.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT,
                execution_time REAL,
                rows_affected INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            # インデックス最適化
            self._create_optimized_indexes(cur)
            
            # データベース設定の最適化
            cur.execute("PRAGMA journal_mode = WAL")  # WALモードで同時読み書き性能向上
            cur.execute("PRAGMA synchronous = NORMAL")  # 同期レベルを調整
            cur.execute("PRAGMA cache_size = 10000")  # キャッシュサイズを増加
            cur.execute("PRAGMA temp_store = MEMORY")  # 一時データをメモリに保存
            cur.execute("PRAGMA mmap_size = 268435456")  # メモリマップサイズを設定（256MB）
            
            conn.commit()
    
    def _create_optimized_indexes(self, cursor):
        """最適化されたインデックスを作成"""
        indexes = [
            # 頻繁にクエリされるカラムのインデックス
            "CREATE INDEX IF NOT EXISTS idx_event_match_id ON event(match_id)",
            "CREATE INDEX IF NOT EXISTS idx_event_ts ON event(ts)",
            "CREATE INDEX IF NOT EXISTS idx_event_actor ON event(actor)",
            "CREATE INDEX IF NOT EXISTS idx_event_target ON event(target)",
            "CREATE INDEX IF NOT EXISTS idx_event_event_type ON event(event)",
            "CREATE INDEX IF NOT EXISTS idx_match_ts ON match(ts)",
            "CREATE INDEX IF NOT EXISTS idx_match_patch ON match(patch)",
            
            # 複合インデックス
            "CREATE INDEX IF NOT EXISTS idx_event_match_ts ON event(match_id, ts)",
            "CREATE INDEX IF NOT EXISTS idx_event_actor_ts ON event(actor, ts)",
            "CREATE INDEX IF NOT EXISTS idx_event_target_ts ON event(target, ts)",
            "CREATE INDEX IF NOT EXISTS idx_event_type_ts ON event(event, ts)",
            
            # パフォーマンスメトリクス用インデックス
            "CREATE INDEX IF NOT EXISTS idx_performance_query_hash ON performance_metrics(query_hash)",
            "CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp)",
        ]
        
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                logger.info(f"インデックス作成: {index_sql}")
            except sqlite3.Error as e:
                logger.warning(f"インデックス作成エラー: {e}")
    
    def _init_shards(self):
        """シャードを初期化"""
        for shard_config in self.shard_configs:
            if shard_config.active:
                shard_config.db_path.parent.mkdir(parents=True, exist_ok=True)
                
                with self._get_connection(shard_config.db_path) as conn:
                    cur = conn.cursor()
                    
                    # シャード用のテーブル作成（同じスキーマ）
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS match (
                        id       TEXT PRIMARY KEY,
                        title    TEXT,
                        patch    TEXT,
                        ts       TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """)
                    
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS event (
                        id       INTEGER PRIMARY KEY AUTOINCREMENT,
                        match_id TEXT,
                        ts       REAL,
                        event    TEXT,
                        actor    TEXT,
                        target   TEXT,
                        meta     TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """)
                    
                    # 最適化されたインデックスを作成
                    self._create_optimized_indexes(cur)
                    
                    # 最適化設定
                    cur.execute("PRAGMA journal_mode = WAL")
                    cur.execute("PRAGMA synchronous = NORMAL")
                    cur.execute("PRAGMA cache_size = 10000")
                    cur.execute("PRAGMA temp_store = MEMORY")
                    
                    conn.commit()
    
    @contextmanager
    def _get_connection(self, db_path: Path):
        """データベース接続のコンテキストマネージャー"""
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()
    
    def _get_shard_db_path(self, key: str) -> Path:
        """キーに基づいてシャードデータベースのパスを取得"""
        if not self.enable_sharding or not self.hash_ring:
            return self.db_path
        
        shard_id = self.hash_ring.get_node(key)
        shard_config = next((config for config in self.shard_configs 
                           if config.shard_id == shard_id and config.active), None)
        
        return shard_config.db_path if shard_config else self.db_path
    
    def _record_performance(self, query: str, execution_time: float, rows_affected: int):
        """パフォーマンスメトリクスを記録"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        metric = QueryPerformanceMetrics(
            query=query,
            execution_time=execution_time,
            rows_affected=rows_affected,
            timestamp=datetime.now()
        )
        
        self.performance_metrics.append(metric)
        
        # データベースにも記録
        with self._get_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO performance_metrics (query_hash, execution_time, rows_affected)
            VALUES (?, ?, ?)
            """, (query_hash, execution_time, rows_affected))
            conn.commit()
    
    def store_match(self, match_data: Dict[str, Any]) -> None:
        """試合データを保存（最適化版）"""
        cache_key = f"match:{match_data['id']}"
        
        # キャッシュを無効化
        self.cache_manager.invalidate(cache_key)
        
        # シャードを決定
        db_path = self._get_shard_db_path(match_data['id'])
        
        start_time = time.time()
        
        with self._get_connection(db_path) as conn:
            cur = conn.cursor()
            
            query = """
            INSERT OR REPLACE INTO match (id, title, patch, ts)
            VALUES (?, ?, ?, ?)
            """
            
            cur.execute(query, (
                match_data["id"],
                match_data["title"],
                match_data["patch"],
                match_data["timestamp"]
            ))
            
            conn.commit()
            
            # パフォーマンスメトリクスを記録
            execution_time = time.time() - start_time
            self._record_performance(query, execution_time, cur.rowcount)
        
        # キャッシュに保存
        self.cache_manager.set(cache_key, match_data)
    
    def store_event(self, match_id: str, event) -> None:
        """イベントデータを保存（最適化版）"""
        # シャードを決定
        db_path = self._get_shard_db_path(match_id)
        
        start_time = time.time()
        
        with self._get_connection(db_path) as conn:
            cur = conn.cursor()
            
            query = """
            INSERT INTO event (match_id, ts, event, actor, target, meta)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            
            row_data = event.to_row(match_id)
            cur.execute(query, row_data)
            
            conn.commit()
            
            # パフォーマンスメトリクスを記録
            execution_time = time.time() - start_time
            self._record_performance(query, execution_time, cur.rowcount)
        
        # 関連するキャッシュを無効化
        self.cache_manager.invalidate(f"events:{match_id}")
    
    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """試合データを取得（キャッシュ機能付き）"""
        cache_key = f"match:{match_id}"
        
        # キャッシュから試行
        cached_result = self.cache_manager.get(cache_key)
        if cached_result:
            return cached_result
        
        # シャードを決定
        db_path = self._get_shard_db_path(match_id)
        
        start_time = time.time()
        
        with self._get_connection(db_path) as conn:
            cur = conn.cursor()
            
            query = "SELECT * FROM match WHERE id = ?"
            cur.execute(query, (match_id,))
            result = cur.fetchone()
            
            # パフォーマンスメトリクスを記録
            execution_time = time.time() - start_time
            self._record_performance(query, execution_time, 1 if result else 0)
        
        if result:
            match_data = {
                "id": result[0],
                "title": result[1],
                "patch": result[2],
                "timestamp": result[3]
            }
            
            # キャッシュに保存
            self.cache_manager.set(cache_key, match_data)
            
            return match_data
        
        return None
    
    def get_events_for_match_parallel(self, match_id: str) -> List:
        """特定の試合のイベントを並列で取得"""
        cache_key = f"events:{match_id}"
        
        # キャッシュから試行
        cached_result = self.cache_manager.get(cache_key)
        if cached_result:
            return cached_result
        
        if not self.enable_sharding:
            return self._get_events_single_db(match_id)
        
        # 全シャードから並列でイベントを取得
        future_to_shard = {}
        
        for shard_config in self.shard_configs:
            if shard_config.active:
                future = self.connection_pool.submit(
                    self._get_events_single_db, match_id, shard_config.db_path
                )
                future_to_shard[future] = shard_config.shard_id
        
        all_events = []
        for future in as_completed(future_to_shard):
            try:
                events = future.result()
                all_events.extend(events)
            except Exception as e:
                logger.error(f"シャード {future_to_shard[future]} からのイベント取得エラー: {e}")
        
        # タイムスタンプでソート
        all_events.sort(key=lambda x: x.timestamp)
        
        # キャッシュに保存
        self.cache_manager.set(cache_key, all_events)
        
        return all_events
    
    def _get_events_single_db(self, match_id: str, db_path: Path = None) -> List:
        """単一データベースからイベントを取得"""
        if db_path is None:
            db_path = self._get_shard_db_path(match_id)
        
        # 動的インポート
        try:
            from canonizer.event import Event
        except ImportError:
            import sys
            import os
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            from canonizer.event import Event
        
        start_time = time.time()
        
        with self._get_connection(db_path) as conn:
            cur = conn.cursor()
            
            query = "SELECT * FROM event WHERE match_id = ? ORDER BY ts"
            cur.execute(query, (match_id,))
            results = cur.fetchall()
            
            # パフォーマンスメトリクスを記録
            execution_time = time.time() - start_time
            self._record_performance(query, execution_time, len(results))
        
        events = []
        for row in results:
            event = Event(
                timestamp=row[2],
                event=row[3],
                actor=row[4],
                target=row[5],
                meta=json.loads(row[6]) if row[6] else {}
            )
            events.append(event)
        
        return events
    
    def backup_database(self, backup_path: Path) -> bool:
        """データベースをバックアップ"""
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # メインデータベースのバックアップ
            if self.db_path.exists():
                shutil.copy2(self.db_path, backup_path)
                logger.info(f"メインデータベースをバックアップ: {backup_path}")
            
            # シャードのバックアップ
            if self.enable_sharding:
                for shard_config in self.shard_configs:
                    if shard_config.active and shard_config.db_path.exists():
                        shard_backup_path = backup_path.parent / f"{backup_path.stem}_{shard_config.shard_id}.db"
                        shutil.copy2(shard_config.db_path, shard_backup_path)
                        logger.info(f"シャード {shard_config.shard_id} をバックアップ: {shard_backup_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"バックアップエラー: {e}")
            return False
    
    def restore_database(self, backup_path: Path) -> bool:
        """データベースをリストア"""
        try:
            if not backup_path.exists():
                logger.error(f"バックアップファイルが見つかりません: {backup_path}")
                return False
            
            # メインデータベースのリストア
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"メインデータベースをリストア: {self.db_path}")
            
            # シャードのリストア
            if self.enable_sharding:
                for shard_config in self.shard_configs:
                    if shard_config.active:
                        shard_backup_path = backup_path.parent / f"{backup_path.stem}_{shard_config.shard_id}.db"
                        if shard_backup_path.exists():
                            shutil.copy2(shard_backup_path, shard_config.db_path)
                            logger.info(f"シャード {shard_config.shard_id} をリストア: {shard_config.db_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"リストアエラー: {e}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """パフォーマンス統計を取得"""
        if not self.performance_metrics:
            return {"message": "パフォーマンスデータがありません"}
        
        execution_times = [metric.execution_time for metric in self.performance_metrics]
        
        stats = {
            "total_queries": len(self.performance_metrics),
            "avg_execution_time": sum(execution_times) / len(execution_times),
            "max_execution_time": max(execution_times),
            "min_execution_time": min(execution_times),
            "cache_stats": self.cache_manager.get_stats(),
            "recent_slow_queries": [
                {
                    "query": metric.query,
                    "execution_time": metric.execution_time,
                    "timestamp": metric.timestamp.isoformat()
                }
                for metric in sorted(self.performance_metrics, 
                                   key=lambda x: x.execution_time, reverse=True)[:5]
            ]
        }
        
        return stats
    
    def optimize_database(self) -> Dict[str, Any]:
        """データベースを最適化"""
        optimization_results = {}
        
        databases = [self.db_path]
        if self.enable_sharding:
            databases.extend([config.db_path for config in self.shard_configs if config.active])
        
        for db_path in databases:
            try:
                with self._get_connection(db_path) as conn:
                    cur = conn.cursor()
                    
                    # VACUUM実行
                    cur.execute("VACUUM")
                    
                    # 統計情報更新
                    cur.execute("ANALYZE")
                    
                    # インデックスの使用状況を確認
                    cur.execute("PRAGMA index_list(match)")
                    match_indexes = cur.fetchall()
                    
                    cur.execute("PRAGMA index_list(event)")
                    event_indexes = cur.fetchall()
                    
                    optimization_results[str(db_path)] = {
                        "vacuum_completed": True,
                        "analyze_completed": True,
                        "match_indexes": len(match_indexes),
                        "event_indexes": len(event_indexes)
                    }
                    
                    logger.info(f"データベース最適化完了: {db_path}")
                    
            except Exception as e:
                logger.error(f"データベース最適化エラー {db_path}: {e}")
                optimization_results[str(db_path)] = {"error": str(e)}
        
        return optimization_results
    
    def close(self):
        """リソースを解放"""
        self.connection_pool.shutdown(wait=True)
        if hasattr(self.cache_manager, 'redis_client') and self.cache_manager.redis_client:
            self.cache_manager.redis_client.close()