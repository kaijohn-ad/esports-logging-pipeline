#!/usr/bin/env python3
"""
LoL APIエラーハンドリング機能のデモンストレーション

このサンプルコードは、強化されたAPIエラーハンドリング機能の
使用方法を示します。
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトのsrcディレクトリをパスに追加
sys.path.append(str(Path(__file__).parent.parent / "src"))

from collectors.lol_fetcher import LoLFetcher, APIRateLimitError, APIQuotaExceededError
from config.lol_config import LoLConfig, ErrorHandlingConfig, APIConfig


def create_demo_config() -> LoLConfig:
    """デモ用の設定を作成"""
    return LoLConfig(
        api=APIConfig(
            riot_api_key="DEMO_KEY",  # 実際のAPIキーに置き換えてください
            riot_region="jp1",
            rate_limit={
                "max_requests": 20,
                "time_window": 120
            }
        ),
        error_handling=ErrorHandlingConfig(
            # Slack通知設定
            slack_webhook_url=None,  # Slack webhook URLを設定してください
            slack_notifications_enabled=True,
            
            # リトライ設定
            max_retries=3,
            retry_delay_base=2.0,
            
            # ログ設定
            structured_logging=True,
            log_level="INFO",
            log_to_file=True,
            log_file_path="logs/lol_fetcher_demo.log",
            
            # メトリクス設定
            collect_metrics=True,
            metrics_retention_hours=24,
            
            # エラー閾値設定
            error_rate_threshold=10.0,
            critical_error_threshold=3,
            
            # 通知対象エラー
            notify_on_errors=[429, 500, 502, 503, 504],
            
            # レート制限対応
            respect_rate_limits=True,
            adaptive_rate_limiting=True
        )
    )


async def demo_basic_error_handling():
    """基本的なエラーハンドリングのデモ"""
    print("=== 基本的なエラーハンドリングのデモ ===")
    
    config = create_demo_config()
    fetcher = LoLFetcher("DEMO_KEY", region="jp1", config=config)
    
    try:
        # 存在しないマッチIDでエラーを意図的に発生させる
        result = await fetcher.fetch_match_details_safe("INVALID_MATCH_ID")
        print(f"結果: {result}")
    except Exception as e:
        print(f"エラーをキャッチしました: {type(e).__name__} - {e}")
    
    # エラー統計を表示
    stats = fetcher.get_error_statistics()
    print(f"エラー統計: {stats}")


async def demo_custom_exceptions():
    """カスタム例外のデモ"""
    print("\n=== カスタム例外のデモ ===")
    
    config = create_demo_config()
    fetcher = LoLFetcher("DEMO_KEY", region="jp1", config=config)
    
    try:
        # 拡張エラーハンドリングでカスタム例外を使用
        result = await fetcher.fetch_with_enhanced_error_handling(
            fetcher.watch.match.by_id, "jp1", "INVALID_MATCH_ID"
        )
    except APIRateLimitError as e:
        print(f"レート制限エラー: {e}")
    except APIQuotaExceededError as e:
        print(f"API割当量超過エラー: {e}")
    except Exception as e:
        print(f"その他のエラー: {type(e).__name__} - {e}")


def demo_configuration():
    """設定機能のデモ"""
    print("\n=== 設定機能のデモ ===")
    
    config = create_demo_config()
    fetcher = LoLFetcher("DEMO_KEY", region="jp1", config=config)
    
    print(f"最大リトライ回数: {fetcher.max_retries}")
    print(f"リトライ遅延ベース: {fetcher.retry_delay_base}")
    print(f"通知対象エラー: {fetcher.notify_on_errors}")
    
    # Slack webhook URLを動的に設定
    fetcher.set_slack_webhook("https://hooks.slack.com/services/DEMO/DEMO/DEMO")
    print(f"Slack webhook URL: {fetcher.slack_webhook_url}")


async def demo_metrics_collection():
    """メトリクス収集のデモ"""
    print("\n=== メトリクス収集のデモ ===")
    
    config = create_demo_config()
    fetcher = LoLFetcher("DEMO_KEY", region="jp1", config=config)
    
    # 複数回のAPI呼び出しでメトリクスを生成
    for i in range(3):
        try:
            await fetcher.fetch_match_details_safe(f"INVALID_MATCH_{i}")
        except Exception:
            pass  # エラーは無視してメトリクスの蓄積を続ける
    
    # メトリクス統計を表示
    stats = fetcher.get_error_statistics()
    print("メトリクス統計:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


def demo_config_variations():
    """設定のバリエーションのデモ"""
    print("\n=== 設定のバリエーションのデモ ===")
    
    # 本番環境向け設定
    production_config = LoLConfig(
        error_handling=ErrorHandlingConfig(
            structured_logging=True,
            log_to_file=True,
            collect_metrics=True,
            slack_notifications_enabled=True,
            error_rate_threshold=5.0,  # より厳しい閾値
            critical_error_threshold=2,
            max_retries=5
        )
    )
    
    # 開発環境向け設定
    development_config = LoLConfig(
        error_handling=ErrorHandlingConfig(
            structured_logging=False,
            log_to_file=False,
            collect_metrics=False,
            slack_notifications_enabled=False,
            max_retries=2
        )
    )
    
    print("本番環境設定:")
    print(f"  構造化ログ: {production_config.error_handling.structured_logging}")
    print(f"  メトリクス収集: {production_config.error_handling.collect_metrics}")
    print(f"  最大リトライ: {production_config.error_handling.max_retries}")
    
    print("開発環境設定:")
    print(f"  構造化ログ: {development_config.error_handling.structured_logging}")
    print(f"  メトリクス収集: {development_config.error_handling.collect_metrics}")
    print(f"  最大リトライ: {development_config.error_handling.max_retries}")


async def main():
    """メインのデモ実行関数"""
    print("LoL APIエラーハンドリング機能デモ")
    print("=" * 50)
    
    # 設定のデモ
    demo_configuration()
    demo_config_variations()
    
    # 実際のAPIコール（API キーが有効な場合のみ）
    print("\n注意: 以下のデモは有効なRiot Games APIキーが必要です")
    print("API キーを設定してからコメントアウトを解除してください")
    
    # await demo_basic_error_handling()
    # await demo_custom_exceptions()
    # await demo_metrics_collection()
    
    print("\nデモ完了！")


if __name__ == "__main__":
    asyncio.run(main())