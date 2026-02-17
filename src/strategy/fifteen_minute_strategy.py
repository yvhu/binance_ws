"""
15-Minute K-Line Trading Strategy
Implements the 15m K-line trading strategy with confirmation intervals
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime
import pandas as pd

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
        self.volume_ratio_threshold = config.get_config("strategy", "volume_ratio_threshold", default=0.55)
        self.body_ratio_threshold = config.get_config("strategy", "body_ratio_threshold", default=0.3)
        self.shadow_ratio_threshold = config.get_config("strategy", "shadow_ratio_threshold", default=0.5)
        self.range_ratio_threshold = config.get_config("strategy", "range_ratio_threshold", default=0.7)
        self.stop_loss_range_multiplier = config.get_config("strategy", "stop_loss_range_multiplier", default=0.6)
        self.engulfing_body_ratio_threshold = config.get_config("strategy", "engulfing_body_ratio_threshold", default=0.7)
        
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
        Handle 5-minute K-line close event (trigger for opening position and checking engulfing stop loss)
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        interval = kline_info['interval']
        
        logger.info(f"[STRATEGY] on_5m_kline_close called for {symbol} {interval}")
        
        # Check for engulfing stop loss if position exists
        if self.position_manager.has_position(symbol):
            await self._check_engulfing_stop_loss(symbol, kline_info)
        
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
        
    
    async def on_15m_kline_close(self, kline_info: Dict) -> None:
        """
        Handle 15-minute K-line close event (trigger for closing position)
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        
        logger.info(f"[STRATEGY] on_15m_kline_close called for {symbol}")
        
        # Check if there is any open position before attempting to close
        if not self.position_manager.has_position(symbol):
            logger.info(f"No open position for {symbol}, skipping close operation")
            # Reset cycle state even if no position
            self.position_manager.reset_cycle()
            logger.info(f"Cycle reset for {symbol} (no position to close)")
            return
        
        logger.info(f"15m K-line closed for {symbol}, closing all positions...")
        
        # Close all positions immediately asynchronously
        success = await self.trading_executor.close_all_positions(symbol)
        
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
    
    def _get_first_closed_kline_in_cycle(self, symbol: str, interval: str) -> Optional[Dict]:
        """
        Get the first closed K-line in the current 15m cycle for a given interval
        
        Args:
            symbol: Trading pair symbol
            interval: K-line interval (3m, 5m, etc.)
            
        Returns:
            First closed K-line in the current 15m cycle, or None
        """
        if self.position_manager.current_15m_start_time is None:
            logger.warning(f"No current 15m cycle start time set")
            return None
        
        cycle_start_time = self.position_manager.current_15m_start_time
        cycle_end_time = cycle_start_time + 15 * 60 * 1000  # 15 minutes in ms
        
        # Get all K-lines for this interval
        all_klines = self.data_handler.get_klines(symbol, interval)
        if not all_klines:
            logger.warning(f"No {interval} K-line data for {symbol}")
            return None
        
        # Filter K-lines that are:
        # 1. Within the current 15m cycle (open_time >= cycle_start_time and open_time < cycle_end_time)
        # 2. Closed (is_closed == True)
        cycle_klines = [
            k for k in all_klines
            if k['is_closed'] and cycle_start_time <= k['open_time'] < cycle_end_time
        ]
        
        if not cycle_klines:
            logger.warning(f"No closed {interval} K-lines in current 15m cycle for {symbol}")
            return None
        
        # Sort by open_time to get the first one
        cycle_klines.sort(key=lambda k: k['open_time'])
        first_kline = cycle_klines[0]
        
        logger.info(
            f"Found first closed {interval} K-line in current 15m cycle for {symbol}: "
            f"open_time={datetime.fromtimestamp(first_kline['open_time']/1000)}, "
            f"close_time={datetime.fromtimestamp(first_kline['close_time']/1000)}"
        )
        
        return first_kline
    
    def _check_volume_condition(self, symbol: str, current_kline: Dict) -> Tuple[bool, Dict]:
        """
        Check if the current 5m K-line volume meets the minimum requirement
        
        Args:
            symbol: Trading pair symbol
            current_kline: The current 5m K-line to check
            
        Returns:
            Tuple of (is_valid, volume_info) where volume_info contains:
            - current_volume: Current K-line volume
            - avg_volume_5: Average volume of last 5 K-lines
            - ratio_5: Current volume / avg_volume_5
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, {}
            
            # Filter only closed K-lines to match Binance's calculation
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if not closed_klines:
                logger.warning(f"No closed 5m K-line data for {symbol}")
                return False, {}
            
            # Find the index of current K-line in closed klines
            current_open_time = current_kline['open_time']
            current_index = -1
            for i, k in enumerate(closed_klines):
                if k['open_time'] == current_open_time:
                    current_index = i
                    break
            
            if current_index == -1:
                logger.warning(f"Current K-line not found in closed klines for {symbol}")
                return False, {}
            
            # Get closed K-lines including current (for MA calculation)
            # Binance updates indicators after K-line closes, including the just-closed K-line
            klines_for_ma = closed_klines[:current_index + 1]
            
            if len(klines_for_ma) < 5:
                logger.warning(f"Not enough closed K-lines for volume check: {len(klines_for_ma)} (need at least 5)")
                return False, {}
            
            # Calculate average volumes including the current K-line
            # MA5 = current + previous 4
            current_volume = current_kline['volume']
            avg_volume_5 = sum(k['volume'] for k in klines_for_ma[-5:]) / 5
            
            # Calculate ratio
            ratio_5 = current_volume / avg_volume_5 if avg_volume_5 > 0 else 0
            
            # Check if volume meets threshold
            is_valid = ratio_5 >= self.volume_ratio_threshold
            
            volume_info = {
                'current_volume': current_volume,
                'avg_volume_5': avg_volume_5,
                'ratio_5': ratio_5,
                'threshold': self.volume_ratio_threshold
            }
            
            logger.info(
                f"Volume check for {symbol}: "
                f"current={current_volume:.2f}, "
                f"avg_5={avg_volume_5:.2f} (ratio={ratio_5:.2f}), "
                f"threshold={self.volume_ratio_threshold}, "
                f"valid={is_valid}"
            )
            
            return is_valid, volume_info
            
        except Exception as e:
            logger.error(f"Error checking volume condition for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {}
    
    def _check_range_condition(self, symbol: str, current_kline: Dict) -> Tuple[bool, Dict]:
        """
        Check if the current 5m K-line range meets the minimum requirement
        
        Args:
            symbol: Trading pair symbol
            current_kline: The current 5m K-line to check
            
        Returns:
            Tuple of (is_valid, range_info) where range_info contains:
            - current_range: Current K-line range (high - low)
            - avg_range_5: Average range of last 5 K-lines
            - ratio_5: Current range / avg_range_5
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, {}
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if not closed_klines:
                logger.warning(f"No closed 5m K-line data for {symbol}")
                return False, {}
            
            # Find the index of current K-line in closed klines
            current_open_time = current_kline['open_time']
            current_index = -1
            for i, k in enumerate(closed_klines):
                if k['open_time'] == current_open_time:
                    current_index = i
                    break
            
            if current_index == -1:
                logger.warning(f"Current K-line not found in closed klines for {symbol}")
                return False, {}
            
            # Get closed K-lines including current (for MA calculation)
            klines_for_ma = closed_klines[:current_index + 1]
            
            if len(klines_for_ma) < 5:
                logger.warning(f"Not enough closed K-lines for range check: {len(klines_for_ma)} (need at least 5)")
                return False, {}
            
            # Calculate current range
            current_range = current_kline['high'] - current_kline['low']
            
            # Calculate average ranges including the current K-line
            # MA5 = current + previous 4
            avg_range_5 = sum(k['high'] - k['low'] for k in klines_for_ma[-5:]) / 5
            
            # Calculate ratio
            ratio_5 = current_range / avg_range_5 if avg_range_5 > 0 else 0
            
            # Check if range meets threshold
            is_valid = ratio_5 >= self.range_ratio_threshold
            
            range_info = {
                'current_range': current_range,
                'avg_range_5': avg_range_5,
                'ratio_5': ratio_5,
                'threshold': self.range_ratio_threshold
            }
            
            logger.info(
                f"Range check for {symbol}: "
                f"current={current_range:.2f}, "
                f"avg_5={avg_range_5:.2f} (ratio={ratio_5:.2f}), "
                f"threshold={self.range_ratio_threshold}, "
                f"valid={is_valid}"
            )
            
            return is_valid, range_info
            
        except Exception as e:
            logger.error(f"Error checking range condition for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {}
    
    def _check_body_ratio(self, kline: Dict) -> Tuple[bool, Dict]:
        """
        Check if the K-line body ratio meets the minimum requirement
        Also checks for excessive single-sided shadows
        
        Args:
            kline: K-line information dictionary
            
        Returns:
            Tuple of (is_valid, body_info) where body_info contains:
            - body: Body length (|close - open|)
            - range: Total range (high - low)
            - body_ratio: Body / range
            - upper_shadow: Upper shadow length
            - lower_shadow: Lower shadow length
            - upper_shadow_ratio: Upper shadow / range
            - lower_shadow_ratio: Lower shadow / range
            - threshold: Minimum body ratio threshold
        """
        try:
            open_price = kline.get('open', 0)
            close_price = kline.get('close', 0)
            high_price = kline.get('high', 0)
            low_price = kline.get('low', 0)
            
            # Calculate body and range
            body = abs(close_price - open_price)
            range_val = high_price - low_price
            
            # Avoid division by zero
            if range_val == 0:
                logger.warning(f"K-line range is zero, cannot calculate body ratio")
                return False, {}
            
            # Calculate body ratio
            body_ratio = body / range_val
            
            # Calculate shadows
            if close_price > open_price:  # Bullish candle
                upper_shadow = high_price - close_price
                lower_shadow = open_price - low_price
            else:  # Bearish candle
                upper_shadow = high_price - open_price
                lower_shadow = close_price - low_price
            
            # Calculate shadow ratios
            upper_shadow_ratio = upper_shadow / range_val if range_val > 0 else 0
            lower_shadow_ratio = lower_shadow / range_val if range_val > 0 else 0
            
            # Check if body ratio meets threshold
            body_valid = body_ratio >= self.body_ratio_threshold
            
            # Check for excessive single-sided shadows (prevent one-sided shadow from meeting condition)
            # If one shadow is too long (> shadow_ratio_threshold of range), reject the candle
            shadow_valid = upper_shadow_ratio < self.shadow_ratio_threshold and lower_shadow_ratio < self.shadow_ratio_threshold
            
            is_valid = body_valid and shadow_valid
            
            body_info = {
                'body': body,
                'range': range_val,
                'body_ratio': body_ratio,
                'upper_shadow': upper_shadow,
                'lower_shadow': lower_shadow,
                'upper_shadow_ratio': upper_shadow_ratio,
                'lower_shadow_ratio': lower_shadow_ratio,
                'threshold': self.body_ratio_threshold,
                'shadow_ratio_threshold': self.shadow_ratio_threshold
            }
            
            logger.info(
                f"Body ratio check: "
                f"body={body:.2f}, "
                f"range={range_val:.2f}, "
                f"body_ratio={body_ratio:.4f}, "
                f"upper_shadow={upper_shadow:.2f} ({upper_shadow_ratio:.2%}), "
                f"lower_shadow={lower_shadow:.2f} ({lower_shadow_ratio:.2%}), "
                f"threshold={self.body_ratio_threshold}, "
                f"body_valid={body_valid}, "
                f"shadow_valid={shadow_valid}, "
                f"valid={is_valid}"
            )
            
            return is_valid, body_info
            
        except Exception as e:
            logger.error(f"Error checking body ratio: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {}
    
    async def _check_and_open_position(self, symbol: str) -> None:
        """
        Check entry conditions and open position if met
        
        Args:
            symbol: Trading pair symbol
        """
        logger.info(f"[STRATEGY] _check_and_open_position called for {symbol}")
        try:
            # Get 5m K-line direction for the first closed 5m K-line in current 15m cycle
            kline_5m = self._get_first_closed_kline_in_cycle(symbol, "5m")
            if kline_5m is None:
                logger.warning(f"No closed 5m K-line in current 15m cycle for {symbol}")
                return
            
            direction_5m = self.technical_analyzer.get_kline_direction(kline_5m)
            if direction_5m is None:
                logger.warning(f"Could not determine 5m K-line direction for {symbol}")
                return
            
            # Check volume condition
            volume_valid, volume_info = self._check_volume_condition(symbol, kline_5m)
            if not volume_valid:
                logger.warning(f"Volume condition not met for {symbol}")
                # Send notification with volume info
                current_price = self.data_handler.get_current_price(symbol)
                await self.telegram_client.send_indicator_analysis(
                    symbol=symbol,
                    sar_direction=None,
                    direction_3m=None,
                    direction_5m=direction_5m,
                    sar_value=None,
                    current_price=current_price,
                    decision='NO_TRADE',
                    volume_info=volume_info,
                    range_info=None,
                    body_info=None,
                    kline_time=kline_5m.get('close_time')
                )
                return
            
            # Check range condition
            range_valid, range_info = self._check_range_condition(symbol, kline_5m)
            if not range_valid:
                logger.warning(f"Range condition not met for {symbol}")
                # Send notification with range info
                current_price = self.data_handler.get_current_price(symbol)
                await self.telegram_client.send_indicator_analysis(
                    symbol=symbol,
                    sar_direction=None,
                    direction_3m=None,
                    direction_5m=direction_5m,
                    sar_value=None,
                    current_price=current_price,
                    decision='NO_TRADE',
                    volume_info=volume_info,
                    range_info=range_info,
                    body_info=None,
                    kline_time=kline_5m.get('close_time')
                )
                return
            
            # Check body ratio condition
            body_valid, body_info = self._check_body_ratio(kline_5m)
            if not body_valid:
                logger.warning(f"Body ratio condition not met for {symbol}")
                # Send notification with body info
                current_price = self.data_handler.get_current_price(symbol)
                await self.telegram_client.send_indicator_analysis(
                    symbol=symbol,
                    sar_direction=None,
                    direction_3m=None,
                    direction_5m=direction_5m,
                    sar_value=None,
                    current_price=current_price,
                    decision='NO_TRADE',
                    volume_info=volume_info,
                    range_info=range_info,
                    body_info=body_info,
                    kline_time=kline_5m.get('close_time')
                )
                return
            
            # Log direction for debugging
            logger.info(f"5m K-line direction for {symbol}: {direction_5m}")
            
            # Get current price for notification
            current_price = self.data_handler.get_current_price(symbol)
            
            # Send indicator analysis notification with decision
            decision = 'LONG' if direction_5m == 'UP' else 'SHORT'
            await self.telegram_client.send_indicator_analysis(
                symbol=symbol,
                sar_direction=None,
                direction_3m=None,
                direction_5m=direction_5m,
                sar_value=None,
                current_price=current_price,
                decision=decision,
                volume_info=volume_info,
                range_info=range_info,
                body_info=body_info,
                kline_time=kline_5m.get('close_time')
            )
            
            # Calculate stop loss price based on 5m K-line range
            stop_loss_price = self._calculate_stop_loss_price(
                kline_5m,
                direction_5m,
                range_info.get('current_range', 0)
            )
            
            # Open position with volume info, range info, stop loss and entry kline
            if direction_5m == 'UP':
                await self._open_long_position(symbol, volume_info, range_info, stop_loss_price, kline_5m, kline_5m.get('close_time'))
            else:  # DOWN
                await self._open_short_position(symbol, volume_info, range_info, stop_loss_price, kline_5m, kline_5m.get('close_time'))
            
            # Add explicit log to confirm completion of check
            logger.info(f"[STRATEGY] _check_and_open_position completed for {symbol}")
                
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    def _calculate_stop_loss_price(self, kline: Dict, direction: str, current_range: float) -> Optional[float]:
        """
        Calculate stop loss price based on 5m K-line range
        
        Args:
            kline: 5m K-line data
            direction: 'UP' or 'DOWN'
            current_range: Current K-line range (high - low)
            
        Returns:
            Stop loss price or None
        """
        try:
            close_price = kline.get('close', 0)
            
            if current_range == 0:
                logger.warning(f"K-line range is zero, cannot calculate stop loss")
                return None
            
            # Stop loss distance = 5m K-line range * multiplier
            stop_loss_distance = current_range * self.stop_loss_range_multiplier
            
            if direction == 'UP':
                # For long position, stop loss is below entry price
                stop_loss_price = close_price - stop_loss_distance
            else:  # DOWN
                # For short position, stop loss is above entry price
                stop_loss_price = close_price + stop_loss_distance
            
            logger.info(
                f"Stop loss calculated: "
                f"direction={direction}, "
                f"close_price={close_price:.2f}, "
                f"range={current_range:.2f}, "
                f"multiplier={self.stop_loss_range_multiplier}, "
                f"stop_loss_distance={stop_loss_distance:.2f}, "
                f"stop_loss_price={stop_loss_price:.2f}"
            )
            
            return stop_loss_price
            
        except Exception as e:
            logger.error(f"Error calculating stop loss price: {e}")
            return None
    
    async def _open_long_position(self, symbol: str, volume_info: Optional[Dict] = None, range_info: Optional[Dict] = None,
                                   stop_loss_price: Optional[float] = None, entry_kline: Optional[Dict] = None,
                                   kline_time: Optional[int] = None) -> None:
        """
        Open a long position
        
        Args:
            symbol: Trading pair symbol
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            stop_loss_price: Stop loss price (optional)
            entry_kline: Entry K-line data (optional)
            kline_time: K-line timestamp in milliseconds (optional)
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
            result = self.trading_executor.open_long_position(symbol, quantity)
            
            if result:
                # Extract order and position calculation info
                order = result.get('order')
                position_calc_info = result.get('position_calc_info')
                final_quantity = result.get('final_quantity', quantity)
                final_price = result.get('final_price', current_price)
                
                # Record position with entry kline
                self.position_manager.open_position(
                    symbol=symbol,
                    side='LONG',
                    entry_price=final_price,
                    quantity=final_quantity,
                    entry_kline=entry_kline
                )
                
                logger.info(f"Long position opened successfully for {symbol}")
                
                # Set stop loss order if stop loss price is provided
                if stop_loss_price is not None:
                    await self._set_stop_loss_order(symbol, 'LONG', final_quantity, stop_loss_price)
                
                # Send trade notification with volume info, range info, stop loss and position calculation info
                await self.telegram_client.send_trade_notification(
                    symbol=symbol,
                    side='LONG',
                    price=final_price,
                    quantity=final_quantity,
                    leverage=self.config.leverage,
                    volume_info=volume_info,
                    range_info=range_info,
                    stop_loss_price=stop_loss_price,
                    position_calc_info=position_calc_info,
                    kline_time=kline_time
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
    
    async def _open_short_position(self, symbol: str, volume_info: Optional[Dict] = None, range_info: Optional[Dict] = None,
                                    stop_loss_price: Optional[float] = None, entry_kline: Optional[Dict] = None,
                                    kline_time: Optional[int] = None) -> None:
        """
        Open a short position
        
        Args:
            symbol: Trading pair symbol
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            stop_loss_price: Stop loss price (optional)
            entry_kline: Entry K-line data (optional)
            kline_time: K-line timestamp in milliseconds (optional)
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
            result = self.trading_executor.open_short_position(symbol, quantity)
            
            if result:
                # Extract order and position calculation info
                order = result.get('order')
                position_calc_info = result.get('position_calc_info')
                final_quantity = result.get('final_quantity', quantity)
                final_price = result.get('final_price', current_price)
                
                # Record position with entry kline
                self.position_manager.open_position(
                    symbol=symbol,
                    side='SHORT',
                    entry_price=final_price,
                    quantity=final_quantity,
                    entry_kline=entry_kline
                )
                
                logger.info(f"Short position opened successfully for {symbol}")
                
                # Set stop loss order if stop loss price is provided
                if stop_loss_price is not None:
                    await self._set_stop_loss_order(symbol, 'SHORT', final_quantity, stop_loss_price)
                
                # Send trade notification with volume info, range info, stop loss and position calculation info
                await self.telegram_client.send_trade_notification(
                    symbol=symbol,
                    side='SHORT',
                    price=final_price,
                    quantity=final_quantity,
                    leverage=self.config.leverage,
                    volume_info=volume_info,
                    range_info=range_info,
                    stop_loss_price=stop_loss_price,
                    position_calc_info=position_calc_info,
                    kline_time=kline_time
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
    
    async def _set_stop_loss_order(self, symbol: str, side: str, quantity: float, stop_loss_price: float) -> bool:
        """
        Set stop loss order for a position
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            quantity: Position quantity
            stop_loss_price: Stop loss price
            
        Returns:
            True if successful
        """
        try:
            import asyncio
            from binance.enums import SIDE_SELL, SIDE_BUY, ORDER_TYPE_STOP_MARKET
            
            if side == 'LONG':
                # For long position, stop loss is a SELL order
                order = await asyncio.to_thread(
                    self.trading_executor.client.futures_create_order,
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_STOP_MARKET,
                    stopPrice=stop_loss_price,
                    quantity=quantity,
                    reduceOnly=True
                )
                logger.info(f"Stop loss order set for LONG position {symbol}: {order}")
            else:  # SHORT
                # For short position, stop loss is a BUY order
                order = await asyncio.to_thread(
                    self.trading_executor.client.futures_create_order,
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_STOP_MARKET,
                    stopPrice=stop_loss_price,
                    quantity=quantity,
                    reduceOnly=True
                )
                logger.info(f"Stop loss order set for SHORT position {symbol}: {order}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting stop loss order for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _check_engulfing_stop_loss(self, symbol: str, current_kline: Dict) -> None:
        """
        Check if the current 5m K-line forms an engulfing pattern that triggers stop loss
        
        Args:
            symbol: Trading pair symbol
            current_kline: Current 5m K-line that just closed
        """
        try:
            # Get position information
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            position_side = position['side']
            entry_kline = position.get('entry_kline')
            
            if not entry_kline:
                logger.warning(f"No entry kline stored for position {symbol}")
                return
            
            # Get current kline direction
            current_direction = self.technical_analyzer.get_kline_direction(current_kline)
            if current_direction is None:
                return
            
            # Get entry kline direction
            entry_direction = self.technical_analyzer.get_kline_direction(entry_kline)
            if entry_direction is None:
                return
            
            # Check if directions are opposite (engulfing pattern)
            if current_direction == entry_direction:
                logger.debug(f"Current kline direction {current_direction} is same as entry direction {entry_direction}, no engulfing")
                return
            
            # Calculate body lengths
            entry_body = abs(entry_kline['close'] - entry_kline['open'])
            current_body = abs(current_kline['close'] - current_kline['open'])
            
            if entry_body == 0:
                logger.warning(f"Entry kline body is zero, cannot calculate engulfing ratio")
                return
            
            # Calculate engulfing ratio
            engulfing_ratio = current_body / entry_body
            
            # Check if engulfing ratio meets threshold
            if engulfing_ratio >= self.engulfing_body_ratio_threshold:
                logger.warning(
                    f"Engulfing stop loss triggered for {symbol}: "
                    f"entry_direction={entry_direction}, current_direction={current_direction}, "
                    f"entry_body={entry_body:.2f}, current_body={current_body:.2f}, "
                    f"engulfing_ratio={engulfing_ratio:.2f}, threshold={self.engulfing_body_ratio_threshold}"
                )
                
                # Close position immediately
                success = await self.trading_executor.close_all_positions(symbol)
                
                if success:
                    # Reset cycle state
                    self.position_manager.reset_cycle()
                    
                    # Send stop loss notification
                    await self.telegram_client.send_error_message(
                        f"反向吞没止损触发 - {symbol}\n"
                        f"开仓方向: {entry_direction}\n"
                        f"当前方向: {current_direction}\n"
                        f"吞没比例: {engulfing_ratio:.2%}\n"
                        f"阈值: {self.engulfing_body_ratio_threshold:.0%}",
                        "Engulfing Stop Loss"
                    )
                    
                    logger.info(f"Position closed due to engulfing stop loss for {symbol}")
                else:
                    logger.error(f"Failed to close position due to engulfing stop loss for {symbol}")
            else:
                logger.debug(
                    f"Engulfing ratio {engulfing_ratio:.2f} below threshold {self.engulfing_body_ratio_threshold}, no stop loss"
                )
                
        except Exception as e:
            logger.error(f"Error checking engulfing stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())