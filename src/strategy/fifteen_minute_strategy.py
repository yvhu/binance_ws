"""
5-Minute K-Line Trading Strategy
Implements the 5m K-line trading strategy with dynamic position management
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


class FiveMinuteStrategy:
    """5-minute K-line trading strategy"""
    
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
        Initialize 5-minute strategy
        
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
        self.check_interval = config.get_config("strategy", "check_interval", default="5m")
        self.volume_ratio_threshold = config.get_config("strategy", "volume_ratio_threshold", default=0.55)
        self.body_ratio_threshold = config.get_config("strategy", "body_ratio_threshold", default=0.3)
        self.shadow_ratio_threshold = config.get_config("strategy", "shadow_ratio_threshold", default=0.5)
        self.range_ratio_threshold = config.get_config("strategy", "range_ratio_threshold", default=0.7)
        self.stop_loss_range_multiplier = config.get_config("strategy", "stop_loss_range_multiplier", default=0.8)
        self.stop_loss_min_distance_percent = config.get_config("strategy", "stop_loss_min_distance_percent", default=0.003)
        self.engulfing_body_ratio_threshold = config.get_config("strategy", "engulfing_body_ratio_threshold", default=0.7)
        self.trend_filter_enabled = config.get_config("strategy", "trend_filter_enabled", default=True)
        self.trend_filter_ma_period = config.get_config("strategy", "trend_filter_ma_period", default=20)
        
        logger.info("5-minute strategy initialized")
    
    async def on_5m_kline_close(self, kline_info: Dict) -> None:
        """
        Handle 5-minute K-line close event (trigger for opening position and checking stop losses)
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        interval = kline_info['interval']
        
        logger.info(f"[STRATEGY] on_5m_kline_close called for {symbol} {interval}")
        
        # Check for stop losses if position exists
        if self.position_manager.has_position(symbol):
            # Check moving stop loss (update stop loss order based on latest 5m K-line)
            await self._update_moving_stop_loss(symbol, kline_info)
            
            # Check engulfing stop loss
            await self._check_engulfing_stop_loss(symbol, kline_info)
        
        # Check if position can be opened (no existing position)
        if self.position_manager.has_position(symbol):
            logger.info(f"Position already exists for {symbol}, skipping entry check")
            return
        
        logger.info(f"5m K-line closed for {symbol}, checking entry conditions...")
        
        # Execute strategy logic
        await self._check_and_open_position(symbol, kline_info)
    
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
                f"upper_shadow={upper_shadow:.2f} ({upper_shadow_ratio*100:.2f}%), "
                f"lower_shadow={lower_shadow:.2f} ({lower_shadow_ratio*100:.2f}%), "
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
    
    def _check_trend_filter(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if the kline direction aligns with the trend based on MA
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, trend_info)
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.trend_filter_ma_period + 1:
                logger.warning(f"Not enough closed K-lines for trend filter: {len(closed_klines)} (need at least {self.trend_filter_ma_period + 1})")
                return False, None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Check trend filter
            trend_valid, trend_info = self.technical_analyzer.check_trend_filter(
                df,
                kline_direction,
                ma_period=self.trend_filter_ma_period
            )
            
            return trend_valid, trend_info
            
        except Exception as e:
            logger.error(f"Error checking trend filter for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    async def _check_and_open_position(self, symbol: str, kline_5m: Dict) -> None:
        """
        Check entry conditions and open position if met
        
        Args:
            symbol: Trading pair symbol
            kline_5m: The current closed 5m K-line
        """
        logger.info(f"[STRATEGY] _check_and_open_position called for {symbol}")
        try:
            # Use the provided 5m K-line directly
            if kline_5m is None:
                logger.warning(f"No 5m K-line provided for {symbol}")
                return
            
            direction_5m = self.technical_analyzer.get_kline_direction(kline_5m)
            if direction_5m is None:
                logger.warning(f"Could not determine 5m K-line direction for {symbol}")
                return
            
            # Check all conditions and collect all information
            volume_valid, volume_info = self._check_volume_condition(symbol, kline_5m)
            range_valid, range_info = self._check_range_condition(symbol, kline_5m)
            body_valid, body_info = self._check_body_ratio(kline_5m)
            
            # Check trend filter if enabled
            trend_valid = True
            trend_info = None
            if self.trend_filter_enabled:
                trend_valid, trend_info = self._check_trend_filter(symbol, direction_5m)
            
            # Determine if all conditions are met
            all_conditions_met = volume_valid and range_valid and body_valid and trend_valid
            
            logger.info(
                f"[STRATEGY] Condition check for {symbol}: "
                f"volume_valid={volume_valid}, "
                f"range_valid={range_valid}, "
                f"body_valid={body_valid}, "
                f"trend_valid={trend_valid}, "
                f"all_conditions_met={all_conditions_met}"
            )
            
            # Get current price for notification
            current_price = self.data_handler.get_current_price(symbol)
            
            # Send indicator analysis notification with all condition information
            if all_conditions_met:
                logger.info(f"[STRATEGY] All conditions met for {symbol}, preparing to open position...")
                # All conditions met - send trade decision
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
                    trend_info=trend_info,
                    kline_time=kline_5m.get('close_time')
                )
                
                # Calculate stop loss price based on 5m K-line range
                stop_loss_price = self._calculate_stop_loss_price(
                    kline_5m,
                    direction_5m,
                    range_info.get('current_range', 0)
                )
                
                # Open position with volume info, range info, stop loss and entry kline
                logger.info(f"[STRATEGY] Opening position for {symbol}, direction={direction_5m}")
                if direction_5m == 'UP':
                    logger.info(f"[STRATEGY] Calling _open_long_position for {symbol}")
                    await self._open_long_position(symbol, volume_info, range_info, stop_loss_price, kline_5m, kline_5m.get('close_time'))
                    logger.info(f"[STRATEGY] _open_long_position completed for {symbol}")
                else:  # DOWN
                    logger.info(f"[STRATEGY] Calling _open_short_position for {symbol}")
                    await self._open_short_position(symbol, volume_info, range_info, stop_loss_price, kline_5m, kline_5m.get('close_time'))
                    logger.info(f"[STRATEGY] _open_short_position completed for {symbol}")
            else:
                # Some conditions not met - send no trade notification with all condition info
                logger.info(f"Not all conditions met for {symbol}: volume={volume_valid}, range={range_valid}, body={body_valid}, trend={trend_valid}")
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
                    trend_info=trend_info,
                    kline_time=kline_5m.get('close_time')
                )
            
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
            
            # Calculate stop loss distance percentage for risk-based position sizing
            stop_loss_distance_percent = None
            if stop_loss_price is not None and current_price > 0:
                # For long position, stop loss is below entry price
                stop_loss_distance_percent = (current_price - stop_loss_price) / current_price
                # Ensure minimum stop loss distance
                min_stop_loss_distance = current_price * self.stop_loss_min_distance_percent
                actual_stop_loss_distance = max(current_price - stop_loss_price, min_stop_loss_distance)
                stop_loss_distance_percent = actual_stop_loss_distance / current_price
                logger.info(
                    f"Stop loss distance for {symbol}: "
                    f"price={current_price:.2f}, "
                    f"stop_loss={stop_loss_price:.2f}, "
                    f"distance={actual_stop_loss_distance:.2f} ({stop_loss_distance_percent*100:.2f}%)"
                )
            
            # Calculate position size with risk management
            quantity = self.trading_executor.calculate_position_size(
                current_price,
                symbol,
                stop_loss_distance_percent=stop_loss_distance_percent
            )
            if quantity is None:
                logger.error(f"Could not calculate position size for {symbol}")
                return
            
            # Execute order with retry logic
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
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
                    stop_loss_set = False
                    if stop_loss_price is not None:
                        stop_loss_set = await self._set_stop_loss_order(symbol, 'LONG', final_quantity, stop_loss_price)
                        
                        if not stop_loss_set:
                            # Stop loss order creation failed - this is a critical error
                            logger.error(f"CRITICAL: Failed to set stop loss order for {symbol} after opening position!")
                            
                            # Send critical error notification
                            await self.telegram_client.send_error_message(
                                f"⚠️ CRITICAL: Long position opened for {symbol} but stop loss order failed!\n"
                                f"Position: {final_quantity} @ {final_price:.2f}\n"
                                f"Stop loss price: {stop_loss_price:.2f}\n"
                                f"⚠️ Position has NO stop loss protection!",
                                "Stop Loss Order Failed"
                            )
                    
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
                    break  # Success, exit retry loop
                else:
                    logger.error(f"Failed to open long position for {symbol} (attempt {attempt + 1}/{max_retries})")
                    
                    if attempt < max_retries - 1:
                        # Cancel any remaining orders before retry
                        import asyncio
                        await asyncio.to_thread(self.trading_executor.cancel_all_orders, symbol)
                        await asyncio.sleep(retry_delay)
                        logger.info(f"Retrying to open long position for {symbol}...")
                    else:
                        # All retries failed
                        logger.error(f"All {max_retries} attempts failed to open long position for {symbol}")
                        
                        # Send error notification
                        await self.telegram_client.send_error_message(
                            f"Failed to open long position for {symbol} after {max_retries} attempts",
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
            
            # Calculate stop loss distance percentage for risk-based position sizing
            stop_loss_distance_percent = None
            if stop_loss_price is not None and current_price > 0:
                # For short position, stop loss is above entry price
                stop_loss_distance_percent = (stop_loss_price - current_price) / current_price
                # Ensure minimum stop loss distance
                min_stop_loss_distance = current_price * self.stop_loss_min_distance_percent
                actual_stop_loss_distance = max(stop_loss_price - current_price, min_stop_loss_distance)
                stop_loss_distance_percent = actual_stop_loss_distance / current_price
                logger.info(
                    f"Stop loss distance for {symbol}: "
                    f"price={current_price:.2f}, "
                    f"stop_loss={stop_loss_price:.2f}, "
                    f"distance={actual_stop_loss_distance:.2f} ({stop_loss_distance_percent*100:.2f}%)"
                )
            
            # Calculate position size with risk management
            quantity = self.trading_executor.calculate_position_size(
                current_price,
                symbol,
                stop_loss_distance_percent=stop_loss_distance_percent
            )
            if quantity is None:
                logger.error(f"Could not calculate position size for {symbol}")
                return
            
            # Execute order with retry logic
            max_retries = 3
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
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
                    stop_loss_set = False
                    if stop_loss_price is not None:
                        stop_loss_set = await self._set_stop_loss_order(symbol, 'SHORT', final_quantity, stop_loss_price)
                        
                        if not stop_loss_set:
                            # Stop loss order creation failed - this is a critical error
                            logger.error(f"CRITICAL: Failed to set stop loss order for {symbol} after opening position!")
                            
                            # Send critical error notification
                            await self.telegram_client.send_error_message(
                                f"⚠️ CRITICAL: Short position opened for {symbol} but stop loss order failed!\n"
                                f"Position: {final_quantity} @ {final_price:.2f}\n"
                                f"Stop loss price: {stop_loss_price:.2f}\n"
                                f"⚠️ Position has NO stop loss protection!",
                                "Stop Loss Order Failed"
                            )
                    
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
                    break  # Success, exit retry loop
                else:
                    logger.error(f"Failed to open short position for {symbol} (attempt {attempt + 1}/{max_retries})")
                    
                    if attempt < max_retries - 1:
                        # Cancel any remaining orders before retry
                        import asyncio
                        await asyncio.to_thread(self.trading_executor.cancel_all_orders, symbol)
                        await asyncio.sleep(retry_delay)
                        logger.info(f"Retrying to open short position for {symbol}...")
                    else:
                        # All retries failed
                        logger.error(f"All {max_retries} attempts failed to open short position for {symbol}")
                        
                        # Send error notification
                        await self.telegram_client.send_error_message(
                            f"Failed to open short position for {symbol} after {max_retries} attempts",
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
            from binance.enums import SIDE_SELL, SIDE_BUY
            # Use string for order type to avoid enum compatibility issues
            ORDER_TYPE_STOP_MARKET = "STOP_MARKET"
            
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
    
    async def _update_moving_stop_loss(self, symbol: str, current_kline: Dict) -> None:
        """
        Update moving stop loss based on the latest 5m K-line range
        This is a moving stop loss - recalculates stop loss price based on the latest 5m K-line
        
        Args:
            symbol: Trading pair symbol
            current_kline: Current 5m K-line that just closed
        """
        try:
            import asyncio
            from binance.enums import SIDE_SELL, SIDE_BUY
            # Use string for order type to avoid enum compatibility issues
            ORDER_TYPE_STOP_MARKET = "STOP_MARKET"
            
            # Get position information
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            position_side = position['side']
            quantity = position['quantity']
            
            # Calculate current range of the latest 5m K-line
            current_range = current_kline['high'] - current_kline['low']
            
            if current_range == 0:
                logger.warning(f"Current K-line range is zero, cannot update moving stop loss")
                return
            
            # Calculate new stop loss distance based on latest 5m K-line range
            stop_loss_distance = current_range * self.stop_loss_range_multiplier
            
            # Get current price
            current_price = self.data_handler.get_current_price(symbol)
            if current_price is None:
                logger.warning(f"Could not get current price for {symbol}")
                return
            
            # Calculate new stop loss price
            if position_side == 'LONG':
                # For long position, stop loss is below current price
                new_stop_loss_price = current_price - stop_loss_distance
            else:  # SHORT
                # For short position, stop loss is above current price
                new_stop_loss_price = current_price + stop_loss_distance
            
            logger.info(
                f"Moving stop loss update for {symbol}: "
                f"side={position_side}, "
                f"current_price={current_price:.2f}, "
                f"current_range={current_range:.2f}, "
                f"multiplier={self.stop_loss_range_multiplier}, "
                f"stop_loss_distance={stop_loss_distance:.2f}, "
                f"new_stop_loss_price={new_stop_loss_price:.2f}"
            )
            
            # Check if there's an existing stop loss order
            has_stop_loss = await asyncio.to_thread(
                self.trading_executor.has_stop_loss_order,
                symbol
            )
            
            if has_stop_loss:
                # Cancel existing stop loss orders
                logger.info(f"Cancelling existing stop loss order for {symbol}")
                cancel_success = await asyncio.to_thread(
                    self.trading_executor.cancel_all_stop_loss_orders,
                    symbol
                )
                
                if not cancel_success:
                    logger.error(f"Failed to cancel stop loss order for {symbol}")
                    return
                
                # Wait a moment for the cancellation to be processed
                await asyncio.sleep(0.5)
            
            # Create new stop loss order
            logger.info(f"Creating new stop loss order for {symbol} at {new_stop_loss_price:.2f}")
            
            if position_side == 'LONG':
                # For long position, stop loss is a SELL order
                order = await asyncio.to_thread(
                    self.trading_executor.client.futures_create_order,
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_STOP_MARKET,
                    stopPrice=new_stop_loss_price,
                    quantity=quantity,
                    reduceOnly=True
                )
            else:  # SHORT
                # For short position, stop loss is a BUY order
                order = await asyncio.to_thread(
                    self.trading_executor.client.futures_create_order,
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_STOP_MARKET,
                    stopPrice=new_stop_loss_price,
                    quantity=quantity,
                    reduceOnly=True
                )
            
            logger.info(f"Moving stop loss order created for {symbol}: {order}")
            
        except Exception as e:
            logger.error(f"Error updating moving stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _check_engulfing_stop_loss(self, symbol: str, current_kline: Dict) -> None:
        """
        Check if the current 5m K-line forms an engulfing pattern with the previous K-line that triggers stop loss
        This is a moving check - compares current K-line with the previous K-line, not the entry K-line
        
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
            
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < 2:
                logger.warning(f"Not enough closed K-lines for engulfing check: {len(closed_klines)} (need at least 2)")
                return
            
            # Find the index of current K-line in closed klines
            current_open_time = current_kline['open_time']
            current_index = -1
            for i, k in enumerate(closed_klines):
                if k['open_time'] == current_open_time:
                    current_index = i
                    break
            
            if current_index == -1:
                logger.warning(f"Current K-line not found in closed klines for {symbol}")
                return
            
            if current_index == 0:
                logger.warning(f"Current K-line is the first closed K-line, no previous K-line to compare")
                return
            
            # Get the previous K-line (the one before current)
            previous_kline = closed_klines[current_index - 1]
            
            # Get current kline direction
            current_direction = self.technical_analyzer.get_kline_direction(current_kline)
            if current_direction is None:
                return
            
            # Get previous kline direction
            previous_direction = self.technical_analyzer.get_kline_direction(previous_kline)
            if previous_direction is None:
                return
            
            # Check if directions are opposite (engulfing pattern)
            if current_direction == previous_direction:
                logger.debug(f"Current kline direction {current_direction} is same as previous direction {previous_direction}, no engulfing")
                return
            
            # Calculate body lengths
            previous_body = abs(previous_kline['close'] - previous_kline['open'])
            current_body = abs(current_kline['close'] - current_kline['open'])
            
            if previous_body == 0:
                logger.warning(f"Previous kline body is zero, cannot calculate engulfing ratio")
                return
            
            # Calculate engulfing ratio
            engulfing_ratio = current_body / previous_body
            
            # Check for true engulfing pattern (price range containment)
            # For a true engulfing pattern, the current K-line must completely contain the previous K-line's price range
            is_true_engulfing = False
            
            if current_direction == 'UP' and previous_direction == 'DOWN':
                # Current is bullish, previous is bearish
                # True engulfing: current open < previous close AND current close > previous open
                is_true_engulfing = (
                    current_kline['open'] < previous_kline['close'] and
                    current_kline['close'] > previous_kline['open']
                )
            elif current_direction == 'DOWN' and previous_direction == 'UP':
                # Current is bearish, previous is bullish
                # True engulfing: current open > previous close AND current close < previous open
                is_true_engulfing = (
                    current_kline['open'] > previous_kline['close'] and
                    current_kline['close'] < previous_kline['open']
                )
            
            if not is_true_engulfing:
                logger.debug(
                    f"Engulfing ratio {engulfing_ratio:.2f} meets threshold but not a true engulfing pattern: "
                    f"current_direction={current_direction}, previous_direction={previous_direction}, "
                    f"current_open={current_kline['open']:.2f}, current_close={current_kline['close']:.2f}, "
                    f"previous_open={previous_kline['open']:.2f}, previous_close={previous_kline['close']:.2f}"
                )
                return
            
            # Check if engulfing ratio meets threshold
            if engulfing_ratio >= self.engulfing_body_ratio_threshold:
                logger.warning(
                    f"Engulfing stop loss triggered for {symbol}: "
                    f"previous_direction={previous_direction}, current_direction={current_direction}, "
                    f"previous_body={previous_body:.2f}, current_body={current_body:.2f}, "
                    f"engulfing_ratio={engulfing_ratio:.2f}, threshold={self.engulfing_body_ratio_threshold}"
                )
                
                # Close position immediately
                success = await self.trading_executor.close_all_positions(symbol)
                
                if success:
                    # Get position details for notification
                    entry_price = position.get('entry_price', 0)
                    quantity = position.get('quantity', 0)
                    current_price = self.data_handler.get_current_price(symbol)
                    
                    # Calculate PnL
                    pnl = 0.0
                    if current_price and entry_price > 0:
                        if position_side == 'LONG':
                            pnl = (current_price - entry_price) * quantity
                        else:  # SHORT
                            pnl = (entry_price - current_price) * quantity
                    
                    # Send stop loss notification with detailed information
                    await self.telegram_client.send_close_notification(
                        symbol=symbol,
                        side=position_side,
                        entry_price=entry_price,
                        exit_price=current_price if current_price else 0,
                        quantity=quantity,
                        pnl=pnl,
                        close_reason=f"反向吞没止损触发\n"
                                   f"上一根K线方向: {previous_direction}\n"
                                   f"当前K线方向: {current_direction}\n"
                                   f"上一根K线实体: {previous_body:.2f}\n"
                                   f"当前K线实体: {current_body:.2f}\n"
                                   f"吞没比例: {engulfing_ratio*100:.2f}%\n"
                                   f"阈值: {self.engulfing_body_ratio_threshold*100:.0f}%"
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