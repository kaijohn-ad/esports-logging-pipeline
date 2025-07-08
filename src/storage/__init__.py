"""
storage パッケージ

データ保存関連のモジュールを含む
"""

from .sqlite_store import init_db

__all__ = ['init_db']