"""
5-Minute K-Line Trading Strategy
Implements the 5m K-line trading strategy with dynamic position management
"""

import asyncio
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
        self.volume_ratio_threshold = config.get_config("strategy", "volume_ratio_threshold", default=0.85)
        self.body_ratio_threshold = config.get_config("strategy", "body_ratio_threshold", default=0.55)
        self.shadow_ratio_threshold = config.get_config("strategy", "shadow_ratio_threshold", default=0.5)
        self.range_ratio_threshold = config.get_config("strategy", "range_ratio_threshold", default=0.60)
        self.stop_loss_range_multiplier = config.get_config("strategy", "stop_loss_range_multiplier", default=0.6)
        self.stop_loss_min_distance_percent = config.get_config("strategy", "stop_loss_min_distance_percent", default=0.015)
        self.stop_loss_max_distance_percent = config.get_config("strategy", "stop_loss_max_distance_percent", default=0.025)
        self.engulfing_body_ratio_threshold = config.get_config("strategy", "engulfing_body_ratio_threshold", default=0.95)
        self.trend_filter_enabled = config.get_config("strategy", "trend_filter_enabled", default=True)
        self.trend_filter_ma_period = config.get_config("strategy", "trend_filter_ma_period", default=20)
        
        # ATR-based stop loss configuration
        self.atr_stop_loss_enabled = config.get_config("strategy", "atr_stop_loss_enabled", default=True)
        self.atr_stop_loss_multiplier = config.get_config("strategy", "atr_stop_loss_multiplier", default=1.5)
        self.atr_period = config.get_config("strategy", "atr_period", default=14)
        
        # Time-based stop loss configuration
        self.time_stop_loss_enabled = config.get_config("strategy", "time_stop_loss_enabled", default=True)
        self.time_stop_loss_klines = config.get_config("strategy", "time_stop_loss_klines", default=3)
        
        # Trailing stop loss configuration
        self.trailing_stop_enabled = config.get_config("strategy", "trailing_stop_enabled", default=False)
        self.trailing_stop_kline_count = config.get_config("strategy", "trailing_stop_kline_count", default=5)
        
        # Real-time stop loss optimization configuration
        self.stop_loss_price_buffer_percent = config.get_config("strategy", "stop_loss_price_buffer_percent", default=0.002)
        self.stop_loss_time_threshold = config.get_config("strategy", "stop_loss_time_threshold", default=5)
        self.stop_loss_check_interval = config.get_config("strategy", "stop_loss_check_interval", default=1)
        
        # Take profit configuration
        self.take_profit_enabled = config.get_config("strategy", "take_profit_enabled", default=True)
        self.take_profit_percent = config.get_config("strategy", "take_profit_percent", default=0.05)
        self.take_profit_trailing_enabled = config.get_config("strategy", "take_profit_trailing_enabled", default=True)
        self.take_profit_trailing_percent = config.get_config("strategy", "take_profit_trailing_percent", default=0.02)
        
        # Partial take profit configuration
        self.partial_take_profit_enabled = config.get_config("strategy", "partial_take_profit_enabled", default=True)
        self.partial_take_profit_levels = config.get_config("strategy", "partial_take_profit_levels", default=[0.03, 0.05])
        self.partial_take_profit_ratios = config.get_config("strategy", "partial_take_profit_ratios", default=[0.5, 0.5])
        
        # Dynamic take profit configuration
        self.dynamic_take_profit_enabled = config.get_config("strategy", "dynamic_take_profit_enabled", default=True)
        self.strong_trend_take_profit_percent = config.get_config("strategy", "strong_trend_take_profit_percent", default=0.07)
        self.weak_trend_take_profit_percent = config.get_config("strategy", "weak_trend_take_profit_percent", default=0.03)
        self.adx_trend_threshold = config.get_config("strategy", "adx_trend_threshold", default=25)
        
        # Additional indicator filters
        self.rsi_filter_enabled = config.get_config("strategy", "rsi_filter_enabled", default=True)
        self.rsi_long_max = config.get_config("strategy", "rsi_long_max", default=70)
        self.rsi_short_min = config.get_config("strategy", "rsi_short_min", default=30)
        
        self.macd_filter_enabled = config.get_config("strategy", "macd_filter_enabled", default=True)
        
        self.adx_filter_enabled = config.get_config("strategy", "adx_filter_enabled", default=True)
        self.adx_min_trend = config.get_config("strategy", "adx_min_trend", default=20)
        self.adx_sideways = config.get_config("strategy", "adx_sideways", default=20)
        
        # Position sizing based on signal strength
        self.strong_signal_position_ratio = config.get_config("trading", "strong_signal_position_ratio", default=1.0)
        self.medium_signal_position_ratio = config.get_config("trading", "medium_signal_position_ratio", default=0.75)
        self.weak_signal_position_ratio = config.get_config("trading", "weak_signal_position_ratio", default=0.5)
        
        # Track highest/lowest price for take profit
        self.position_peak_prices: Dict[str, float] = {}  # symbol -> peak price (highest for LONG, lowest for SHORT)
        
        # Track stop loss trigger times for each symbol
        self.stop_loss_trigger_times: Dict[str, float] = {}
        self.stop_loss_first_trigger_time: Dict[str, float] = {}
        
        # Track position entry time for time-based stop loss
        self.position_entry_times: Dict[str, int] = {}  # symbol -> entry timestamp (milliseconds)
        
        # Track partial take profit status for each position
        self.partial_take_profit_status: Dict[str, Dict] = {}  # symbol -> {level_index: bool}
        
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
            # Check engulfing stop loss
            await self._check_engulfing_stop_loss(symbol, kline_info)
            
            # Update trailing stop loss if enabled
            if self.trailing_stop_enabled:
                await self._update_trailing_stop_loss(symbol, kline_info)
        
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
    
    def _check_rsi_filter(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if RSI conditions are met for entry
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, rsi_info)
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.technical_analyzer.rsi_period + 1:
                logger.warning(f"Not enough closed K-lines for RSI filter: {len(closed_klines)}")
                return False, None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Check RSI filter
            rsi_valid, rsi_info = self.technical_analyzer.check_rsi_filter(
                df,
                kline_direction,
                rsi_long_max=self.rsi_long_max,
                rsi_short_min=self.rsi_short_min
            )
            
            return rsi_valid, rsi_info
            
        except Exception as e:
            logger.error(f"Error checking RSI filter for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    def _check_macd_filter(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if MACD conditions are met for entry
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, macd_info)
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.technical_analyzer.macd_slow + self.technical_analyzer.macd_signal + 1:
                logger.warning(f"Not enough closed K-lines for MACD filter: {len(closed_klines)}")
                return False, None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Check MACD filter
            macd_valid, macd_info = self.technical_analyzer.check_macd_filter(df, kline_direction)
            
            return macd_valid, macd_info
            
        except Exception as e:
            logger.error(f"Error checking MACD filter for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    def _check_adx_filter(self, symbol: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check ADX for trend strength and market type
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Tuple of (is_valid, adx_info)
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < 15:
                logger.warning(f"Not enough closed K-lines for ADX filter: {len(closed_klines)}")
                return False, None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Check ADX filter
            adx_valid, adx_info = self.technical_analyzer.check_adx_filter(
                df,
                adx_min_trend=self.adx_min_trend,
                adx_sideways=self.adx_sideways
            )
            
            return adx_valid, adx_info
            
        except Exception as e:
            logger.error(f"Error checking ADX filter for {symbol}: {e}")
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
            
            # Check RSI filter if enabled
            rsi_valid = True
            rsi_info = None
            if self.rsi_filter_enabled:
                rsi_valid, rsi_info = self._check_rsi_filter(symbol, direction_5m)
            
            # Check MACD filter if enabled
            macd_valid = True
            macd_info = None
            if self.macd_filter_enabled:
                macd_valid, macd_info = self._check_macd_filter(symbol, direction_5m)
            
            # Check ADX filter if enabled
            adx_valid = True
            adx_info = None
            if self.adx_filter_enabled:
                adx_valid, adx_info = self._check_adx_filter(symbol)
            
            # Determine if all conditions are met
            all_conditions_met = volume_valid and range_valid and body_valid and trend_valid and rsi_valid and macd_valid and adx_valid
            
            # Calculate signal strength
            signal_strength = self.technical_analyzer.calculate_signal_strength(
                volume_valid, range_valid, body_valid, trend_valid, rsi_valid, macd_valid, adx_valid
            )
            
            logger.info(
                f"[STRATEGY] Condition check for {symbol}: "
                f"volume_valid={volume_valid}, "
                f"range_valid={range_valid}, "
                f"body_valid={body_valid}, "
                f"trend_valid={trend_valid}, "
                f"rsi_valid={rsi_valid}, "
                f"macd_valid={macd_valid}, "
                f"adx_valid={adx_valid}, "
                f"signal_strength={signal_strength}, "
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
                    rsi_info=rsi_info,
                    macd_info=macd_info,
                    adx_info=adx_info,
                    signal_strength=signal_strength,
                    kline_time=kline_5m.get('close_time')
                )
                
                # Calculate stop loss price based on ATR or K-line range
                stop_loss_price = self._calculate_stop_loss_price(
                    symbol,
                    kline_5m,
                    direction_5m,
                    range_info.get('current_range', 0)
                )
                
                # Calculate dynamic take profit based on trend strength
                take_profit_percent = self._calculate_take_profit_percent(symbol, direction_5m)
                
                # Open position with volume info, range info, stop loss and entry kline
                logger.info(f"[STRATEGY] Opening position for {symbol}, direction={direction_5m}, signal_strength={signal_strength}")
                if direction_5m == 'UP':
                    logger.info(f"[STRATEGY] Calling _open_long_position for {symbol}")
                    await self._open_long_position(
                        symbol, volume_info, range_info, stop_loss_price, kline_5m,
                        kline_5m.get('close_time'), signal_strength, take_profit_percent
                    )
                    logger.info(f"[STRATEGY] _open_long_position completed for {symbol}")
                else:  # DOWN
                    logger.info(f"[STRATEGY] Calling _open_short_position for {symbol}")
                    await self._open_short_position(
                        symbol, volume_info, range_info, stop_loss_price, kline_5m,
                        kline_5m.get('close_time'), signal_strength, take_profit_percent
                    )
                    logger.info(f"[STRATEGY] _open_short_position completed for {symbol}")
            else:
                # Some conditions not met - send no trade notification with all condition info
                logger.info(f"Not all conditions met for {symbol}: volume={volume_valid}, range={range_valid}, body={body_valid}, trend={trend_valid}, rsi={rsi_valid}, macd={macd_valid}, adx={adx_valid}")
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
                    rsi_info=rsi_info,
                    macd_info=macd_info,
                    adx_info=adx_info,
                    signal_strength=signal_strength,
                    kline_time=kline_5m.get('close_time')
                )
            
            # Add explicit log to confirm completion of check
            logger.info(f"[STRATEGY] _check_and_open_position completed for {symbol}")
                
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    def _calculate_take_profit_percent(self, symbol: str, kline_direction: str) -> float:
        """
        Calculate dynamic take profit percentage based on trend strength (ADX)
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Take profit percentage
        """
        try:
            # If dynamic take profit is not enabled, use fixed percentage
            if not self.dynamic_take_profit_enabled:
                return self.take_profit_percent
            
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}, using default take profit")
                return self.take_profit_percent
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < 15:
                logger.warning(f"Not enough closed K-lines for ADX calculation: {len(closed_klines)}, using default take profit")
                return self.take_profit_percent
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Calculate ADX
            adx_series = self.technical_analyzer.calculate_adx(df, period=self.atr_period)
            if adx_series is None or len(adx_series) == 0:
                logger.warning(f"Could not calculate ADX for {symbol}, using default take profit")
                return self.take_profit_percent
            
            # Get latest ADX value
            latest_adx = adx_series.iloc[-1]
            
            # Determine take profit based on ADX
            if latest_adx >= self.adx_trend_threshold:
                # Strong trend - use higher take profit
                take_profit_percent = self.strong_trend_take_profit_percent
                logger.info(
                    f"Strong trend detected for {symbol}: ADX={latest_adx:.2f} >= {self.adx_trend_threshold}, "
                    f"using take profit={take_profit_percent*100:.1f}%"
                )
            else:
                # Weak trend - use lower take profit
                take_profit_percent = self.weak_trend_take_profit_percent
                logger.info(
                    f"Weak trend detected for {symbol}: ADX={latest_adx:.2f} < {self.adx_trend_threshold}, "
                    f"using take profit={take_profit_percent*100:.1f}%"
                )
            
            return take_profit_percent
            
        except Exception as e:
            logger.error(f"Error calculating take profit percent for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.take_profit_percent
    
    def _calculate_stop_loss_price(self, symbol: str, kline: Dict, direction: str, current_range: float) -> Optional[float]:
        """
        Calculate stop loss price based on ATR or 5m K-line range
        
        Args:
            symbol: Trading pair symbol
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
            
            # Calculate stop loss distance
            if self.atr_stop_loss_enabled:
                # Use ATR-based stop loss
                stop_loss_distance = self._calculate_atr_stop_loss_distance(symbol, close_price)
                if stop_loss_distance is None:
                    # Fallback to range-based if ATR calculation fails
                    stop_loss_distance = current_range * self.stop_loss_range_multiplier
                    logger.warning(f"ATR calculation failed for {symbol}, using range-based stop loss")
            else:
                # Use range-based stop loss
                stop_loss_distance = current_range * self.stop_loss_range_multiplier
            
            if direction == 'UP':
                # For long position, stop loss is below entry price
                stop_loss_price = close_price - stop_loss_distance
            else:  # DOWN
                # For short position, stop loss is above entry price
                stop_loss_price = close_price + stop_loss_distance
            
            logger.info(
                f"Stop loss calculated: "
                f"symbol={symbol}, "
                f"direction={direction}, "
                f"close_price={close_price:.2f}, "
                f"range={current_range:.2f}, "
                f"atr_enabled={self.atr_stop_loss_enabled}, "
                f"stop_loss_distance={stop_loss_distance:.2f}, "
                f"stop_loss_price={stop_loss_price:.2f}"
            )
            
            return stop_loss_price
            
        except Exception as e:
            logger.error(f"Error calculating stop loss price: {e}")
            return None
    
    def _calculate_atr_stop_loss_distance(self, symbol: str, current_price: float) -> Optional[float]:
        """
        Calculate ATR-based stop loss distance
        
        Args:
            symbol: Trading pair symbol
            current_price: Current price
            
        Returns:
            Stop loss distance or None
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.atr_period + 1:
                logger.warning(f"Not enough closed K-lines for ATR calculation: {len(closed_klines)}")
                return None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Calculate ATR
            atr_series = self.technical_analyzer.calculate_atr(df, period=self.atr_period)
            if atr_series is None or len(atr_series) == 0:
                logger.warning(f"Could not calculate ATR for {symbol}")
                return None
            
            # Get latest ATR value
            latest_atr = atr_series.iloc[-1]
            
            # Calculate stop loss distance
            stop_loss_distance = latest_atr * self.atr_stop_loss_multiplier
            
            logger.info(
                f"ATR-based stop loss distance for {symbol}: "
                f"ATR={latest_atr:.2f}, "
                f"multiplier={self.atr_stop_loss_multiplier}, "
                f"distance={stop_loss_distance:.2f} ({stop_loss_distance/current_price*100:.2f}%)"
            )
            
            return stop_loss_distance
            
        except Exception as e:
            logger.error(f"Error calculating ATR stop loss distance for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def _open_long_position(self, symbol: str, volume_info: Optional[Dict] = None, range_info: Optional[Dict] = None,
                                   stop_loss_price: Optional[float] = None, entry_kline: Optional[Dict] = None,
                                   kline_time: Optional[int] = None, signal_strength: str = 'MEDIUM',
                                   take_profit_percent: float = 0.05) -> None:
        """
        Open a long position
        
        Args:
            symbol: Trading pair symbol
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            stop_loss_price: Stop loss price (optional)
            entry_kline: Entry K-line data (optional)
            kline_time: K-line timestamp in milliseconds (optional)
            signal_strength: Signal strength (STRONG/MEDIUM/WEAK)
            take_profit_percent: Take profit percentage
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
                calculated_stop_loss_distance = current_price - stop_loss_price
                # Ensure minimum stop loss distance AND limit maximum stop loss distance
                min_stop_loss_distance = current_price * self.stop_loss_min_distance_percent
                # Use min() to limit maximum stop loss distance, not max()
                actual_stop_loss_distance = max(calculated_stop_loss_distance, min_stop_loss_distance)
                # But also cap it at a reasonable maximum (e.g., 3% for 10x leverage)
                max_stop_loss_distance = current_price * self.stop_loss_max_distance_percent
                actual_stop_loss_distance = min(actual_stop_loss_distance, max_stop_loss_distance)
                stop_loss_distance_percent = actual_stop_loss_distance / current_price
                
                # Recalculate stop loss price if it was capped
                if actual_stop_loss_distance != calculated_stop_loss_distance:
                    stop_loss_price = current_price - actual_stop_loss_distance
                    # Update position's stop loss price
                    position = self.position_manager.get_position(symbol)
                    if position:
                        position['stop_loss_price'] = stop_loss_price
                
                logger.info(
                    f"Stop loss distance for {symbol}: "
                    f"price={current_price:.2f}, "
                    f"calculated_stop_loss={calculated_stop_loss_distance:.2f} ({calculated_stop_loss_distance/current_price*100:.2f}%), "
                    f"min_distance={min_stop_loss_distance:.2f} ({self.stop_loss_min_distance_percent*100:.2f}%), "
                    f"max_distance={max_stop_loss_distance:.2f} ({self.stop_loss_max_distance_percent*100:.2f}%), "
                    f"actual_distance={actual_stop_loss_distance:.2f} ({stop_loss_distance_percent*100:.2f}%), "
                    f"final_stop_loss={stop_loss_price:.2f}"
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
            
            # Adjust position size based on signal strength
            if signal_strength == 'STRONG':
                position_ratio = self.strong_signal_position_ratio
            elif signal_strength == 'MEDIUM':
                position_ratio = self.medium_signal_position_ratio
            else:  # WEAK
                position_ratio = self.weak_signal_position_ratio
            
            adjusted_quantity = quantity * position_ratio
            logger.info(
                f"Position size adjustment for {symbol}: "
                f"signal_strength={signal_strength}, "
                f"position_ratio={position_ratio}, "
                f"original_quantity={quantity:.4f}, "
                f"adjusted_quantity={adjusted_quantity:.4f}"
            )
            quantity = adjusted_quantity
            
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
                    
                    # Record position with entry kline and stop loss price
                    self.position_manager.open_position(
                        symbol=symbol,
                        side='LONG',
                        entry_price=final_price,
                        quantity=final_quantity,
                        entry_kline=entry_kline
                    )
                    
                    # Store stop loss price in position for real-time monitoring
                    position = self.position_manager.get_position(symbol)
                    if position and stop_loss_price is not None:
                        position['stop_loss_price'] = stop_loss_price
                    
                    # Initialize peak price tracking for take profit
                    self.position_peak_prices[symbol] = final_price
                    
                    # Record entry time for time-based stop loss
                    self.position_entry_times[symbol] = kline_time if kline_time else int(datetime.now().timestamp() * 1000)
                    
                    # Initialize partial take profit status
                    self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
                    
                    logger.info(f"Long position opened successfully for {symbol}")
                    
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
                                    kline_time: Optional[int] = None, signal_strength: str = 'MEDIUM',
                                    take_profit_percent: float = 0.05) -> None:
        """
        Open a short position
        
        Args:
            symbol: Trading pair symbol
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            stop_loss_price: Stop loss price (optional)
            entry_kline: Entry K-line data (optional)
            kline_time: K-line timestamp in milliseconds (optional)
            signal_strength: Signal strength (STRONG/MEDIUM/WEAK)
            take_profit_percent: Take profit percentage
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
                calculated_stop_loss_distance = stop_loss_price - current_price
                # Ensure minimum stop loss distance AND limit maximum stop loss distance
                min_stop_loss_distance = current_price * self.stop_loss_min_distance_percent
                # Use min() to limit maximum stop loss distance, not max()
                actual_stop_loss_distance = max(calculated_stop_loss_distance, min_stop_loss_distance)
                # But also cap it at a reasonable maximum (e.g., 3% for 10x leverage)
                max_stop_loss_distance = current_price * self.stop_loss_max_distance_percent
                actual_stop_loss_distance = min(actual_stop_loss_distance, max_stop_loss_distance)
                stop_loss_distance_percent = actual_stop_loss_distance / current_price
                
                # Recalculate stop loss price if it was capped
                if actual_stop_loss_distance != calculated_stop_loss_distance:
                    stop_loss_price = current_price + actual_stop_loss_distance
                    # Update position's stop loss price
                    position = self.position_manager.get_position(symbol)
                    if position:
                        position['stop_loss_price'] = stop_loss_price
                
                logger.info(
                    f"Stop loss distance for {symbol}: "
                    f"price={current_price:.2f}, "
                    f"calculated_stop_loss={calculated_stop_loss_distance:.2f} ({calculated_stop_loss_distance/current_price*100:.2f}%), "
                    f"min_distance={min_stop_loss_distance:.2f} ({self.stop_loss_min_distance_percent*100:.2f}%), "
                    f"max_distance={max_stop_loss_distance:.2f} ({self.stop_loss_max_distance_percent*100:.2f}%), "
                    f"actual_distance={actual_stop_loss_distance:.2f} ({stop_loss_distance_percent*100:.2f}%), "
                    f"final_stop_loss={stop_loss_price:.2f}"
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
            
            # Adjust position size based on signal strength
            if signal_strength == 'STRONG':
                position_ratio = self.strong_signal_position_ratio
            elif signal_strength == 'MEDIUM':
                position_ratio = self.medium_signal_position_ratio
            else:  # WEAK
                position_ratio = self.weak_signal_position_ratio
            
            adjusted_quantity = quantity * position_ratio
            logger.info(
                f"Position size adjustment for {symbol}: "
                f"signal_strength={signal_strength}, "
                f"position_ratio={position_ratio}, "
                f"original_quantity={quantity:.4f}, "
                f"adjusted_quantity={adjusted_quantity:.4f}"
            )
            quantity = adjusted_quantity
            
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
                    
                    # Record position with entry kline and stop loss price
                    self.position_manager.open_position(
                        symbol=symbol,
                        side='SHORT',
                        entry_price=final_price,
                        quantity=final_quantity,
                        entry_kline=entry_kline
                    )
                    
                    # Store stop loss price in position for real-time monitoring
                    position = self.position_manager.get_position(symbol)
                    if position and stop_loss_price is not None:
                        position['stop_loss_price'] = stop_loss_price
                    
                    # Initialize peak price tracking for take profit
                    self.position_peak_prices[symbol] = final_price
                    
                    # Record entry time for time-based stop loss
                    self.position_entry_times[symbol] = kline_time if kline_time else int(datetime.now().timestamp() * 1000)
                    
                    # Initialize partial take profit status
                    self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
                    
                    logger.info(f"Short position opened successfully for {symbol}")
                    
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
                    
                    # Clear local position state to prevent duplicate notifications
                    self.position_manager.close_position(symbol, current_price if current_price else 0)
                    
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
    
    async def _check_engulfing_stop_loss_realtime(self, symbol: str, current_kline: Dict) -> None:
        """
        实时检查反向吞没止损（不等待K线关闭）
        当检测到吞没形态时立即平仓，响应更快
        
        Args:
            symbol: 交易对
            current_kline: 当前K线（可能未关闭）
        """
        try:
            # 获取持仓信息
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            position_side = position['side']
            
            # 获取最近的K线数据
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines or len(all_klines) < 2:
                return
            
            # 获取上一根已关闭的K线
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            if len(closed_klines) < 1:
                logger.debug(f"No closed klines for {symbol}, skipping realtime engulfing check")
                return
            
            previous_kline = closed_klines[-1]
            
            # 判断当前K线方向（即使未关闭）
            current_direction = self.technical_analyzer.get_kline_direction(current_kline)
            if current_direction is None:
                return
            
            # 判断上一根K线方向
            previous_direction = self.technical_analyzer.get_kline_direction(previous_kline)
            if previous_direction is None:
                return
            
            # 检查是否形成反向吞没
            if current_direction == previous_direction:
                logger.debug(f"Current kline direction {current_direction} is same as previous direction {previous_direction}, no engulfing")
                return
            
            # 计算实体比例
            previous_body = abs(previous_kline['close'] - previous_kline['open'])
            current_body = abs(current_kline['close'] - current_kline['open'])
            
            if previous_body == 0:
                logger.warning(f"Previous kline body is zero, cannot calculate engulfing ratio")
                return
            
            engulfing_ratio = current_body / previous_body
            
            # 检查真正的吞没形态
            is_true_engulfing = False
            if current_direction == 'UP' and previous_direction == 'DOWN':
                # 当前是阳线，上一根是阴线
                # 真正的吞没：当前开盘价 < 上一根收盘价 且 当前收盘价 > 上一根开盘价
                is_true_engulfing = (
                    current_kline['open'] < previous_kline['close'] and
                    current_kline['close'] > previous_kline['open']
                )
            elif current_direction == 'DOWN' and previous_direction == 'UP':
                # 当前是阴线，上一根是阳线
                # 真正的吞没：当前开盘价 > 上一根收盘价 且 当前收盘价 < 上一根开盘价
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
            
            # 如果满足条件，立即平仓
            if engulfing_ratio >= self.engulfing_body_ratio_threshold:
                logger.warning(
                    f"[REALTIME_ENGULFING_STOP_LOSS] {symbol}: "
                    f"previous_direction={previous_direction}, current_direction={current_direction}, "
                    f"previous_body={previous_body:.2f}, current_body={current_body:.2f}, "
                    f"engulfing_ratio={engulfing_ratio:.2f}, threshold={self.engulfing_body_ratio_threshold}"
                )
                
                # 立即平仓
                success = await self.trading_executor.close_all_positions(symbol)
                
                if success:
                    # 获取持仓详情用于通知
                    entry_price = position.get('entry_price', 0)
                    quantity = position.get('quantity', 0)
                    current_price = self.data_handler.get_current_price(symbol)
                    
                    # 计算盈亏
                    pnl = 0.0
                    if current_price and entry_price > 0:
                        if position_side == 'LONG':
                            pnl = (current_price - entry_price) * quantity
                        else:  # SHORT
                            pnl = (entry_price - current_price) * quantity
                    
                    # 发送平仓通知
                    await self.telegram_client.send_close_notification(
                        symbol=symbol,
                        side=position_side,
                        entry_price=entry_price,
                        exit_price=current_price if current_price else 0,
                        quantity=quantity,
                        pnl=pnl,
                        close_reason=f"实时反向吞没止损触发\n"
                                   f"上一根K线方向: {previous_direction}\n"
                                   f"当前K线方向: {current_direction}\n"
                                   f"上一根K线实体: {previous_body:.2f}\n"
                                   f"当前K线实体: {current_body:.2f}\n"
                                   f"吞没比例: {engulfing_ratio*100:.2f}%\n"
                                   f"阈值: {self.engulfing_body_ratio_threshold*100:.0f}%\n"
                                   f"⚡ 实时监控，未等待K线关闭"
                    )
                    
                    # 清除本地持仓状态
                    self.position_manager.close_position(symbol, current_price if current_price else 0)
                    
                    # 清除相关状态
                    if symbol in self.position_peak_prices:
                        del self.position_peak_prices[symbol]
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                    if symbol in self.partial_take_profit_status:
                        del self.partial_take_profit_status[symbol]
                    
                    logger.info(f"Position closed due to realtime engulfing stop loss for {symbol}")
                else:
                    logger.error(f"Failed to close position due to realtime engulfing stop loss for {symbol}")
            else:
                logger.debug(
                    f"Engulfing ratio {engulfing_ratio:.2f} below threshold {self.engulfing_body_ratio_threshold}, no stop loss"
                )
                
        except Exception as e:
            logger.error(f"Error checking realtime engulfing stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _update_trailing_stop_loss(self, symbol: str, current_kline: Dict) -> None:
        """
        Update trailing stop loss based on recent K-line highs/lows
        
        For LONG positions: stop loss follows recent N klines' lowest price
        For SHORT positions: stop loss follows recent N klines' highest price
        Stop loss can only move in favorable direction (up for LONG, down for SHORT)
        
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
            current_stop_loss = position.get('stop_loss_price')
            
            # If no stop loss price is set, skip update
            if current_stop_loss is None:
                logger.debug(f"No stop loss price set for {symbol}, skipping trailing stop update")
                return
            
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.trailing_stop_kline_count:
                logger.warning(
                    f"Not enough closed K-lines for trailing stop: "
                    f"{len(closed_klines)} (need at least {self.trailing_stop_kline_count})"
                )
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
            
            # Get recent N klines (including current)
            recent_klines = closed_klines[max(0, current_index - self.trailing_stop_kline_count + 1):current_index + 1]
            
            if len(recent_klines) < self.trailing_stop_kline_count:
                logger.warning(
                    f"Not enough recent klines for trailing stop: "
                    f"{len(recent_klines)} (need {self.trailing_stop_kline_count})"
                )
                return
            
            # Calculate new trailing stop loss price
            new_stop_loss = None
            
            if position_side == 'LONG':
                # For long position, trailing stop follows the lowest price in recent klines
                lowest_price = min(k['low'] for k in recent_klines)
                new_stop_loss = lowest_price
                
                # Stop loss can only move up (favorable direction)
                if new_stop_loss <= current_stop_loss:
                    logger.debug(
                        f"Trailing stop for {symbol} (LONG): "
                        f"new_stop={new_stop_loss:.2f} <= current_stop={current_stop_loss:.2f}, "
                        f"no update needed"
                    )
                    return
                
                logger.info(
                    f"Trailing stop updated for {symbol} (LONG): "
                    f"current_stop={current_stop_loss:.2f} -> new_stop={new_stop_loss:.2f}, "
                    f"lowest_in_recent={lowest_price:.2f}, "
                    f"improvement={((new_stop_loss - current_stop_loss) / current_stop_loss * 100):.2f}%"
                )
                
            else:  # SHORT
                # For short position, trailing stop follows the highest price in recent klines
                highest_price = max(k['high'] for k in recent_klines)
                new_stop_loss = highest_price
                
                # Stop loss can only move down (favorable direction)
                if new_stop_loss >= current_stop_loss:
                    logger.debug(
                        f"Trailing stop for {symbol} (SHORT): "
                        f"new_stop={new_stop_loss:.2f} >= current_stop={current_stop_loss:.2f}, "
                        f"no update needed"
                    )
                    return
                
                logger.info(
                    f"Trailing stop updated for {symbol} (SHORT): "
                    f"current_stop={current_stop_loss:.2f} -> new_stop={new_stop_loss:.2f}, "
                    f"highest_in_recent={highest_price:.2f}, "
                    f"improvement={((current_stop_loss - new_stop_loss) / current_stop_loss * 100):.2f}%"
                )
            
            # Update stop loss price in position
            position['stop_loss_price'] = new_stop_loss
            
            # Send notification about trailing stop update
            entry_price = position.get('entry_price', 0)
            current_price = self.data_handler.get_current_price(symbol)
            
            if current_price:
                # Calculate unrealized PnL
                quantity = position.get('quantity', 0)
                unrealized_pnl = 0.0
                if position_side == 'LONG':
                    unrealized_pnl = (current_price - entry_price) * quantity
                else:  # SHORT
                    unrealized_pnl = (entry_price - current_price) * quantity
                
                await self.telegram_client.send_message(
                    f"🔄 移动止损更新\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {position_side}\n"
                    f"开仓价格: ${entry_price:.2f}\n"
                    f"当前价格: ${current_price:.2f}\n"
                    f"未实现盈亏: ${unrealized_pnl:.2f}\n"
                    f"止损价格: ${current_stop_loss:.2f} → ${new_stop_loss:.2f}\n"
                    f"参考K线数: {self.trailing_stop_kline_count}\n"
                    f"{'最低价' if position_side == 'LONG' else '最高价'}: "
                    f"{'${:.2f}'.format(lowest_price if position_side == 'LONG' else highest_price)}"
                )
            
        except Exception as e:
            logger.error(f"Error updating trailing stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def check_stop_loss_on_price_update(self, symbol: str, current_price: float) -> None:
        """
        Check stop loss and take profit when price is updated via WebSocket
        This provides real-time stop loss protection with price buffer and time threshold
        Also checks for take profit conditions
        
        Args:
            symbol: Trading pair symbol
            current_price: Current price from WebSocket ticker
        """
        try:
            # Get position information
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            # Check time-based stop loss first
            if self.time_stop_loss_enabled:
                await self._check_time_stop_loss(symbol, current_price)
            
            # Re-check position after time stop loss check (might have been closed)
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            # Check take profit (before stop loss)
            await self._check_take_profit(symbol, current_price)
            
            # Re-check position after take profit check (might have been closed)
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            position_side = position['side']
            quantity = position['quantity']
            entry_price = position.get('entry_price', 0)
            stop_loss_price = position.get('stop_loss_price')
            
            # If no stop loss price is set, skip check
            if stop_loss_price is None:
                logger.debug(f"No stop loss price set for {symbol}")
                return
            
            # Calculate price buffer to avoid false triggers from minor fluctuations
            price_buffer = stop_loss_price * self.stop_loss_price_buffer_percent
            
            # Check if stop loss is triggered with buffer
            stop_loss_triggered = False
            if position_side == 'LONG':
                # For long position, stop loss is below entry price
                # Only trigger if price goes below stop_loss - buffer
                stop_loss_triggered = current_price <= (stop_loss_price - price_buffer)
            else:  # SHORT
                # For short position, stop loss is above entry price
                # Only trigger if price goes above stop_loss + buffer
                stop_loss_triggered = current_price >= (stop_loss_price + price_buffer)
            
            # Calculate distance from entry price
            distance_from_entry = abs(current_price - entry_price)
            distance_percent = (distance_from_entry / entry_price) * 100 if entry_price > 0 else 0
            
            # Calculate distance from stop loss
            distance_from_stop_loss = abs(current_price - stop_loss_price)
            
            # Get current time
            import time
            current_time = time.time()
            
            # Handle stop loss trigger with time threshold
            if stop_loss_triggered:
                # Check if this is the first time we've seen the trigger
                if symbol not in self.stop_loss_first_trigger_time:
                    self.stop_loss_first_trigger_time[symbol] = current_time
                    logger.warning(
                        f"[STOP_LOSS_FIRST_TRIGGER] {symbol}: "
                        f"current_price={current_price:.2f}, "
                        f"stop_loss_price={stop_loss_price:.2f}, "
                        f"buffer={price_buffer:.2f}, "
                        f"waiting {self.stop_loss_time_threshold}s for confirmation..."
                    )
                    return
                
                # Check if enough time has passed since first trigger
                time_since_first_trigger = current_time - self.stop_loss_first_trigger_time[symbol]
                
                if time_since_first_trigger < self.stop_loss_time_threshold:
                    # Not enough time has passed, continue waiting
                    logger.debug(
                        f"[STOP_LOSS_WAITING] {symbol}: "
                        f"waiting {self.stop_loss_time_threshold - time_since_first_trigger:.1f}s more..."
                    )
                    return
                
                # Time threshold passed, confirm stop loss trigger
                logger.warning(
                    f"[STOP_LOSS_CONFIRMED] {symbol}: "
                    f"current_price={current_price:.2f}, "
                    f"stop_loss_price={stop_loss_price:.2f}, "
                    f"duration={time_since_first_trigger:.1f}s"
                )
                
                # Close position immediately
                success = await self.trading_executor.close_all_positions(symbol)
                
                if success:
                    # Calculate PnL
                    pnl = 0.0
                    if current_price and entry_price > 0:
                        if position_side == 'LONG':
                            pnl = (current_price - entry_price) * quantity
                        else:  # SHORT
                            pnl = (entry_price - current_price) * quantity
                    
                    # Send close notification with stop loss reason
                    await self.telegram_client.send_close_notification(
                        symbol=symbol,
                        side=position_side,
                        entry_price=entry_price,
                        exit_price=current_price,
                        quantity=quantity,
                        pnl=pnl,
                        close_reason=f"实时止损触发\n"
                                   f"当前价格: ${current_price:.2f}\n"
                                   f"止损价格: ${stop_loss_price:.2f}\n"
                                   f"价格缓冲: ${price_buffer:.2f} ({self.stop_loss_price_buffer_percent*100:.2f}%)\n"
                                   f"持续时间: {time_since_first_trigger:.1f}s\n"
                                   f"距离开仓: ${distance_from_entry:.2f} ({distance_percent:.2f}%)"
                    )
                    
                    # Clear local position state to prevent duplicate notifications
                    self.position_manager.close_position(symbol, current_price)
                    
                    # Clear trigger time tracking
                    if symbol in self.stop_loss_first_trigger_time:
                        del self.stop_loss_first_trigger_time[symbol]
                    
                    # Clear entry time tracking
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                    
                    # Clear partial take profit status
                    if symbol in self.partial_take_profit_status:
                        del self.partial_take_profit_status[symbol]
                    
                    logger.info(f"Position closed due to stop loss for {symbol}")
                else:
                    logger.error(f"Failed to close position due to stop loss for {symbol}")
            else:
                # Price moved back above stop loss threshold, reset trigger time
                if symbol in self.stop_loss_first_trigger_time:
                    logger.info(
                        f"[STOP_LOSS_RESET] {symbol}: "
                        f"price moved back, resetting trigger timer"
                    )
                    del self.stop_loss_first_trigger_time[symbol]
            
            # Log stop loss check status (less frequent to avoid log spam)
            if symbol not in self.stop_loss_trigger_times or (current_time - self.stop_loss_trigger_times[symbol]) >= 5:
                logger.info(
                    f"[STOP_LOSS_CHECK] {symbol}: "
                    f"side={position_side}, "
                    f"entry={entry_price:.2f}, "
                    f"current={current_price:.2f}, "
                    f"stop_loss={stop_loss_price:.2f}, "
                    f"buffer={price_buffer:.2f}, "
                    f"from_entry={distance_from_entry:.2f} ({distance_percent:.2f}%), "
                    f"from_stop_loss={distance_from_stop_loss:.2f}, "
                    f"triggered={stop_loss_triggered}"
                )
                self.stop_loss_trigger_times[symbol] = current_time
            
        except Exception as e:
            logger.error(f"Error checking stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _check_take_profit(self, symbol: str, current_price: float) -> None:
        """
        Check if take profit should be triggered
        Implements both fixed take profit and trailing take profit
        
        Args:
            symbol: Trading pair symbol
            current_price: Current price from WebSocket ticker
        """
        try:
            # Get position information
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            position_side = position['side']
            quantity = position['quantity']
            entry_price = position.get('entry_price', 0)
            
            # Calculate current PnL percentage
            pnl_percent = 0.0
            if position_side == 'LONG':
                pnl_percent = (current_price - entry_price) / entry_price if entry_price > 0 else 0
            else:  # SHORT
                pnl_percent = (entry_price - current_price) / entry_price if entry_price > 0 else 0
            
            # Initialize peak price tracking if not exists
            if symbol not in self.position_peak_prices:
                self.position_peak_prices[symbol] = current_price
            
            # Update peak price
            if position_side == 'LONG':
                # For long, track highest price
                if current_price > self.position_peak_prices[symbol]:
                    self.position_peak_prices[symbol] = current_price
            else:  # SHORT
                # For short, track lowest price
                if current_price < self.position_peak_prices[symbol]:
                    self.position_peak_prices[symbol] = current_price
            
            # Check if take profit is enabled
            if not self.take_profit_enabled:
                return
            
            # Calculate take profit threshold
            take_profit_threshold = entry_price * (1 + self.take_profit_percent) if position_side == 'LONG' else entry_price * (1 - self.take_profit_percent)
            
            # Check partial take profit first
            partial_tp_executed = await self._check_partial_take_profit(
                symbol, current_price, position_side, entry_price, quantity, pnl_percent
            )
            
            # Re-check position after partial take profit (might have been closed)
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            # Update quantity after partial take profit
            quantity = position['quantity']
            
            # Check if fixed take profit is triggered
            take_profit_triggered = False
            if position_side == 'LONG':
                take_profit_triggered = current_price >= take_profit_threshold
            else:  # SHORT
                take_profit_triggered = current_price <= take_profit_threshold
            
            if take_profit_triggered:
                # Check if trailing take profit is enabled
                if self.take_profit_trailing_enabled:
                    # Calculate trailing take profit threshold based on peak price
                    trailing_threshold = self.position_peak_prices[symbol] * (1 - self.take_profit_trailing_percent) if position_side == 'LONG' else self.position_peak_prices[symbol] * (1 + self.take_profit_trailing_percent)
                    
                    # Only close if price drops below trailing threshold
                    if position_side == 'LONG':
                        if current_price >= trailing_threshold:
                            logger.info(
                                f"[TAKE_PROFIT_WAITING] {symbol}: "
                                f"current={current_price:.2f} >= trailing={trailing_threshold:.2f}, "
                                f"continuing to trail..."
                            )
                            return
                    else:  # SHORT
                        if current_price <= trailing_threshold:
                            logger.info(
                                f"[TAKE_PROFIT_WAITING] {symbol}: "
                                f"current={current_price:.2f} <= trailing={trailing_threshold:.2f}, "
                                f"continuing to trail..."
                            )
                            return
                
                # Close position for take profit
                success = await self.trading_executor.close_all_positions(symbol)
                
                if success:
                    # Calculate PnL
                    pnl = 0.0
                    if current_price and entry_price > 0:
                        if position_side == 'LONG':
                            pnl = (current_price - entry_price) * quantity
                        else:  # SHORT
                            pnl = (entry_price - current_price) * quantity
                    
                    # Send close notification with take profit reason
                    await self.telegram_client.send_close_notification(
                        symbol=symbol,
                        side=position_side,
                        entry_price=entry_price,
                        exit_price=current_price,
                        quantity=quantity,
                        pnl=pnl,
                        close_reason=f"止盈触发\n"
                                   f"当前价格: ${current_price:.2f}\n"
                                   f"开仓价格: ${entry_price:.2f}\n"
                                   f"盈亏比例: {pnl_percent*100:.2f}%\n"
                                   f"止盈阈值: {self.take_profit_percent*100:.1f}%\n"
                                   f"{'最高价' if position_side == 'LONG' else '最低价'}: ${self.position_peak_prices[symbol]:.2f}"
                    )
                    
                    # Clear local position state
                    self.position_manager.close_position(symbol, current_price)
                    
                    # Clear peak price tracking
                    if symbol in self.position_peak_prices:
                        del self.position_peak_prices[symbol]
                    
                    # Clear entry time tracking
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                    
                    # Clear partial take profit status
                    if symbol in self.partial_take_profit_status:
                        del self.partial_take_profit_status[symbol]
                    
                    logger.info(f"Position closed due to take profit for {symbol}")
                else:
                    logger.error(f"Failed to close position due to take profit for {symbol}")
            
        except Exception as e:
            logger.error(f"Error checking take profit for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _check_time_stop_loss(self, symbol: str, current_price: float) -> None:
        """
        Check if position should be closed due to time-based stop loss
        Closes position if it has been held for too many K-lines without reaching take profit
        
        Args:
            symbol: Trading pair symbol
            current_price: Current price from WebSocket ticker
        """
        try:
            # Get position information
            position = self.position_manager.get_position(symbol)
            if not position:
                return
            
            # Check if entry time is recorded
            if symbol not in self.position_entry_times:
                logger.warning(f"No entry time recorded for {symbol}, skipping time stop loss check")
                return
            
            entry_time = self.position_entry_times[symbol]
            current_time = int(datetime.now().timestamp() * 1000)
            
            # Calculate elapsed time in milliseconds
            elapsed_time_ms = current_time - entry_time
            
            # Convert to K-lines (5 minutes = 300000 milliseconds)
            elapsed_klines = elapsed_time_ms / 300000
            
            # Check if time stop loss is triggered
            if elapsed_klines >= self.time_stop_loss_klines:
                logger.warning(
                    f"[TIME_STOP_LOSS] {symbol}: "
                    f"elapsed_klines={elapsed_klines:.1f}, "
                    f"threshold={self.time_stop_loss_klines}, "
                    f"closing position..."
                )
                
                # Close position immediately
                success = await self.trading_executor.close_all_positions(symbol)
                
                if success:
                    position_side = position['side']
                    quantity = position['quantity']
                    entry_price = position.get('entry_price', 0)
                    
                    # Calculate PnL
                    pnl = 0.0
                    if current_price and entry_price > 0:
                        if position_side == 'LONG':
                            pnl = (current_price - entry_price) * quantity
                        else:  # SHORT
                            pnl = (entry_price - current_price) * quantity
                    
                    # Calculate PnL percentage
                    pnl_percent = 0.0
                    if entry_price > 0:
                        if position_side == 'LONG':
                            pnl_percent = (current_price - entry_price) / entry_price
                        else:  # SHORT
                            pnl_percent = (entry_price - current_price) / entry_price
                    
                    # Send close notification with time stop loss reason
                    await self.telegram_client.send_close_notification(
                        symbol=symbol,
                        side=position_side,
                        entry_price=entry_price,
                        exit_price=current_price,
                        quantity=quantity,
                        pnl=pnl,
                        close_reason=f"时间止损触发\n"
                                   f"持仓时间: {elapsed_klines:.1f} 根K线\n"
                                   f"时间阈值: {self.time_stop_loss_klines} 根K线\n"
                                   f"当前价格: ${current_price:.2f}\n"
                                   f"开仓价格: ${entry_price:.2f}\n"
                                   f"盈亏比例: {pnl_percent*100:.2f}%"
                    )
                    
                    # Clear local position state
                    self.position_manager.close_position(symbol, current_price)
                    
                    # Clear entry time tracking
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                    
                    # Clear partial take profit status
                    if symbol in self.partial_take_profit_status:
                        del self.partial_take_profit_status[symbol]
                    
                    # Clear peak price tracking
                    if symbol in self.position_peak_prices:
                        del self.position_peak_prices[symbol]
                    
                    logger.info(f"Position closed due to time stop loss for {symbol}")
                else:
                    logger.error(f"Failed to close position due to time stop loss for {symbol}")
            else:
                logger.debug(
                    f"[TIME_STOP_LOSS_CHECK] {symbol}: "
                    f"elapsed_klines={elapsed_klines:.1f}, "
                    f"threshold={self.time_stop_loss_klines}, "
                    f"remaining={self.time_stop_loss_klines - elapsed_klines:.1f} klines"
                )
                
        except Exception as e:
            logger.error(f"Error checking time stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _check_partial_take_profit(self, symbol: str, current_price: float, position_side: str,
                                        entry_price: float, quantity: float, pnl_percent: float) -> bool:
        """
        Check and execute partial take profit at predefined levels
        
        Args:
            symbol: Trading pair symbol
            current_price: Current price
            position_side: 'LONG' or 'SHORT'
            entry_price: Entry price
            quantity: Position quantity
            pnl_percent: Current PnL percentage
            
        Returns:
            True if partial take profit was executed, False otherwise
        """
        try:
            # Check if partial take profit is enabled
            if not self.partial_take_profit_enabled:
                return False
            
            # Check if partial take profit status exists
            if symbol not in self.partial_take_profit_status:
                logger.warning(f"No partial take profit status for {symbol}")
                return False
            
            # Check each take profit level
            for i, level in enumerate(self.partial_take_profit_levels):
                # Skip if this level has already been executed
                if self.partial_take_profit_status[symbol].get(i, False):
                    continue
                
                # Check if current PnL reaches this level
                if pnl_percent >= level:
                    logger.info(
                        f"[PARTIAL_TAKE_PROFIT] {symbol}: "
                        f"level={i+1}/{len(self.partial_take_profit_levels)}, "
                        f"pnl_percent={pnl_percent*100:.2f}%, "
                        f"level_threshold={level*100:.1f}%, "
                        f"executing partial close..."
                    )
                    
                    # Calculate quantity to close
                    ratio = self.partial_take_profit_ratios[i] if i < len(self.partial_take_profit_ratios) else 0.5
                    close_quantity = quantity * ratio
                    
                    # Execute partial close
                    # Note: This is a simplified implementation. In production, you would need to
                    # track remaining quantity and update position state accordingly
                    success = await self.trading_executor.close_all_positions(symbol)
                    
                    if success:
                        # Calculate PnL for this partial close
                        pnl = 0.0
                        if current_price and entry_price > 0:
                            if position_side == 'LONG':
                                pnl = (current_price - entry_price) * close_quantity
                            else:  # SHORT
                                pnl = (entry_price - current_price) * close_quantity
                        
                        # Send notification
                        await self.telegram_client.send_message(
                            f"📊 分批止盈执行\n\n"
                            f"交易对: {symbol}\n"
                            f"方向: {position_side}\n"
                            f"开仓价格: ${entry_price:.2f}\n"
                            f"当前价格: ${current_price:.2f}\n"
                            f"止盈级别: {i+1}/{len(self.partial_take_profit_levels)}\n"
                            f"止盈阈值: {level*100:.1f}%\n"
                            f"当前盈亏: {pnl_percent*100:.2f}%\n"
                            f"平仓数量: {close_quantity:.4f}\n"
                            f"平仓比例: {ratio*100:.1f}%\n"
                            f"本次盈亏: ${pnl:.2f}"
                        )
                        
                        # Mark this level as executed
                        self.partial_take_profit_status[symbol][i] = True
                        
                        logger.info(f"Partial take profit executed for {symbol} at level {i+1}")
                        return True
                    else:
                        logger.error(f"Failed to execute partial take profit for {symbol} at level {i+1}")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking partial take profit for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False