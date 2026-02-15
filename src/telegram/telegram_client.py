"""
Telegram Client
Handles communication with Telegram Bot API
"""
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, TimedOut

from ..config.config_manager import ConfigManager
from .message_formatter import MessageFormatter

logger = logging.getLogger(__name__)

import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, TimedOut

from ..config.config_manager import ConfigManager
from .message_formatter import MessageFormatter

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
        self.application: Optional[Application] = None
        
        # Rate limiting
        self.max_messages_per_minute = config.get_config("telegram", "max_messages_per_minute", default=20)
        self.message_timestamps: list = []
        
        # Message formatter
        self.formatter = MessageFormatter()
    
    async def initialize(self) -> None:
        """Initialize Telegram bot"""
        if not self.bot_token:
            logger.warning("Telegram bot token not configured. Telegram notifications disabled.")
            self.enable_notifications = False
            return
        
        try:
            self.bot = Bot(token=self.bot_token)
            self.application = Application.builder().token(self.bot_token).build()
            
            # Test connection
            await self.bot.get_me()
            logger.info("Telegram bot initialized successfully")
            
        except TelegramError as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enable_notifications = False
    
    async def shutdown(self) -> None:
        """Shutdown Telegram bot"""
        if self.application:
            await self.application.shutdown()
            logger.info("Telegram bot shutdown complete")
    
    def _check_rate_limit(self) -> bool:
        """
        Check if rate limit allows sending a message
        
        Returns:
            True if message can be sent, False otherwise
        """
        now = datetime.now()
        
        # Remove timestamps older than 1 minute
        self.message_timestamps = [
            ts for ts in self.message_timestamps 
            if now - ts < timedelta(minutes=1)
        ]
        
        if len(self.message_timestamps) >= self.max_messages_per_minute:
            logger.warning(f"Rate limit reached: {len(self.message_timestamps)} messages in last minute")
            return False
        
        self.message_timestamps.append(now)
        return True
    
    async def send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send message to Telegram chat
        
        Args:
            message: Message text to send
            parse_mode: Parse mode (Markdown, HTML, or None)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enable_notifications or not self.bot or not self.chat_id:
            logger.debug("Telegram notifications disabled or not configured")
            return False
        
        if not self._check_rate_limit():
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            logger.debug(f"Message sent to Telegram: {message[:50]}...")
            return True
            
        except TimedOut:
            logger.error("Telegram API timeout")
            return False
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def send_ticker_alert(self, ticker_data: Dict) -> bool:
        """
        Send ticker alert to Telegram
        
        Args:
            ticker_data: Ticker data dictionary
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_ticker_alert(ticker_data)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_signal_alert(self, symbol: str, signal_type: str, indicators: Dict, price: float) -> bool:
        """
        Send trading signal alert to Telegram
        
        Args:
            symbol: Trading pair symbol
            signal_type: Type of signal (BUY/SELL)
            indicators: Dictionary of indicator values
            price: Current price
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_signal_alert(symbol, signal_type, indicators, price)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_kline_update(self, kline_data: Dict) -> bool:
        """
        Send kline update to Telegram
        
        Args:
            kline_data: Kline data dictionary
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_kline_update(kline_data)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_error_message(self, error: str, context: Optional[str] = None) -> bool:
        """
        Send error message to Telegram
        
        Args:
            error: Error message
            context: Additional context information
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_error_message(error, context)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_system_status(self, status: str, details: Optional[Dict] = None) -> bool:
        """
        Send system status message to Telegram
        
        Args:
            status: System status
            details: Additional status details
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_system_status(status, details)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_summary_report(self, symbols: list, data: Dict) -> bool:
        """
        Send summary report to Telegram
        
        Args:
            symbols: List of trading symbols
            data: Dictionary containing data for each symbol
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_summary_report(symbols, data)
        return await self.send_message(message, parse_mode='HTML')
    
    async def start_bot(self) -> None:
        """Start Telegram bot with command handlers"""
        if not self.application:
            logger.warning("Telegram application not initialized")
            return
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("status", self._status_command))
        self.application.add_handler(CommandHandler("summary", self._summary_command))
        
        # Start the bot
        await self.application.initialize()
        await self.application.start()
        logger.info("Telegram bot started with command handlers")
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        message = (
            "🤖 <b>Binance Trading Bot</b>\n\n"
            "Welcome! I'm here to keep you updated on market movements and trading signals.\n\n"
            "Available commands:\n"
            "/help - Show this help message\n"
            "/status - Check bot status\n"
            "/summary - Get market summary"
        )
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        message = (
            "📚 <b>Help</b>\n\n"
            "Available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/status - Check bot status\n"
            "/summary - Get market summary\n\n"
            "The bot will automatically send you:\n"
            "• Price alerts for significant movements\n"
            "• Trading signals based on technical indicators\n"
            "• System status updates"
        )
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        status = "CONNECTED" if self.enable_notifications else "DISABLED"
        details = {
            "Notifications": "Enabled" if self.enable_notifications else "Disabled",
            "Rate Limit": f"{self.max_messages_per_minute} messages/minute"
        }
        message = self.formatter.format_system_status(status, details)
        await update.message.reply_text(message, parse_mode='HTML')
    
    async def send_trade_notification(self, symbol: str, side: str, price: float, quantity: float, leverage: int,
                                       volume_info: Optional[Dict] = None,
                                       position_calc_info: Optional[Dict] = None,
                                       kline_time: Optional[int] = None) -> bool:
        """
        Send trade notification to Telegram
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            price: Entry price
            quantity: Position quantity
            leverage: Leverage multiplier
            volume_info: Volume information dictionary (optional)
            position_calc_info: Position calculation information (optional)
            kline_time: K-line timestamp in milliseconds (optional)
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_trade_notification(
            symbol, side, price, quantity, leverage, volume_info, position_calc_info, kline_time
        )
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_close_notification(self, symbol: str, side: str, entry_price: float, exit_price: float, quantity: float, pnl: float) -> bool:
        """
        Send position close notification to Telegram
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position quantity
            pnl: Profit/Loss
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_close_notification(symbol, side, entry_price, exit_price, quantity, pnl)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_no_trade_notification(self, symbol: str, reason: str) -> bool:
        """
        Send no trade notification to Telegram
        
        Args:
            symbol: Trading pair symbol
            reason: Reason for not trading
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_no_trade_notification(symbol, reason)
        return await self.send_message(message, parse_mode='HTML')
    
    async def send_indicator_analysis(self, symbol: str, sar_direction: Optional[str], direction_3m: str,
                                       direction_5m: str, sar_value: Optional[float] = None,
                                       current_price: Optional[float] = None,
                                       decision: Optional[str] = None,
                                       volume_info: Optional[Dict] = None,
                                       body_info: Optional[Dict] = None,
                                       kline_time: Optional[int] = None) -> bool:
        """
        Send indicator analysis notification to Telegram
        
        Args:
            symbol: Trading pair symbol
            sar_direction: SAR direction (deprecated, always None)
            direction_3m: 3m K-line direction ('UP' or 'DOWN')
            direction_5m: 5m K-line direction ('UP' or 'DOWN')
            sar_value: SAR value (deprecated, always None)
            current_price: Current price (optional)
            decision: Trading decision (optional)
            volume_info: Volume information dictionary (optional)
            body_info: Body ratio information dictionary (optional)
            kline_time: K-line timestamp in milliseconds (optional)
            
        Returns:
            True if message sent successfully
        """
        message = self.formatter.format_indicator_analysis(
            symbol, sar_direction, direction_3m, direction_5m,
            sar_value, current_price, decision, volume_info, body_info, kline_time
        )
        return await self.send_message(message, parse_mode='HTML')
    
    async def _summary_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summary command"""
        message = "📊 <b>Market Summary</b>\n\nSummary report will be sent when data is available."
        await update.message.reply_text(message, parse_mode='HTML')