"""
データ検証モジュール

データの完全性と整合性を検証する
"""

import logging
from typing import Dict, Any, List

from .validation_result import ValidationResult
from .anomaly_report import AnomalyReport
from ..canonizer.event import Event


class DataValidator:
    """データ検証クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_match_completeness(self, match_data: Dict[str, Any]) -> ValidationResult:
        """マッチデータの完全性をチェック"""
        errors = []
        warnings = []
        
        # 基本構造チェック
        if not isinstance(match_data, dict):
            errors.append("Match data must be a dictionary")
            return ValidationResult(is_valid=False, error_count=1, errors=errors)
        
        # メタデータチェック
        metadata = match_data.get("metadata", {})
        if not metadata.get("matchId"):
            errors.append("Missing matchId in metadata")
        
        participants = metadata.get("participants", [])
        if len(participants) != 10:
            errors.append(f"Expected 10 participants, got {len(participants)}")
        
        # 情報セクションチェック
        info = match_data.get("info", {})
        if not info:
            errors.append("Missing info section")
        else:
            # ゲーム時間チェック
            game_duration = info.get("gameDuration")
            if game_duration is None:
                errors.append("Missing gameDuration")
            elif game_duration < 0:
                errors.append("Invalid gameDuration: negative value")
        
        is_valid = len(errors) == 0
        quality_score = max(0.0, 1.0 - (len(errors) * 0.2) - (len(warnings) * 0.1))
        
        return ValidationResult(
            is_valid=is_valid,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            quality_score=quality_score
        )
    
    def validate_timeline_consistency(self, timeline: Dict[str, Any]) -> ValidationResult:
        """タイムラインの整合性をチェック"""
        errors = []
        warnings = []
        
        # 基本実装
        if not timeline:
            errors.append("Empty timeline data")
        
        is_valid = len(errors) == 0
        quality_score = max(0.0, 1.0 - (len(errors) * 0.2) - (len(warnings) * 0.1))
        
        return ValidationResult(
            is_valid=is_valid,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            quality_score=quality_score
        )
    
    def detect_anomalies(self, events: List[Event]) -> List[AnomalyReport]:
        """異常データの検出"""
        anomalies = []
        
        # 基本実装
        for i, event in enumerate(events):
            if event.timestamp < 0:
                anomalies.append(AnomalyReport(
                    event_id=str(i),
                    anomaly_type="negative_timestamp",
                    severity="high",
                    description=f"Event has negative timestamp: {event.timestamp}",
                    suggested_action="Check data source and parsing logic",
                    confidence=0.9
                ))
        
        return anomalies