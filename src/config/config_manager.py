"""
設定管理モジュール

設定ファイルの読み込み・保存・検証を管理する
"""

import os
import yaml
import logging
from typing import Dict, Any
from pathlib import Path

from .lol_config import LoLConfig


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, config_path: str = "config/lol_config.yaml"):
        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)
        self.config: LoLConfig = LoLConfig()
    
    def load_config(self, config_file: str = None) -> LoLConfig:
        """設定ファイルを読み込み"""
        config_path = Path(config_file) if config_file else self.config_path
        
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                self.config = LoLConfig(**config_data)
                self.logger.info(f"Configuration loaded from {config_path}")
            else:
                self.logger.info(f"Config file not found at {config_path}, using defaults")
                self.config = LoLConfig()
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            self.config = LoLConfig()
        
        # 環境変数からAPIキーを取得
        self.load_from_env()
        
        return self.config
    
    def save_config(self, config_data: Dict[str, Any] = None, config_file: str = None) -> None:
        """設定をファイルに保存"""
        config_path = Path(config_file) if config_file else self.config_path
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = config_data if config_data else self.config.model_dump()
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            self.logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
    
    def load_from_env(self) -> None:
        """環境変数から設定を読み込み"""
        # Riot API Key
        riot_api_key = os.getenv("RIOT_API_KEY")
        if riot_api_key:
            self.config.api.riot_api_key = riot_api_key
        
        # OpenRouter API Key
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_api_key:
            self.config.api.openrouter_api_key = openrouter_api_key
        
        # Region
        region = os.getenv("RIOT_REGION")
        if region:
            self.config.api.riot_region = region