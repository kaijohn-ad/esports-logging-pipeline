"""
League of Legends 設定モジュール

LoL関連の設定を管理する
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class APIConfig(BaseModel):
    """API設定クラス"""
    riot_api_key: str = ""
    openrouter_api_key: str = ""
    riot_region: str = "jp1"
    rate_limit: Dict[str, int] = Field(default_factory=lambda: {
        "max_requests": 20,
        "time_window": 120
    })


class PlayerConfig(BaseModel):
    """プレイヤー設定クラス"""
    summoner_name: str = ""
    puuid: str = ""
    default_region: str = "jp1"
    tracked_champions: List[str] = Field(default_factory=list)


class ErrorHandlingConfig(BaseModel):
    """エラーハンドリング設定クラス"""
    # Slack通知設定
    slack_webhook_url: Optional[str] = None
    slack_notifications_enabled: bool = False
    
    # リトライ設定
    max_retries: int = 3
    retry_delay_base: float = 2.0  # 指数バックオフのベース秒数
    
    # ログ設定
    structured_logging: bool = True
    log_level: str = "INFO"
    log_to_file: bool = False
    log_file_path: str = "logs/lol_fetcher.log"
    
    # メトリクス設定
    collect_metrics: bool = True
    metrics_retention_hours: int = 24
    
    # エラー閾値設定
    error_rate_threshold: float = 10.0  # エラー率の閾値（%）
    critical_error_threshold: int = 5   # 重要エラーの閾値（連続回数）
    
    # 通知対象エラー
    notify_on_errors: List[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    
    # レート制限対応
    respect_rate_limits: bool = True
    adaptive_rate_limiting: bool = True  # 動的レート制限調整


class MonitoringConfig(BaseModel):
    """監視・アラート設定クラス"""
    enabled: bool = False
    health_check_interval: int = 300  # 5分
    alert_channels: List[str] = Field(default_factory=list)  # Slack, Email, etc.
    
    # ヘルスチェック項目
    check_api_response_time: bool = True
    response_time_threshold: float = 2.0  # 秒
    
    check_error_rate: bool = True
    error_rate_threshold: float = 5.0  # %
    
    check_rate_limit_usage: bool = True
    rate_limit_usage_threshold: float = 80.0  # %


class LoLConfig(BaseModel):
    """LoL総合設定クラス"""
    api: APIConfig = Field(default_factory=APIConfig)
    player: PlayerConfig = Field(default_factory=PlayerConfig)
    error_handling: ErrorHandlingConfig = Field(default_factory=ErrorHandlingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)