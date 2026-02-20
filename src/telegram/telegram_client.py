"""
Telegram Client
Handles communication with Telegram Bot API
"""
import asyncio
import logging
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError, TimedOut

from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class TelegramClient:
    """Telegram bot client for sending notifications"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize Telegram client
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.bot_token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        self.enable_notifications = config.telegram_enable_notifications
        
        self.bot: Optional[Bot] = None
    
    async def initialize(self) -> None:
        """Initialize Telegram bot"""
        if not self.bot_token:
            logger.warning("Telegram bot token not configured. Telegram notifications disabled.")
            self.enable_notifications = False
            return
        
        try:
            self.bot = Bot(token=self.bot_token)
            # Test connection
            await self.bot.get_me()
            logger.info("Telegram bot initialized successfully")
        except TelegramError as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enable_notifications = False
    
    async def shutdown(self) -> None:
        """Shutdown Telegram bot"""
        if self.bot:
            await self.bot.shutdown()
            logger.info("Telegram bot shutdown successfully")
    
    async def send_message(self, message: str) -> bool:
        """
        Send message to Telegram chat
        
        Args:
            message: Message text to send
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enable_notifications or not self.bot or not self.chat_id:
            logger.debug("Telegram notifications disabled or not configured")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                disable_web_page_preview=True
            )
            logger.info("Telegram message sent successfully")
            return True
            
        except TimedOut:
            logger.error("Telegram API timeout")
            return False
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False