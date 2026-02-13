"""
Configuration Manager
Handles loading and accessing configuration from .env and .toml files
"""

import os
from typing import Any, Dict, Optional
from pathlib import Path
import toml
from dotenv import load_dotenv


class ConfigManager:
    """Configuration manager for the application"""
    
    def __init__(self, env_path: str = ".env", config_path: str = "config.toml"):
        """
        Initialize configuration manager
        
        Args:
            env_path: Path to .env file
            config_path: Path to config.toml file
        """
        self.env_path = Path(env_path)
        self.config_path = Path(config_path)
        self._env_vars: Dict[str, str] = {}
        self._config: Dict[str, Any] = {}
        
        self._load_env()
        self._load_config()
    
    def _load_env(self) -> None:
        """Load environment variables from .env file"""
        if self.env_path.exists():
            load_dotenv(self.env_path)
        
        # Store all environment variables
        self._env_vars = dict(os.environ)
    
    def _load_config(self) -> None:
        """Load configuration from .toml file"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = toml.load(f)
    
    def get_env(self, key: str, default: Optional[str] = None) -> str:
        """
        Get environment variable
        
        Args:
            key: Environment variable key
            default: Default value if key not found
            
        Returns:
            Environment variable value
        """
        return self._env_vars.get(key, default or "")
    
    def get_config(self, *keys: str, default: Optional[Any] = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            *keys: Configuration keys (e.g., 'app', 'name')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    @property
    def binance_api_key(self) -> str:
        """Get Binance API key"""
        return self.get_env("BINANCE_API_KEY")
    
    @property
    def binance_api_secret(self) -> str:
        """Get Binance API secret"""
        return self.get_env("BINANCE_API_SECRET")
    
    @property
    def binance_ws_url(self) -> str:
        """Get Binance WebSocket URL"""
        return self.get_env("BINANCE_WS_URL", "wss://stream.binance.com:9443")
    
    @property
    def telegram_bot_token(self) -> str:
        """Get Telegram bot token"""
        return self.get_env("TELEGRAM_BOT_TOKEN")
    
    @property
    def telegram_chat_id(self) -> str:
        """Get Telegram chat ID"""
        return self.get_env("TELEGRAM_CHAT_ID")
    
    @property
    def leverage(self) -> int:
        """Get trading leverage"""
        return int(self.get_env("LEVERAGE", "10"))
    
    @property
    def binance_symbols(self) -> list:
        """Get Binance symbols to monitor"""
        return self.get_config("binance", "symbols", default=[])
    
    @property
    def binance_streams(self) -> list:
        """Get Binance WebSocket streams"""
        return self.get_config("binance", "streams", default=[])
    
    @property
    def telegram_enable_notifications(self) -> bool:
        """Check if Telegram notifications are enabled"""
        return self.get_config("telegram", "enable_notifications", default=True)
    
    @property
    def indicators_config(self) -> Dict[str, Any]:
        """Get indicators configuration"""
        return self.get_config("indicators", default={})
    
    @property
    def strategy_config(self) -> Dict[str, Any]:
        """Get strategy configuration"""
        return self.get_config("strategy", default={})
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.get_config("logging", default={})