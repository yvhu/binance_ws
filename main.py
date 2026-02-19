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
from src.binance.user_data_client import UserDataClient
from src.binance.data_handler import BinanceDataHandler
from src.telegram.telegram_client import TelegramClient
from src.indicators.technical_analyzer import TechnicalAnalyzer
from src.indicators.sentiment_analyzer import SentimentAnalyzer
from src.indicators.ml_predictor import MLPredictor
from src.trading.position_manager import PositionManager
from src.trading.trading_executor import TradingExecutor
from src.strategy.fifteen_minute_strategy import FiveMinuteStrategy
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
        
        # Initialize components for futures trading
        self.data_handler = BinanceDataHandler()
        self.binance_client = BinanceWSClient(self.config)
        self.telegram_client = TelegramClient(self.config)
        
        # User data client will be initialized after trading executor
        self.user_data_client: Optional[UserDataClient] = None
        
        self.technical_analyzer = TechnicalAnalyzer(self.config.indicators_config)
        
        # Initialize trading components
        try:
            self.trading_executor = TradingExecutor(self.config)
        except Exception as e:
            self.logger.error(f"✗ Failed to initialize trading executor: {e}")
            raise
        
        self.position_manager = PositionManager(
            trading_executor=self.trading_executor,
            config=self.config,
            data_handler=self.data_handler
        )
        
        self.user_data_client = UserDataClient(self.config, self.trading_executor)
        self.sentiment_analyzer = SentimentAnalyzer()
        self.ml_predictor = MLPredictor()
        
        self.strategy = FiveMinuteStrategy(
            self.config,
            self.technical_analyzer,
            self.position_manager,
            self.trading_executor,
            self.data_handler,
            self.telegram_client,
            self.sentiment_analyzer,
            self.ml_predictor
        )
        
        # Bot state
        self.is_running = False
        self.last_signal_time = {}
        
        # Task references
        self.user_data_task = None
        self.market_data_task = None
        self.sentiment_update_task = None
        self.ml_retrain_task = None
        
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
            
            # Set trading executor for data handler to fetch historical data
            self.data_handler.set_trading_executor(self.trading_executor)
            
            # Sync positions from Binance exchange to avoid "logic empty but real has position" risk
            await self.position_manager.sync_from_exchange(self.config.binance_symbols)
            
            # Load historical klines for all configured symbols and intervals
            await self._load_historical_data()
            
            # Register Binance Futures WebSocket callbacks
            self._register_callbacks()
            
            # Register user data stream callbacks
            self._register_user_data_callbacks()
            
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
    
    def _register_user_data_callbacks(self) -> None:
        """Register callbacks for user data stream messages"""
        # Account update callback
        self.user_data_client.on_account_update(self._on_account_update)
        
        # Order update callback
        self.user_data_client.on_order_update(self._on_order_update)
        
        # Position update callback
        self.user_data_client.on_position_update(self._on_position_update)
        
        # Error callback
        self.user_data_client.on_error(self._on_user_data_error)
    
    async def _load_historical_data(self) -> None:
        """Load historical kline data for all configured symbols and intervals"""
        try:
            symbols = self.config.binance_symbols
            intervals = ['5m', '15m', '1h']  # Load data for all intervals used in strategy
            
            for symbol in symbols:
                for interval in intervals:
                    # Load 100 historical klines
                    success = await asyncio.to_thread(
                        self.data_handler.load_historical_klines,
                        symbol,
                        interval,
                        limit=100
                    )
                    
                    if not success:
                        self.logger.warning(f"✗ Failed to load historical data for {symbol} {interval}")
            
        except Exception as e:
            self.logger.error(f"Error loading historical data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    async def _on_ticker(self, ticker_info: dict) -> None:
        """
        Handle ticker updates
        
        Args:
            ticker_info: Ticker information dictionary
        """
        try:
            # Store data
            self.data_handler.process_ticker(ticker_info)
            
            # Check stop loss for positions with this symbol
            symbol = ticker_info['symbol']
            current_price = ticker_info.get('current_price')
            
            if current_price and self.position_manager.has_position(symbol):
                # Real-time stop loss check on every price update
                await self.strategy.check_stop_loss_on_price_update(symbol, current_price)
            
            # Price alerts disabled - only store data for strategy use
            # Uncomment below to enable price alerts
            # price_change = ticker_info.get('price_change_percent', 0)
            # min_change = self.config.strategy_config.get('min_price_change', 0.5)
            # if abs(price_change) >= min_change:
            #     self.logger.info(f"Significant price change for {symbol}: {price_change:.2f}%")
            #     await self.telegram_client.send_ticker_alert(ticker_info)
            
        except Exception as e:
            self.logger.error(f"Error processing ticker: {e}")
    
    async def _on_kline(self, kline_info: dict) -> None:
        """
        Handle kline (candlestick) updates
        
        Args:
            kline_info: Kline information dictionary
        """
        try:
            symbol = kline_info['symbol']
            interval = kline_info['interval']
            is_closed = kline_info.get('is_closed', False)
            open_time = kline_info.get('open_time', 0)
            
            # Debug log for all kline events
            self.logger.debug(f"[KLINE] Received: {symbol} {interval} closed={is_closed}")
            
            # Store data
            self.data_handler.process_kline(kline_info)
            
            # Route to strategy based on interval
            if interval == '5m':
                # Call on_5m_kline_update for all kline updates (including unclosed)
                # This handles early entry and real-time stop loss checks
                self.logger.debug(f"[KLINE] Calling on_5m_kline_update for {symbol}")
                await self.strategy.on_5m_kline_update(kline_info)
                
                # Only process closed klines for opening positions
                if is_closed:
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
            
        except Exception as e:
            self.logger.error(f"Error sending signal notification: {e}")
    
    async def _on_mark_price(self, mark_price_info: dict) -> None:
        """
        Handle mark price updates (Futures specific)
        
        Args:
            mark_price_info: Mark price information dictionary
        """
        try:
            symbol = mark_price_info.get('symbol', 'UNKNOWN')
            mark_price = mark_price_info.get('mark_price', 0)
            funding_rate = mark_price_info.get('funding_rate', 0)
            
            self.logger.debug(f"Mark price update for {symbol}: {mark_price}, funding rate: {funding_rate}")
            
            # Store data for strategy use
            self.data_handler.process_mark_price(mark_price_info)
            
        except Exception as e:
            self.logger.error(f"Error processing mark price: {e}")
    
    async def _on_force_order(self, force_order_info: dict) -> None:
        """
        Handle force order/liquidation updates (Futures specific)
        
        Args:
            force_order_info: Force order information dictionary
        """
        try:
            symbol = force_order_info.get('symbol', 'UNKNOWN')
            side = force_order_info.get('side', 'UNKNOWN')
            order_type = force_order_info.get('order_type', 'UNKNOWN')
            
            # Send liquidation alert to Telegram
            await self.telegram_client.send_error_message(
                error=f"Force order detected: {side} {order_type}",
                context=f"Liquidation alert for {symbol}"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing force order: {e}")
    
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
    
    async def _on_account_update(self, account_info: dict) -> None:
        """
        Handle account balance updates from user data stream
        
        Args:
            account_info: Account information dictionary
        """
        try:
            balances = account_info.get('B', [])
            for b in balances:
                if b.get('a') == 'USDC':  # 或 'USDT'，根据实际账户稳定币调整
                    balance = float(b.get('cw', 0))
                    self.user_data_client.account_balance = balance
                    break
            else:
                self.logger.warning("USDC balance not found in ACCOUNT_UPDATE message")
        except Exception as e:
            self.logger.error(f"Error processing account update: {e}")
    
    async def _on_order_update(self, order_info: dict) -> None:
        """
        Handle order updates from user data stream
        
        Args:
            order_info: Order information dictionary
        """
        try:
            symbol = order_info.get('symbol', 'UNKNOWN')
            status = order_info.get('status', 'UNKNOWN')
            order_type = order_info.get('order_type', 'UNKNOWN')
            side = order_info.get('side', 'UNKNOWN')
            executed_qty = order_info.get('executed_quantity', 0)
            avg_price = order_info.get('avg_price', 0)
            
            # Check if this is a stop loss order that was filled
            if order_type == 'STOP_MARKET' and status == 'FILLED':
                # Stop loss was triggered - send detailed notification
                position = self.position_manager.get_position(symbol)
                if position:
                    entry_price = position.get('entry_price', 0)
                    quantity = position.get('quantity', 0)
                    
                    # Calculate PnL
                    if position['side'] == 'LONG':
                        pnl = (avg_price - entry_price) * quantity
                    else:  # SHORT
                        pnl = (entry_price - avg_price) * quantity
                    
                    # Send close notification with stop loss reason
                    await self.telegram_client.send_close_notification(
                        symbol=symbol,
                        side=position['side'],
                        entry_price=entry_price,
                        exit_price=avg_price,
                        quantity=quantity,
                        pnl=pnl,
                        close_reason="移动止损触发 (基于5m K线振幅)"
                    )
                    
                    # Update position manager
                    self.position_manager.close_position(symbol, avg_price)
                    
        except Exception as e:
            self.logger.error(f"Error processing order update: {e}")
    
    async def _on_position_update(self, position_info: dict) -> None:
        """
        Handle position updates from user data stream
        
        Args:
            position_info: Position information dictionary
        """
        try:
            symbol = position_info.get('symbol', 'UNKNOWN')
            amount = position_info.get('amount', 0)
            unrealized_pnl = position_info.get('unrealized_pnl', 0)
        except Exception as e:
            self.logger.error(f"Error processing position update: {e}")
    
    async def _on_user_data_error(self, error_info) -> None:
        """
        Handle user data stream errors
        
        Args:
            error_info: Error information (dict or str)
        """
        try:
            # Handle both dict and str error info
            if isinstance(error_info, dict):
                error_type = error_info.get('type', 'unknown')
                error_message = error_info.get('error', 'Unknown error')
            else:
                error_type = 'unknown'
                error_message = str(error_info)
            
            self.logger.error(f"User data stream error ({error_type}): {error_message}")
            
            # Send error notification to Telegram
            await self.telegram_client.send_error_message(
                error=error_message,
                context=f"User data stream {error_type}"
            )
        except Exception as e:
            self.logger.error(f"Error in user data error handler: {e}")
    
    async def send_startup_notification(self) -> None:
        """Send startup notification to Telegram"""
        symbols = self.config.binance_symbols
        
        # Get account balance from user data stream (WebSocket)
        balance = self.user_data_client.get_account_balance()
        
        # If balance not available yet or zero, try REST API as fallback
        if balance is None or balance == 0:
            self.logger.warning("Balance not available or zero from WebSocket, using REST API fallback")
            balance = self.trading_executor.get_account_balance()
        
        balance_str = f"{balance:.2f} USDC" if balance is not None else "获取失败"
        
        details = {
            "交易对": ", ".join(symbols),
            "杠杆": f"{self.config.leverage}倍",
            "策略": "5分钟K线策略",
            "仓位大小": "100% (全仓)",
            "可用资金": balance_str,
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
            await self.initialize()

            # --- 关键改动：后台启动 WebSocket，不阻塞主协程 ---
            self.user_data_task = asyncio.create_task(self.user_data_client.start())
            self.market_data_task = asyncio.create_task(self.binance_client.start())
            
            # 实时止损检查已集成到ticker回调中，无需单独任务
            
            # 等待一小段时间让任务开始执行
            await asyncio.sleep(0.1)
            
            # 等待WebSocket连接并获取价格数据 (最多 10 秒)
            for i in range(10):
                await asyncio.sleep(1)
                # 检查是否有持仓需要更新止损价格
                if self.position_manager.positions:
                    # 尝试获取第一个持仓的价格
                    first_symbol = list(self.position_manager.positions.keys())[0]
                    test_price = self.data_handler.get_current_price(first_symbol)
                    if test_price is not None:
                        break
                else:
                    # 没有持仓，直接退出等待
                    break
            
            # 更新所有持仓的止损价格
            if self.position_manager.positions:
                await self.position_manager.update_stop_loss_prices()
            
            # 检查任务状态
            if self.user_data_task.done():
                try:
                    result = self.user_data_task.result()
                    self.logger.error(f"User data task completed immediately with result: {result}")
                except Exception as e:
                    self.logger.error(f"User data task failed immediately: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())

            # 等待 user data stream 连接并获取余额 (最多 10 秒)
            balance = None
            for i in range(10):
                await asyncio.sleep(1)
                balance = self.user_data_client.get_account_balance()
                if balance is not None and balance > 0:
                    break

            # 如果还是没有余额，用 REST API 主动获取
            if balance is None or balance == 0:
                balance = await asyncio.to_thread(self.trading_executor.get_account_balance)
                self.user_data_client.account_balance = balance

            # 发送启动通知
            await self.send_startup_notification()

            # --- 启动情绪指标更新任务 ---
            if self.config.get_config("strategy", "sentiment_filter_enabled", default=False):
                self.sentiment_update_task = asyncio.create_task(self._update_sentiment_periodically())

            # --- 启动ML模型训练任务 ---
            if self.config.get_config("strategy", "ml_filter_enabled", default=False):
                await self._train_ml_model()
                
                # 启动定期重新训练任务
                retrain_interval = self.config.get_config("strategy", "ml_retrain_interval", default=24)
                self.ml_retrain_task = asyncio.create_task(self._retrain_ml_periodically(retrain_interval))

            # --- 主协程可以继续做其他任务，WebSocket 永远在后台运行 ---
            loop_count = 0
            while self.is_running:
                loop_count += 1
                if loop_count % 60 == 0:  # 每分钟记录一次
                    # 检查 WebSocket 任务状态
                    if self.user_data_task:
                        if self.user_data_task.done():
                            self.logger.warning("User data task has stopped!")
                            try:
                                result = self.user_data_task.result()
                                self.logger.warning(f"User data task result: {result}")
                            except Exception as e:
                                self.logger.error(f"User data task exception: {e}")
                    else:
                        self.logger.warning("User data task is None!")
                    
                    if self.market_data_task:
                        if self.market_data_task.done():
                            self.logger.warning("Market data task has stopped!")
                            try:
                                result = self.market_data_task.result()
                                self.logger.warning(f"Market data task result: {result}")
                            except Exception as e:
                                self.logger.error(f"Market data task exception: {e}")
                    else:
                        self.logger.warning("Market data task is None!")
                    
                    # 检查情绪指标更新任务状态
                    if self.sentiment_update_task:
                        if self.sentiment_update_task.done():
                            self.logger.warning("Sentiment update task has stopped!")
                            try:
                                result = self.sentiment_update_task.result()
                                self.logger.warning(f"Sentiment update task result: {result}")
                            except Exception as e:
                                self.logger.error(f"Sentiment update task exception: {e}")
                    
                    # 检查ML重新训练任务状态
                    if self.ml_retrain_task:
                        if self.ml_retrain_task.done():
                            self.logger.warning("ML retrain task has stopped!")
                            try:
                                result = self.ml_retrain_task.result()
                                self.logger.warning(f"ML retrain task result: {result}")
                            except Exception as e:
                                self.logger.error(f"ML retrain task exception: {e}")
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            self.logger.info("Bot cancelled")
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            await self.telegram_client.send_error_message(str(e), "Bot runtime error")
        finally:
            await self.shutdown()
    
    async def _update_sentiment_periodically(self) -> None:
        """Periodically update Fear and Greed Index"""
        while self.is_running:
            try:
                # Fetch Fear and Greed Index
                sentiment_data = await asyncio.to_thread(self.sentiment_analyzer.get_fear_greed_index)
                
                if sentiment_data:
                    value = sentiment_data.get('value', 0)
                    classification = sentiment_data.get('classification', 'N/A')
                    timestamp = sentiment_data.get('timestamp', 0)
                    
                    pass
                else:
                    self.logger.warning("[SENTIMENT] Failed to fetch Fear and Greed Index")
                
                # Wait for 1 hour before next update
                await asyncio.sleep(3600)  # 1 hour
                
            except asyncio.CancelledError:
                self.logger.info("Sentiment update task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error updating sentiment: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                # Wait for 5 minutes before retry
                await asyncio.sleep(300)  # 5 minutes
    
    async def _train_ml_model(self) -> bool:
        """Train ML model with historical data"""
        try:
            self.logger.info("Training ML model...")
            
            # Get historical data for all symbols
            symbols = self.config.binance_symbols
            
            for symbol in symbols:
                # Get 5m klines
                all_klines = self.data_handler.get_klines(symbol, "5m")
                if not all_klines:
                    self.logger.warning(f"No 5m K-line data for {symbol}")
                    continue
                
                # Filter only closed K-lines
                closed_klines = [k for k in all_klines if k.get('is_closed', False)]
                
                if len(closed_klines) < 50:
                    self.logger.warning(f"Not enough closed K-lines for ML training: {len(closed_klines)} < 50")
                    continue
                
                # Convert to DataFrame
                import pandas as pd
                df = pd.DataFrame(closed_klines)
                
                # Train model
                success = await asyncio.to_thread(self.ml_predictor.train_model, df)
                
                if success:
                    return True
                else:
                    pass
            
            self.logger.warning("Failed to train ML model for any symbol")
            return False
            
        except Exception as e:
            self.logger.error(f"Error training ML model: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    async def _retrain_ml_periodically(self, interval_hours: int) -> None:
        """Periodically retrain ML model"""
        while self.is_running:
            try:
                # Wait for the specified interval
                await asyncio.sleep(interval_hours * 3600)  # Convert hours to seconds
                
                # Retrain model
                await self._train_ml_model()
                
            except asyncio.CancelledError:
                self.logger.info("ML retrain task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error retraining ML model: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
    
    async def shutdown(self) -> None:
        """Shutdown the bot gracefully"""
        self.logger.info("Shutting down bot...")
        
        try:
            # Send shutdown notification
            await self.send_shutdown_notification()
            
            # Cancel sentiment update task
            if self.sentiment_update_task and not self.sentiment_update_task.done():
                self.sentiment_update_task.cancel()
                try:
                    await self.sentiment_update_task
                except asyncio.CancelledError:
                    pass
            
            # Cancel ML retrain task
            if self.ml_retrain_task and not self.ml_retrain_task.done():
                self.ml_retrain_task.cancel()
                try:
                    await self.ml_retrain_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect WebSocket clients
            if self.binance_client:
                await self.binance_client.disconnect()
            
            if self.user_data_client:
                await self.user_data_client.disconnect()
            
            # Stop Telegram bot
            if self.telegram_client:
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