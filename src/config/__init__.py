"""
config パッケージ

設定管理関連のモジュールを含む
"""

from .lol_config import LoLConfig
from .config_manager import ConfigManager

__all__ = ['LoLConfig', 'ConfigManager']