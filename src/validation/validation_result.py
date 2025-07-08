"""
検証結果モジュール

データ検証の結果を格納するデータクラス
"""

from typing import List
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """データ検証結果クラス"""
    is_valid: bool
    error_count: int = 0
    warning_count: int = 0
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    quality_score: float = 1.0  # 0.0 - 1.0