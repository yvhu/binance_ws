"""
Binance Futures Telegram Bot - Main Entry Point
Binance合约交易Telegram机器人 - 主程序入口
"""

import asyncio
import signal
import logging
from typing import Optional

from src.config.config_manager import ConfigManager
from src.binance.ws_client import BinanceWSClient
from src.binance.data_handler import BinanceDataHandler
from src.telegram.telegram_client import TelegramClient
from src.indicators.technical_analyzer import TechnicalAnalyzer
from src.trading.position_manager import PositionManager
from src.trading.trading_executor import TradingExecutor
from src.strategy.fifteen_minute_strategy import FifteenMinuteStrategy
from src.utils.logger import setup_logger


class BinanceTelegramBot:
    """Main bot class that coordinates all components for futures trading"""
    
    def __init__(self):
        """Initialize the bot"""
        # Load configuration
        self.config = ConfigManager()
        
        # Setup logging
        log_config = self.config.logging_config
        self.logger = setup_logger(
            name='binance_futures_bot',
            level=log_config.get('level', 'INFO'),
            log_file=log_config.get('file'),
            format_string=log_config.get('format')
        )
        
        self.logger.info("Initializing Binance Futures Telegram Bot...")
        
        # Initialize components for futures trading
        self.data_handler = BinanceDataHandler()
        self.binance_client = BinanceWSClient(self.config)
        self.telegram_client = TelegramClient(self.config)
        self.technical_analyzer = TechnicalAnalyzer(self.config.indicators_config)
        
        # Initialize trading components
        self.position_manager = PositionManager()
        self.trading_executor = TradingExecutor(self.config)
        self.strategy = FifteenMinuteStrategy(
            self.config,
            self.technical_analyzer,
            self.position_manager,
            self.trading_executor,
            self.data_handler,
            self.telegram_client
        )
        
        # Bot state
        self.is_running = False
        self.last_signal_time = {}
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False
    
    async def initialize(self) -> None:
        """Initialize all components for futures trading"""
        try:
            # Initialize Telegram client
            await self.telegram_client.initialize()
            await self.telegram_client.start_bot()
            
            # Register Binance Futures WebSocket callbacks
            self._register_callbacks()
            
            self.logger.info("All components initialized successfully for futures trading")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise
    
    def _register_callbacks(self) -> None:
        """Register callbacks for Binance Futures WebSocket messages"""
        # Ticker callback
        self.binance_client.on_message('ticker', self._on_ticker)
        
        # Kline callback
        self.binance_client.on_message('kline', self._on_kline)
        
        # Mark price callback (futures specific)
        self.binance_client.on_message('mark_price', self._on_mark_price)
        
        # Force order callback (futures specific)
        self.binance_client.on_message('force_order', self._on_force_order)
        
        # Error callback
        self.binance_client.on_message('error', self._on_error)
    
    async def _on_ticker(self, ticker_info: dict) -> None:
        """
        Handle ticker updates
        
        Args:
            ticker_info: Ticker information dictionary
        """
        try:
            # Store data
            self.data_handler.process_ticker(ticker_info)
            
            symbol = ticker_info['symbol']
            price_change = ticker_info.get('price_change_percent', 0)
            
            # Check for significant price changes
            min_change = self.config.strategy_config.get('min_price_change', 0.5)
            
            if abs(price_change) >= min_change:
                self.logger.info(f"Significant price change for {symbol}: {price_change:.2f}%")
                
                # Send alert to Telegram
                await self.telegram_client.send_ticker_alert(ticker_info)
            
        except Exception as e:
            self.logger.error(f"Error processing ticker: {e}")
    
    async def _on_kline(self, kline_info: dict) -> None:
        """
        Handle kline (candlestick) updates
        
        Args:
            kline_info: Kline information dictionary
        """
        try:
            # Store data
            self.data_handler.process_kline(kline_info)
            
            symbol = kline_info['symbol']
            interval = kline_info['interval']
            
            # Only process closed klines
            if not kline_info.get('is_closed', False):
                return
            
            self.logger.debug(f"Processing closed kline for {symbol} {interval}")
            
            # Route to strategy based on interval
            if interval == '15m':
                # Handle 15m K-line events
                self.strategy.on_15m_kline_close(kline_info)
            elif interval == '5m':
                # Handle 5m K-line events (trigger for opening position)
                await self.strategy.on_5m_kline_close(kline_info)
            
        except Exception as e:
            self.logger.error(f"Error processing kline: {e}")
    
    async def _send_signal_notification(self, symbol: str, signal_type: str, summary: dict) -> None:
        """
        Send trading signal notification to Telegram
        
        Args:
            symbol: Trading pair symbol
            signal_type: Type of signal (BUY/SELL)
            summary: Indicator summary dictionary
        """
        try:
            # Rate limit signals (avoid spamming)
            import time
            current_time = time.time()
            
            if symbol in self.last_signal_time:
                time_since_last = current_time - self.last_signal_time[symbol]
                if time_since_last < 300:  # 5 minutes minimum between signals
                    self.logger.debug(f"Signal rate limited for {symbol}")
                    return
            
            self.last_signal_time[symbol] = current_time
            
            # Get current price
            current_price = self.data_handler.get_current_price(symbol)
            
            if current_price is None:
                self.logger.warning(f"Could not get current price for {symbol}")
                return
            
            # Prepare indicator values for message
            indicators = summary.get('indicators', {})
            relevant_indicators = {
                'Trend': summary.get('trend', 'N/A'),
                'RSI': indicators.get('RSI', 0),
                'MACD': indicators.get('MACD', 0),
                'MA7': indicators.get('MA7', 0),
                'MA25': indicators.get('MA25', 0)
            }
            
            # Send signal alert
            await self.telegram_client.send_signal_alert(
                symbol=symbol,
                signal_type=signal_type,
                indicators=relevant_indicators,
                price=current_price
            )
            
            self.logger.info(f"Sent {signal_type} signal for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error sending signal notification: {e}")
    
    async def _on_error(self, error_info: dict) -> None:
        """
        Handle WebSocket errors
        
        Args:
            error_info: Error information dictionary
        """
        error_type = error_info.get('type', 'unknown')
        error_message = error_info.get('error', 'Unknown error')
        
        self.logger.error(f"WebSocket error ({error_type}): {error_message}")
        
        # Send error notification to Telegram
        await self.telegram_client.send_error_message(
            error=error_message,
            context=f"WebSocket {error_type}"
        )
    
    async def send_startup_notification(self) -> None:
        """Send startup notification to Telegram"""
        symbols = self.config.binance_symbols
        details = {
            "交易对": ", ".join(symbols),
            "杠杆": f"{self.config.leverage}倍",
            "策略": "15分钟K线 + SAR指标",
            "仓位大小": "100% (全仓)",
            "数据流": ", ".join(self.config.binance_streams)
        }
        
        await self.telegram_client.send_system_status("STARTED", details)
    
    async def send_shutdown_notification(self) -> None:
        """Send shutdown notification to Telegram"""
        await self.telegram_client.send_system_status("STOPPED")
    
    async def run(self) -> None:
        """Run the bot"""
        self.is_running = True
        
        try:
            # Initialize components
            await self.initialize()
            
            # Send startup notification
            await self.send_startup_notification()
            
            self.logger.info("Bot started successfully")
            
            # Start Binance WebSocket connection
            await self.binance_client.start()
            
        except asyncio.CancelledError:
            self.logger.info("Bot cancelled")
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
            await self.telegram_client.send_error_message(str(e), "Bot runtime error")
        finally:
            # Cleanup
            await self.shutdown()
    
    async def _on_mark_price(self, mark_price_info: dict) -> None:
        """
        Handle mark price updates (Futures specific)
        
        Args:
            mark_price_info: Mark price information dictionary
        """
        try:
            symbol = mark_price_info['symbol']
            mark_price = mark_price_info.get('mark_price', 0)
            funding_rate = mark_price_info.get('funding_rate', 0)
            
            self.logger.debug(f"Mark price update for {symbol}: {mark_price}, Funding rate: {funding_rate}")
            
            # Can add logic here to alert on significant funding rate changes
            if abs(funding_rate) > 0.0001:  # 0.01% threshold
                self.logger.info(f"Significant funding rate for {symbol}: {funding_rate:.4%}")
                
        except Exception as e:
            self.logger.error(f"Error processing mark price: {e}")
    
    async def _on_force_order(self, force_order_info: dict) -> None:
        """
        Handle force order/liquidation updates (Futures specific)
        
        Args:
            force_order_info: Force order information dictionary
        """
        try:
            symbol = force_order_info['symbol']
            side = force_order_info.get('side', 'UNKNOWN')
            quantity = force_order_info.get('total_filled_quantity', 0)
            price = force_order_info.get('average_price', 0)
            
            self.logger.warning(f"Liquidation detected for {symbol}: {side} {quantity} @ {price}")
            
            # Send alert for large liquidations
            if quantity * price > 100000:  # $100,000 threshold
                message = (
                    f"⚠️ <b>大额强平提醒</b>\n\n"
                    f"📊 交易对: {symbol}\n"
                    f"📈 方向: {side}\n"
                    f"💰 数量: {quantity:.4f}\n"
                    f"💵 价格: ${price:,.2f}\n"
                    f"💵 价值: ${quantity * price:,.2f}"
                )
                await self.telegram_client.send_message(message, parse_mode='HTML')
            
        except Exception as e:
            self.logger.error(f"Error processing force order: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the bot gracefully"""
        self.logger.info("Shutting down bot...")
        
        try:
            # Send shutdown notification
            await self.send_shutdown_notification()
            
            # Disconnect Binance WebSocket
            await self.binance_client.disconnect()
            
            # Shutdown Telegram client
            await self.telegram_client.shutdown()
            
            self.logger.info("Bot shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


async def main():
    """Main entry point"""
    bot = BinanceTelegramBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")