"""
通知管理モジュール

スケジューラーの実行結果を通知
"""

import json
import logging
import smtplib
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

from .data_collector import DataCollectionResult
from .trend_analyzer import TrendAnalysisResult
from ..config.lol_config import LoLConfig


class NotificationResult:
    """通知結果クラス"""
    
    def __init__(self):
        self.success: bool = True
        self.messages: List[str] = []
        self.channels_used: List[str] = []
        self.errors: List[str] = []
        self.timestamp: datetime = datetime.now()
    
    def add_success(self, channel: str, message: str):
        """成功メッセージを追加"""
        self.channels_used.append(channel)
        self.messages.append(f"[{channel}] {message}")
    
    def add_error(self, channel: str, error: str):
        """エラーメッセージを追加"""
        self.success = False
        self.errors.append(f"[{channel}] {error}")
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "success": self.success,
            "messages": self.messages,
            "channels_used": self.channels_used,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat()
        }


class NotificationManager:
    """通知管理クラス"""
    
    def __init__(self, config: LoLConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 通知レポート保存ディレクトリ
        self.reports_dir = Path("data/reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # 通知テンプレート
        self.templates = {
            "data_collection": {
                "subject": "データ収集レポート - {date}",
                "body": """
データ収集が完了しました。

実行時間: {duration}
処理プレイヤー数: {players_processed}
収集マッチ数: {collected_matches}
収集イベント数: {collected_events}
エラー数: {error_count}

{details}
                """.strip()
            },
            "trend_analysis": {
                "subject": "トレンド分析レポート - {date}",
                "body": """
トレンド分析が完了しました。

分析プレイヤー数: {total_players}
改善傾向: {improving_players}名
低下傾向: {declining_players}名
安定傾向: {stable_players}名

平均パフォーマンススコア: {average_score}

{details}
                """.strip()
            },
            "scheduler_error": {
                "subject": "スケジューラーエラー - {date}",
                "body": """
スケジューラーでエラーが発生しました。

エラー内容: {error_message}
発生時刻: {timestamp}
ジョブ名: {job_name}

{details}
                """.strip()
            }
        }
    
    def notify_data_collection_complete(self, result: DataCollectionResult) -> NotificationResult:
        """データ収集完了通知"""
        notification_result = NotificationResult()
        
        try:
            # 通知データの準備
            notification_data = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "duration": str(result.get_duration()),
                "players_processed": result.players_processed,
                "collected_matches": result.collected_matches,
                "collected_events": result.collected_events,
                "error_count": len(result.errors),
                "details": self._format_collection_details(result)
            }
            
            # 各通知チャンネルに送信
            for channel in self.config.scheduler.notification_channels:
                try:
                    if channel == "console":
                        self._notify_console(notification_data, "data_collection")
                        notification_result.add_success("console", "コンソール通知完了")
                    
                    elif channel == "file":
                        self._notify_file(notification_data, "data_collection")
                        notification_result.add_success("file", "ファイル通知完了")
                    
                    elif channel == "slack":
                        self._notify_slack(notification_data, "data_collection")
                        notification_result.add_success("slack", "Slack通知完了")
                    
                    elif channel == "email":
                        self._notify_email(notification_data, "data_collection")
                        notification_result.add_success("email", "Email通知完了")
                    
                except Exception as e:
                    error_msg = f"通知送信エラー: {str(e)}"
                    self.logger.error(error_msg)
                    notification_result.add_error(channel, error_msg)
            
            return notification_result
            
        except Exception as e:
            self.logger.error(f"通知処理中にエラーが発生: {e}")
            notification_result.add_error("system", f"通知処理エラー: {str(e)}")
            return notification_result
    
    def notify_trend_analysis_complete(self, results: List[TrendAnalysisResult], 
                                     summary: Dict[str, Any]) -> NotificationResult:
        """トレンド分析完了通知"""
        notification_result = NotificationResult()
        
        try:
            # 通知データの準備
            notification_data = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "total_players": summary["total_players"],
                "improving_players": summary["improving_players"],
                "declining_players": summary["declining_players"],
                "stable_players": summary["stable_players"],
                "average_score": summary["average_performance_score"],
                "details": self._format_trend_details(results, summary)
            }
            
            # 各通知チャンネルに送信
            for channel in self.config.scheduler.notification_channels:
                try:
                    if channel == "console":
                        self._notify_console(notification_data, "trend_analysis")
                        notification_result.add_success("console", "コンソール通知完了")
                    
                    elif channel == "file":
                        self._notify_file(notification_data, "trend_analysis")
                        notification_result.add_success("file", "ファイル通知完了")
                    
                    elif channel == "slack":
                        self._notify_slack(notification_data, "trend_analysis")
                        notification_result.add_success("slack", "Slack通知完了")
                    
                    elif channel == "email":
                        self._notify_email(notification_data, "trend_analysis")
                        notification_result.add_success("email", "Email通知完了")
                    
                except Exception as e:
                    error_msg = f"通知送信エラー: {str(e)}"
                    self.logger.error(error_msg)
                    notification_result.add_error(channel, error_msg)
            
            return notification_result
            
        except Exception as e:
            self.logger.error(f"通知処理中にエラーが発生: {e}")
            notification_result.add_error("system", f"通知処理エラー: {str(e)}")
            return notification_result
    
    def notify_scheduler_error(self, error_message: str, job_name: str = "unknown", 
                             details: str = "") -> NotificationResult:
        """スケジューラーエラー通知"""
        notification_result = NotificationResult()
        
        try:
            # 通知データの準備
            notification_data = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "error_message": error_message,
                "timestamp": datetime.now().isoformat(),
                "job_name": job_name,
                "details": details
            }
            
            # 緊急性の高いエラー通知なので、すべてのチャンネルに送信
            for channel in self.config.scheduler.notification_channels:
                try:
                    if channel == "console":
                        self._notify_console(notification_data, "scheduler_error")
                        notification_result.add_success("console", "エラー通知完了")
                    
                    elif channel == "file":
                        self._notify_file(notification_data, "scheduler_error")
                        notification_result.add_success("file", "エラーログ記録完了")
                    
                    elif channel == "slack":
                        self._notify_slack(notification_data, "scheduler_error")
                        notification_result.add_success("slack", "Slackエラー通知完了")
                    
                    elif channel == "email":
                        self._notify_email(notification_data, "scheduler_error")
                        notification_result.add_success("email", "Emailエラー通知完了")
                    
                except Exception as e:
                    error_msg = f"エラー通知送信失敗: {str(e)}"
                    self.logger.error(error_msg)
                    notification_result.add_error(channel, error_msg)
            
            return notification_result
            
        except Exception as e:
            self.logger.error(f"エラー通知処理中に例外発生: {e}")
            notification_result.add_error("system", f"エラー通知処理失敗: {str(e)}")
            return notification_result
    
    def _notify_console(self, data: Dict[str, Any], template_name: str):
        """コンソール通知"""
        template = self.templates[template_name]
        message = template["body"].format(**data)
        
        print(f"\n{'='*60}")
        print(f"📊 {template['subject'].format(**data)}")
        print(f"{'='*60}")
        print(message)
        print(f"{'='*60}\n")
    
    def _notify_file(self, data: Dict[str, Any], template_name: str):
        """ファイル通知"""
        template = self.templates[template_name]
        
        # ファイル名生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{template_name}_{timestamp}.txt"
        filepath = self.reports_dir / filename
        
        # ファイルに書き込み
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Subject: {template['subject'].format(**data)}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
            f.write(template["body"].format(**data))
            f.write(f"\n{'='*60}\n")
        
        self.logger.info(f"レポートファイル作成: {filepath}")
    
    def _notify_slack(self, data: Dict[str, Any], template_name: str):
        """Slack通知"""
        if not self.config.error_handling.slack_webhook_url:
            raise ValueError("Slack webhook URL が設定されていません")
        
        template = self.templates[template_name]
        
        # Slack用メッセージ作成
        slack_message = {
            "text": template["subject"].format(**data),
            "attachments": [
                {
                    "color": "good" if template_name != "scheduler_error" else "danger",
                    "fields": [
                        {
                            "title": "詳細",
                            "value": template["body"].format(**data),
                            "short": False
                        }
                    ],
                    "footer": "eSports Logger",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }
        
        # Slack API に送信
        response = requests.post(
            self.config.error_handling.slack_webhook_url,
            json=slack_message,
            timeout=10
        )
        
        if response.status_code != 200:
            raise ValueError(f"Slack通知送信失敗: {response.status_code}")
        
        self.logger.info("Slack通知送信完了")
    
    def _notify_email(self, data: Dict[str, Any], template_name: str):
        """Email通知"""
        # Email設定の確認
        email_config = getattr(self.config, 'email', None)
        if not email_config:
            raise ValueError("Email設定が見つかりません")
        
        template = self.templates[template_name]
        
        # メール作成
        msg = MimeMultipart()
        msg['From'] = email_config.sender
        msg['To'] = email_config.recipient
        msg['Subject'] = template["subject"].format(**data)
        
        # メール本文
        body = template["body"].format(**data)
        msg.attach(MimeText(body, 'plain', 'utf-8'))
        
        # SMTP送信
        server = smtplib.SMTP(email_config.smtp_server, email_config.smtp_port)
        server.starttls()
        server.login(email_config.username, email_config.password)
        
        text = msg.as_string()
        server.sendmail(email_config.sender, email_config.recipient, text)
        server.quit()
        
        self.logger.info("Email通知送信完了")
    
    def _format_collection_details(self, result: DataCollectionResult) -> str:
        """データ収集詳細をフォーマット"""
        details = []
        
        if result.success:
            details.append("✅ 収集処理が正常に完了しました")
        else:
            details.append("❌ 収集処理中にエラーが発生しました")
        
        if result.players_failed > 0:
            details.append(f"⚠️ {result.players_failed}名のプレイヤーで処理に失敗しました")
        
        if result.errors:
            details.append("\n【エラー詳細】")
            for error in result.errors[:5]:  # 最大5件まで表示
                details.append(f"  • {error}")
            if len(result.errors) > 5:
                details.append(f"  ... 他 {len(result.errors) - 5} 件のエラー")
        
        return "\n".join(details) if details else "詳細情報なし"
    
    def _format_trend_details(self, results: List[TrendAnalysisResult], 
                            summary: Dict[str, Any]) -> str:
        """トレンド分析詳細をフォーマット"""
        details = []
        
        # 上位パフォーマー
        if summary["top_performers"]:
            details.append("🏆 【上位パフォーマー】")
            for performer in summary["top_performers"]:
                details.append(f"  • {performer['name']}: {performer['score']}")
        
        # 注意が必要なプレイヤー
        if summary["needs_attention"]:
            details.append("\n⚠️ 【注意が必要なプレイヤー】")
            for player in summary["needs_attention"]:
                details.append(f"  • {player['name']}: {player['trend']} ({player['score']})")
        
        # 各プレイヤーの詳細（改善・低下傾向のみ）
        notable_players = [r for r in results if r.overall_trend in ["improving", "declining"]]
        if notable_players:
            details.append("\n📊 【注目すべきトレンド】")
            for result in notable_players[:3]:  # 最大3名まで表示
                trend_emoji = "📈" if result.overall_trend == "improving" else "📉"
                details.append(f"  {trend_emoji} {result.player_name}: {result.overall_trend}")
                
                # 改善指標
                if result.improving_metrics:
                    details.append(f"    向上: {', '.join(result.improving_metrics[:2])}")
                
                # 低下指標
                if result.declining_metrics:
                    details.append(f"    低下: {', '.join(result.declining_metrics[:2])}")
        
        return "\n".join(details) if details else "詳細情報なし"
    
    def generate_weekly_report(self, collection_results: List[DataCollectionResult], 
                             trend_results: List[TrendAnalysisResult]) -> str:
        """週次レポートを生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"weekly_report_{timestamp}.json"
        filepath = self.reports_dir / filename
        
        # レポートデータ作成
        report_data = {
            "report_type": "weekly_summary",
            "generated_at": datetime.now().isoformat(),
            "collection_summary": {
                "total_runs": len(collection_results),
                "successful_runs": sum(1 for r in collection_results if r.success),
                "total_matches": sum(r.collected_matches for r in collection_results),
                "total_events": sum(r.collected_events for r in collection_results),
                "total_errors": sum(len(r.errors) for r in collection_results)
            },
            "trend_summary": {
                "analyzed_players": len(trend_results),
                "improving_players": sum(1 for r in trend_results if r.overall_trend == "improving"),
                "declining_players": sum(1 for r in trend_results if r.overall_trend == "declining"),
                "stable_players": sum(1 for r in trend_results if r.overall_trend == "stable"),
                "average_score": sum(r.performance_score for r in trend_results) / len(trend_results) if trend_results else 0
            },
            "detailed_results": {
                "collection_results": [r.to_dict() for r in collection_results],
                "trend_results": [r.to_dict() for r in trend_results]
            }
        }
        
        # JSONファイルに保存
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"週次レポート作成: {filepath}")
        return str(filepath)
    
    def test_notifications(self) -> NotificationResult:
        """通知機能のテスト"""
        notification_result = NotificationResult()
        
        test_data = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "duration": "0:01:30",
            "players_processed": 1,
            "collected_matches": 5,
            "collected_events": 100,
            "error_count": 0,
            "details": "テスト通知が正常に動作しています"
        }
        
        for channel in self.config.scheduler.notification_channels:
            try:
                if channel == "console":
                    self._notify_console(test_data, "data_collection")
                    notification_result.add_success("console", "テスト通知成功")
                
                elif channel == "file":
                    self._notify_file(test_data, "data_collection")
                    notification_result.add_success("file", "テスト通知成功")
                
                elif channel == "slack":
                    self._notify_slack(test_data, "data_collection")
                    notification_result.add_success("slack", "テスト通知成功")
                
                elif channel == "email":
                    self._notify_email(test_data, "data_collection")
                    notification_result.add_success("email", "テスト通知成功")
                
            except Exception as e:
                error_msg = f"テスト通知失敗: {str(e)}"
                self.logger.error(error_msg)
                notification_result.add_error(channel, error_msg)
        
        return notification_result