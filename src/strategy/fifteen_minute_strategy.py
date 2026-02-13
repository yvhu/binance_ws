"""
15-Minute K-Line Trading Strategy
Implements the 15m K-line trading strategy with SAR and confirmation intervals
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime

from ..config.config_manager import ConfigManager
from ..indicators.technical_analyzer import TechnicalAnalyzer
from ..trading.position_manager import PositionManager
from ..trading.trading_executor import TradingExecutor
from ..binance.data_handler import BinanceDataHandler
from ..telegram.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class FifteenMinuteStrategy:
    """15-minute K-line trading strategy"""
    
    def __init__(
        self,
        config: ConfigManager,
        technical_analyzer: TechnicalAnalyzer,
        position_manager: PositionManager,
        trading_executor: TradingExecutor,
        data_handler: BinanceDataHandler,
        telegram_client: TelegramClient
    ):
        """
        Initialize 15-minute strategy
        
        Args:
            config: Configuration manager
            technical_analyzer: Technical analyzer instance
            position_manager: Position manager instance
            trading_executor: Trading executor instance
            data_handler: Data handler instance
            telegram_client: Telegram client instance
        """
        self.config = config
        self.technical_analyzer = technical_analyzer
        self.position_manager = position_manager
        self.trading_executor = trading_executor
        self.data_handler = data_handler
        self.telegram_client = telegram_client
        
        # Strategy configuration
        self.main_interval = config.get_config("strategy", "main_interval", default="15m")
        self.check_interval = config.get_config("strategy", "check_interval", default="5m")
        self.confirm_interval_1 = config.get_config("strategy", "confirm_interval_1", default="3m")
        self.confirm_interval_2 = config.get_config("strategy", "confirm_interval_2", default="5m")
        
        logger.info("15-minute strategy initialized")
    
    def on_15m_kline_start(self, kline_info: Dict) -> None:
        """
        Handle 15-minute K-line start event
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        start_time = kline_info['open_time']
        
        logger.info(f"[STRATEGY] on_15m_kline_start called for {symbol}")
        
        # Set new cycle start time
        self.position_manager.set_15m_cycle_start(start_time)
        
        logger.info(f"15m K-line started for {symbol} at {datetime.fromtimestamp(start_time/1000)}")
    
    async def on_5m_kline_close(self, kline_info: Dict) -> None:
        """
        Handle 5-minute K-line close event (trigger for opening position)
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        interval = kline_info['interval']
        
        logger.info(f"[STRATEGY] on_5m_kline_close called for {symbol} {interval}")
        
        # Only process if it's the first 5m K-line in the 15m cycle
        if not self._is_first_5m_in_15m_cycle(kline_info):
            logger.debug(f"Not the first 5m K-line in 15m cycle for {symbol}")
            return
        
        # Check if position can be opened
        if not self.position_manager.can_open_position():
            logger.info(f"Position already opened in current cycle for {symbol}")
            return
        
        logger.info(f"First 5m K-line closed for {symbol}, checking entry conditions...")
        
        # Execute strategy logic
        await self._check_and_open_position(symbol)
        
        # Also trigger SAR calculation and direction check for 15m interval here
        logger.info(f"Triggering SAR calculation and direction check for 15m interval at 5m close for {symbol}")
        sar_direction = self._get_sar_direction(symbol)
        if sar_direction is not None:
            logger.info(f"SAR direction at 5m close: {sar_direction}")
        else:
            logger.warning(f"Could not determine SAR direction at 5m close for {symbol}")
    
    async def on_15m_kline_close(self, kline_info: Dict) -> None:
        """
        Handle 15-minute K-line close event (trigger for closing position)
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        
        logger.info(f"[STRATEGY] on_15m_kline_close called for {symbol}")
        logger.info(f"15m K-line closed for {symbol}, closing all positions...")
        
        # Close all positions immediately asynchronously
        import asyncio
        success = await asyncio.to_thread(self.trading_executor.close_all_positions, symbol)
        
        if success:
            # Reset cycle state
            self.position_manager.reset_cycle()
            logger.info(f"Positions closed and cycle reset for {symbol}")
        else:
            logger.error(f"Failed to close positions for {symbol}")
    
    def _is_first_5m_in_15m_cycle(self, kline_info: Dict) -> bool:
        """
        Check if this is the first 5m K-line in the current 15m cycle
        
        Args:
            kline_info: K-line information
            
        Returns:
            True if it's the first 5m K-line
        """
        if self.position_manager.current_15m_start_time is None:
            return False
        
        # Calculate time difference
        kline_close_time = kline_info['close_time']
        cycle_start_time = self.position_manager.current_15m_start_time
        
        # First 5m K-line should close approximately 5 minutes after 15m start
        time_diff = kline_close_time - cycle_start_time
        
        # Allow some tolerance (within 30 seconds of 5 minutes)
        is_first = 290000 <= time_diff <= 310000  # 4:50 to 5:10 minutes
        
        logger.debug(f"Time diff: {time_diff/1000}s, is_first: {is_first}")
        
        return is_first
    
    async def _check_and_open_position(self, symbol: str) -> None:
        """
        Check entry conditions and open position if met
        
        Args:
            symbol: Trading pair symbol
        """
        logger.info(f"[STRATEGY] _check_and_open_position called for {symbol}")
        try:
            # Get SAR direction from current 15m K-line
            sar_direction = self._get_sar_direction(symbol)
            if sar_direction is None:
                logger.warning(f"Could not determine SAR direction for {symbol}")
                return
            
            # Get 3m K-line direction
            kline_3m = self.data_handler.get_klines(symbol, "3m", count=1)
            if not kline_3m:
                logger.warning(f"No 3m K-line data for {symbol}")
                return
            
            direction_3m = self.technical_analyzer.get_kline_direction(kline_3m[0])
            if direction_3m is None:
                logger.warning(f"Could not determine 3m K-line direction for {symbol}")
                return
            
            # Get 5m K-line direction
            kline_5m = self.data_handler.get_klines(symbol, "5m", count=1)
            if not kline_5m:
                logger.warning(f"No 5m K-line data for {symbol}")
                return
            
            direction_5m = self.technical_analyzer.get_kline_direction(kline_5m[0])
            if direction_5m is None:
                logger.warning(f"Could not determine 5m K-line direction for {symbol}")
                return
            
            # Check if all directions match
            if sar_direction == direction_3m == direction_5m:
                logger.info(f"All directions match for {symbol}: {sar_direction}")
                
                # Open position
                if sar_direction == 'UP':
                    await self._open_long_position(symbol)
                else:  # DOWN
                    await self._open_short_position(symbol)
            else:
                logger.info(
                    f"Directions do not match for {symbol}: "
                    f"SAR={sar_direction}, 3m={direction_3m}, 5m={direction_5m}"
                )
                
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    def _get_sar_direction(self, symbol: str) -> Optional[str]:
        """
        Get SAR direction based on current 15m K-line data
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            'UP' or 'DOWN' or None
        """
        try:
            # Get 15m K-line data (including current incomplete K-line)
            df = self.data_handler.get_klines_dataframe(symbol, "15m")
            
            if df.empty or len(df) < 2:
                logger.warning(f"Not enough 15m K-line data for SAR calculation: {len(df)}")
                return None
            
            # Calculate SAR direction based on current price vs SAR
            sar_direction = self.technical_analyzer.get_sar_direction(df)
            
            logger.debug(f"SAR direction for {symbol}: {sar_direction}")
            
            return sar_direction
            
        except Exception as e:
            logger.error(f"Error getting SAR direction for {symbol}: {e}")
            return None
    
    async def _open_long_position(self, symbol: str) -> None:
        """
        Open a long position
        
        Args:
            symbol: Trading pair symbol
        """
        try:
            # Get current price
            current_price = self.data_handler.get_current_price(symbol)
            if current_price is None:
                logger.error(f"Could not get current price for {symbol}")
                return
            
            # Calculate position size (with fees and safety margin)
            quantity = self.trading_executor.calculate_position_size(current_price, symbol)
            if quantity is None:
                logger.error(f"Could not calculate position size for {symbol}")
                return
            
            # Execute order
            order = self.trading_executor.open_long_position(symbol, quantity)
            
            if order:
                # Record position
                self.position_manager.open_position(
                    symbol=symbol,
                    side='LONG',
                    entry_price=current_price,
                    quantity=quantity
                )
                
                logger.info(f"Long position opened successfully for {symbol}")
                
                # Send trade notification
                await self.telegram_client.send_trade_notification(
                    symbol=symbol,
                    side='LONG',
                    price=current_price,
                    quantity=quantity,
                    leverage=self.config.leverage
                )
            else:
                logger.error(f"Failed to open long position for {symbol}")
                
                # Send error notification
                await self.telegram_client.send_error_message(
                    f"Failed to open long position for {symbol}",
                    "Trading execution error"
                )
                
        except Exception as e:
            logger.error(f"Error opening long position for {symbol}: {e}")
    
    async def _open_short_position(self, symbol: str) -> None:
        """
        Open a short position
        
        Args:
            symbol: Trading pair symbol
        """
        try:
            # Get current price
            current_price = self.data_handler.get_current_price(symbol)
            if current_price is None:
                logger.error(f"Could not get current price for {symbol}")
                return
            
            # Calculate position size (with fees and safety margin)
            quantity = self.trading_executor.calculate_position_size(current_price, symbol)
            if quantity is None:
                logger.error(f"Could not calculate position size for {symbol}")
                return
            
            # Execute order
            order = self.trading_executor.open_short_position(symbol, quantity)
            
            if order:
                # Record position
                self.position_manager.open_position(
                    symbol=symbol,
                    side='SHORT',
                    entry_price=current_price,
                    quantity=quantity
                )
                
                logger.info(f"Short position opened successfully for {symbol}")
                
                # Send trade notification
                await self.telegram_client.send_trade_notification(
                    symbol=symbol,
                    side='SHORT',
                    price=current_price,
                    quantity=quantity,
                    leverage=self.config.leverage
                )
            else:
                logger.error(f"Failed to open short position for {symbol}")
                
                # Send error notification
                await self.telegram_client.send_error_message(
                    f"Failed to open short position for {symbol}",
                    "Trading execution error"
                )
                
        except Exception as e:
            logger.error(f"Error opening short position for {symbol}: {e}")