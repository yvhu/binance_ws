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
from ..indicators.sentiment_analyzer import SentimentAnalyzer
from ..indicators.ml_predictor import MLPredictor
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
        telegram_client: TelegramClient,
        sentiment_analyzer: Optional[SentimentAnalyzer] = None,
        ml_predictor: Optional[MLPredictor] = None
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
            sentiment_analyzer: Sentiment analyzer instance (optional)
            ml_predictor: ML predictor instance (optional)
        """
        self.config = config
        self.technical_analyzer = technical_analyzer
        self.position_manager = position_manager
        self.trading_executor = trading_executor
        self.data_handler = data_handler
        self.telegram_client = telegram_client
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
        self.ml_predictor = ml_predictor or MLPredictor()
        
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
        
        # Market environment recognition configuration
        self.market_env_filter_enabled = config.get_config("strategy", "market_env_filter_enabled", default=True)
        self.market_env_allow_ranging = config.get_config("strategy", "market_env_allow_ranging", default=True)
        self.market_env_min_confidence = config.get_config("strategy", "market_env_min_confidence", default=50)
        self.market_env_adx_trend_threshold = config.get_config("strategy", "market_env_adx_trend_threshold", default=25)
        self.market_env_adx_strong_threshold = config.get_config("strategy", "market_env_adx_strong_threshold", default=40)
        
        # Multi-timeframe analysis configuration
        self.multi_timeframe_enabled = config.get_config("strategy", "multi_timeframe_enabled", default=False)
        self.multi_timeframe_intervals = config.get_config("strategy", "multi_timeframe_intervals", default=["15m", "1h"])
        self.multi_timeframe_require_alignment = config.get_config("strategy", "multi_timeframe_require_alignment", default=True)
        self.multi_timeframe_min_aligned = config.get_config("strategy", "multi_timeframe_min_aligned", default=2)
        
        # Sentiment filter configuration
        self.sentiment_filter_enabled = config.get_config("strategy", "sentiment_filter_enabled", default=False)
        self.sentiment_min_fear = config.get_config("strategy", "sentiment_min_fear", default=25)
        self.sentiment_max_greed = config.get_config("strategy", "sentiment_max_greed", default=75)
        self.sentiment_min_greed = config.get_config("strategy", "sentiment_min_greed", default=56)
        self.sentiment_max_fear = config.get_config("strategy", "sentiment_max_fear", default=44)
        
        # ML filter configuration
        self.ml_filter_enabled = config.get_config("strategy", "ml_filter_enabled", default=False)
        self.ml_min_confidence = config.get_config("strategy", "ml_min_confidence", default=0.6)
        
        # Early entry configuration
        self.early_entry_enabled = config.get_config("strategy", "early_entry_enabled", default=False)
        self.early_entry_min_progress = config.get_config("strategy", "early_entry_min_progress", default=0.7)
        self.early_entry_strong_signal_only = config.get_config("strategy", "early_entry_strong_signal_only", default=True)
        
        # Entry confirmation configuration
        self.entry_confirmation_enabled = config.get_config("strategy", "entry_confirmation_enabled", default=True)
        self.entry_confirmation_type = config.get_config("strategy", "entry_confirmation_type", default="price")
        self.entry_confirmation_wait_klines = config.get_config("strategy", "entry_confirmation_wait_klines", default=1)
        self.entry_confirmation_price_threshold = config.get_config("strategy", "entry_confirmation_price_threshold", default=0.002)
        self.entry_confirmation_volume_threshold = config.get_config("strategy", "entry_confirmation_volume_threshold", default=1.1)
        
        # Track early entry status for each symbol
        self.early_entry_checked: Dict[str, int] = {}  # symbol -> kline_open_time
        
        # Track pending entry confirmations for each symbol
        self.pending_entry_confirmations: Dict[str, Dict] = {}  # symbol -> {direction, kline_time, signal_strength, volume_info, range_info, body_info, trend_info, rsi_info, macd_info, adx_info, market_env_info, multi_timeframe_info, sentiment_info, ml_info}
        
        # Position sizing based on signal strength
        self.strong_signal_position_ratio = config.get_config("trading", "strong_signal_position_ratio", default=1.0)
        self.medium_signal_position_ratio = config.get_config("trading", "medium_signal_position_ratio", default=0.75)
        self.weak_signal_position_ratio = config.get_config("trading", "weak_signal_position_ratio", default=0.5)
        
        # Drawdown protection configuration
        self.drawdown_protection_enabled = config.get_config("trading", "drawdown_protection_enabled", default=True)
        self.max_consecutive_losses = config.get_config("trading", "max_consecutive_losses", default=3)
        self.max_daily_loss_percent = config.get_config("trading", "max_daily_loss_percent", default=0.05)
        self.position_reduction_on_loss = config.get_config("trading", "position_reduction_on_loss", default=0.5)
        self.trading_pause_duration = config.get_config("trading", "trading_pause_duration", default=3600)
        
        # Track highest/lowest price for take profit
        self.position_peak_prices: Dict[str, float] = {}  # symbol -> peak price (highest for LONG, lowest for SHORT)
        
        # Track drawdown protection state
        self.consecutive_losses = 0  # Consecutive losses count
        self.daily_start_balance = 0.0  # Daily starting balance
        self.daily_pnl = 0.0  # Daily PnL
        self.trading_paused_until = 0  # Timestamp until which trading is paused
        self.position_reduction_active = False  # Whether position reduction is active
        
        # Track stop loss trigger times for each symbol
        self.stop_loss_trigger_times: Dict[str, float] = {}
        self.stop_loss_first_trigger_time: Dict[str, float] = {}
        
        # Track position entry time for time-based stop loss
        self.position_entry_times: Dict[str, int] = {}  # symbol -> entry timestamp (milliseconds)
        
        # Track partial take profit status for each position
        self.partial_take_profit_status: Dict[str, Dict] = {}  # symbol -> {level_index: bool}
        
        logger.info("5-minute strategy initialized")
    
    async def on_5m_kline_update(self, kline_info: Dict) -> None:
        """
        Handle 5-minute K-line update event (trigger for early entry and real-time stop loss)
        This is called for every K-line update, including unclosed K-lines
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        interval = kline_info['interval']
        is_closed = kline_info.get('is_closed', False)
        
        logger.info(f"[STRATEGY] on_5m_kline_update called for {symbol} {interval} closed={is_closed}")
        
        # Check for real-time engulfing stop loss if position exists
        if self.position_manager.has_position(symbol):
            await self._check_engulfing_stop_loss_realtime(symbol, kline_info)
        
        # Check for early entry if enabled and K-line is not closed
        if not is_closed and self.early_entry_enabled:
            await self._check_early_entry(symbol, kline_info)
    
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
        
        # Check entry confirmation if enabled
        if self.entry_confirmation_enabled and symbol in self.pending_entry_confirmations:
            await self._check_entry_confirmation(symbol, kline_info)
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
    
    def _check_market_environment_filter(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if market environment is suitable for trading
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, env_info) where env_info contains market environment details
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False, None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < 30:
                logger.warning(f"Not enough closed K-lines for market environment filter: {len(closed_klines)}")
                return False, None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Check market environment filter
            env_valid, env_info = self.technical_analyzer.check_market_environment_filter(
                df,
                kline_direction,
                allow_ranging=self.market_env_allow_ranging,
                min_confidence=self.market_env_min_confidence
            )
            
            return env_valid, env_info
            
        except Exception as e:
            logger.error(f"Error checking market environment filter for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    def _check_multi_timeframe_trend(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if trend direction aligns across multiple timeframes
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN' (from 5m timeframe)
            
        Returns:
            Tuple of (is_valid, timeframe_info) where timeframe_info contains:
            - aligned_count: Number of timeframes aligned with 5m direction
            - total_count: Total number of timeframes checked
            - timeframe_trends: Dictionary of timeframe -> trend direction
        """
        try:
            # Check if multi-timeframe analysis is enabled
            if not self.multi_timeframe_enabled:
                return True, None
            
            # Get trend direction for each timeframe
            timeframe_trends = {}
            aligned_count = 0
            
            for interval in self.multi_timeframe_intervals:
                # Get klines for this timeframe
                all_klines = self.data_handler.get_klines(symbol, interval)
                if not all_klines:
                    logger.warning(f"No {interval} K-line data for {symbol}")
                    continue
                
                # Filter only closed K-lines
                closed_klines = [k for k in all_klines if k.get('is_closed', False)]
                
                if len(closed_klines) < self.trend_filter_ma_period + 1:
                    logger.warning(f"Not enough closed {interval} K-lines for trend check: {len(closed_klines)}")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(closed_klines)
                
                # Check trend direction using MA
                ma_period = self.trend_filter_ma_period
                ma = self.technical_analyzer.calculate_ma(df['close'], ma_period)
                
                if ma is None or len(ma) == 0:
                    logger.warning(f"Could not calculate MA for {symbol} {interval}")
                    continue
                
                # Get latest MA and price
                latest_ma = ma.iloc[-1]
                latest_price = df['close'].iloc[-1]
                previous_ma = ma.iloc[-2] if len(ma) >= 2 else latest_ma
                
                # Determine trend direction
                if latest_price > latest_ma and latest_ma > previous_ma:
                    trend_direction = 'UP'
                elif latest_price < latest_ma and latest_ma < previous_ma:
                    trend_direction = 'DOWN'
                else:
                    trend_direction = 'SIDEWAYS'
                
                timeframe_trends[interval] = trend_direction
                
                # Check if aligned with 5m direction
                if trend_direction == kline_direction:
                    aligned_count += 1
            
            total_count = len(timeframe_trends)
            
            # Check if enough timeframes are aligned
            if total_count == 0:
                logger.warning(f"No timeframe data available for {symbol}")
                return True, None
            
            if self.multi_timeframe_require_alignment:
                is_valid = aligned_count >= self.multi_timeframe_min_aligned
            else:
                # If alignment not required, just log the information
                is_valid = True
            
            timeframe_info = {
                'aligned_count': aligned_count,
                'total_count': total_count,
                'timeframe_trends': timeframe_trends,
                'kline_direction': kline_direction
            }
            
            logger.info(
                f"[MULTI_TIMEFRAME] {symbol}: "
                f"5m={kline_direction}, "
                f"aligned={aligned_count}/{total_count}, "
                f"trends={timeframe_trends}, "
                f"valid={is_valid}"
            )
            
            return is_valid, timeframe_info
            
        except Exception as e:
            logger.error(f"Error checking multi-timeframe trend for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return True, None
    
    def _check_sentiment_filter(self, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if market sentiment conditions are met for entry
        
        Args:
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, sentiment_info) where sentiment_info contains:
            - fear_greed_value: Current Fear and Greed Index value
            - fear_greed_classification: Classification (Extreme Fear, Fear, etc.)
            - sentiment_valid: Whether sentiment conditions are met
        """
        try:
            # Check if sentiment filter is enabled
            if not self.sentiment_filter_enabled:
                return True, None
            
            # Check if sentiment analyzer is available
            if not self.sentiment_analyzer:
                logger.warning("Sentiment analyzer not available, skipping sentiment filter")
                return True, None
            
            # Check sentiment filter
            sentiment_valid, sentiment_info = self.sentiment_analyzer.check_sentiment_filter(
                kline_direction,
                min_fear=self.sentiment_min_fear,
                max_greed=self.sentiment_max_greed,
                min_greed=self.sentiment_min_greed,
                max_fear=self.sentiment_max_fear
            )
            
            if sentiment_info:
                logger.info(
                    f"[SENTIMENT_FILTER] "
                    f"direction={kline_direction}, "
                    f"fear_greed={sentiment_info.get('fear_greed_value', 'N/A')} "
                    f"({sentiment_info.get('fear_greed_classification', 'N/A')}), "
                    f"valid={sentiment_valid}"
                )
            
            return sentiment_valid, sentiment_info
            
        except Exception as e:
            logger.error(f"Error checking sentiment filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return True, None
    
    def _check_ml_filter(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if ML prediction aligns with kline direction
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, ml_info) where ml_info contains ML filter details
        """
        try:
            # Check if ML filter is enabled
            if not self.ml_filter_enabled:
                return True, None
            
            # Check if ML predictor is available
            if not self.ml_predictor:
                logger.warning("ML predictor not available, skipping ML filter")
                return True, None
            
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return True, None
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < 50:
                logger.warning(f"Not enough closed K-lines for ML prediction: {len(closed_klines)}")
                return True, None
            
            # Convert to DataFrame
            df = pd.DataFrame(closed_klines)
            
            # Make prediction
            prediction, prediction_info = self.ml_predictor.predict(df)
            
            # Check ML filter
            ml_valid, ml_info = self.ml_predictor.check_ml_filter(
                kline_direction,
                prediction,
                prediction_info,
                min_confidence=self.ml_min_confidence
            )
            
            return ml_valid, ml_info
            
        except Exception as e:
            logger.error(f"Error checking ML filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return True, None
    
    def _calculate_kline_progress(self, kline: Dict) -> float:
        """
        Calculate K-line progress (0.0 to 1.0)
        
        Args:
            kline: K-line information dictionary
            
        Returns:
            Progress as a float between 0.0 and 1.0
        """
        try:
            import time
            current_time = int(time.time() * 1000)
            open_time = kline.get('open_time', 0)
            close_time = kline.get('close_time', 0)
            
            if close_time <= open_time:
                return 0.0
            
            elapsed = current_time - open_time
            total_duration = close_time - open_time
            progress = elapsed / total_duration if total_duration > 0 else 0.0
            
            # Clamp progress between 0 and 1
            progress = max(0.0, min(1.0, progress))
            
            return progress
            
        except Exception as e:
            logger.error(f"Error calculating K-line progress: {e}")
            return 0.0
    
    async def _check_early_entry(self, symbol: str, kline: Dict) -> None:
        """
        Check if early entry conditions are met before K-line closes
        
        Args:
            symbol: Trading pair symbol
            kline: Current K-line (may not be closed)
        """
        try:
            # Check if early entry is enabled
            if not self.early_entry_enabled:
                return
            
            # Check if position already exists
            if self.position_manager.has_position(symbol):
                return
            
            # Check if this K-line has already been checked for early entry
            kline_open_time = kline.get('open_time', 0)
            if symbol in self.early_entry_checked and self.early_entry_checked[symbol] == kline_open_time:
                return
            
            # Calculate K-line progress
            progress = self._calculate_kline_progress(kline)
            
            # Check if K-line has reached minimum progress
            if progress < self.early_entry_min_progress:
                return
            
            # Mark this K-line as checked
            self.early_entry_checked[symbol] = kline_open_time
            
            logger.info(
                f"[EARLY_ENTRY] {symbol}: "
                f"K-line progress={progress*100:.1f}%, "
                f"checking early entry conditions..."
            )
            
            # Get K-line direction
            direction = self.technical_analyzer.get_kline_direction(kline)
            if direction is None:
                return
            
            # Check all conditions (same as normal entry check)
            volume_valid, volume_info = self._check_volume_condition(symbol, kline)
            range_valid, range_info = self._check_range_condition(symbol, kline)
            body_valid, body_info = self._check_body_ratio(kline)
            
            # Check trend filter if enabled
            trend_valid = True
            trend_info = None
            if self.trend_filter_enabled:
                trend_valid, trend_info = self._check_trend_filter(symbol, direction)
            
            # Check RSI filter if enabled
            rsi_valid = True
            rsi_info = None
            if self.rsi_filter_enabled:
                rsi_valid, rsi_info = self._check_rsi_filter(symbol, direction)
            
            # Check MACD filter if enabled
            macd_valid = True
            macd_info = None
            if self.macd_filter_enabled:
                macd_valid, macd_info = self._check_macd_filter(symbol, direction)
            
            # Check ADX filter if enabled
            adx_valid = True
            adx_info = None
            if self.adx_filter_enabled:
                adx_valid, adx_info = self._check_adx_filter(symbol)
            
            # Check market environment filter if enabled
            market_env_valid = True
            market_env_info = None
            if self.market_env_filter_enabled:
                market_env_valid, market_env_info = self._check_market_environment_filter(symbol, direction)
            
            # Check multi-timeframe trend if enabled
            multi_timeframe_valid = True
            multi_timeframe_info = None
            if self.multi_timeframe_enabled:
                multi_timeframe_valid, multi_timeframe_info = self._check_multi_timeframe_trend(symbol, direction)
            
            # Check sentiment filter if enabled
            sentiment_valid = True
            sentiment_info = None
            if self.sentiment_filter_enabled:
                sentiment_valid, sentiment_info = self._check_sentiment_filter(direction)
            
            # Check ML filter if enabled
            ml_valid = True
            ml_info = None
            if self.ml_filter_enabled:
                ml_valid, ml_info = self._check_ml_filter(symbol, direction)
            
            # Determine if all conditions are met
            all_conditions_met = volume_valid and range_valid and body_valid and trend_valid and rsi_valid and macd_valid and adx_valid and market_env_valid and multi_timeframe_valid and sentiment_valid and ml_valid
            
            # Calculate signal strength
            signal_strength = self.technical_analyzer.calculate_signal_strength(
                volume_valid, range_valid, body_valid, trend_valid, rsi_valid, macd_valid, adx_valid
            )
            
            # Adjust signal strength based on market environment confidence
            if market_env_info and market_env_info.get('confidence', 0) < 70:
                if signal_strength == 'STRONG':
                    signal_strength = 'MEDIUM'
                elif signal_strength == 'MEDIUM':
                    signal_strength = 'WEAK'
            
            # Check if only strong signals are allowed for early entry
            if self.early_entry_strong_signal_only and signal_strength != 'STRONG':
                logger.info(
                    f"[EARLY_ENTRY] {symbol}: "
                    f"Signal strength={signal_strength}, "
                    f"only STRONG signals allowed for early entry, skipping"
                )
                return
            
            # If all conditions met, open position
            if all_conditions_met:
                logger.info(
                    f"[EARLY_ENTRY] {symbol}: "
                    f"All conditions met, opening position early at {progress*100:.1f}% K-line progress"
                )
                
                # Get current price
                current_price = self.data_handler.get_current_price(symbol)
                
                # Calculate stop loss price
                stop_loss_price = self._calculate_stop_loss_price(
                    symbol,
                    kline,
                    direction,
                    range_info.get('current_range', 0)
                )
                
                # Calculate dynamic take profit
                take_profit_percent = self._calculate_take_profit_percent(symbol, direction)
                
                # Open position
                if direction == 'UP':
                    await self._open_long_position(
                        symbol, volume_info, range_info, stop_loss_price, kline,
                        kline.get('close_time'), signal_strength, take_profit_percent
                    )
                else:  # DOWN
                    await self._open_short_position(
                        symbol, volume_info, range_info, stop_loss_price, kline,
                        kline.get('close_time'), signal_strength, take_profit_percent
                    )
                
                # Send notification
                await self.telegram_client.send_message(
                    f"⚡ 提前开仓执行\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {direction}\n"
                    f"K线进度: {progress*100:.1f}%\n"
                    f"信号强度: {signal_strength}\n"
                    f"当前价格: ${current_price:.2f}\n"
                    f"止损价格: ${stop_loss_price:.2f if stop_loss_price else 'N/A'}\n"
                    f"止盈比例: {take_profit_percent*100:.1f}%"
                )
            else:
                logger.info(
                    f"[EARLY_ENTRY] {symbol}: "
                    f"Conditions not met, waiting for K-line close"
                )
                
        except Exception as e:
            logger.error(f"Error checking early entry for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _check_entry_confirmation(self, symbol: str, current_kline: Dict) -> None:
        """
        Check if entry confirmation conditions are met
        
        Args:
            symbol: Trading pair symbol
            current_kline: Current K-line that just closed
        """
        try:
            # Get pending entry confirmation
            if symbol not in self.pending_entry_confirmations:
                return
            
            pending = self.pending_entry_confirmations[symbol]
            direction = pending['direction']
            entry_kline = pending['entry_kline']
            
            logger.info(
                f"[ENTRY_CONFIRMATION] {symbol}: "
                f"Checking confirmation for {direction} signal..."
            )
            
            # Get current price
            current_price = current_kline.get('close', 0)
            entry_price = entry_kline.get('close', 0)
            
            if current_price == 0 or entry_price == 0:
                logger.warning(f"Invalid price for {symbol}, skipping confirmation check")
                del self.pending_entry_confirmations[symbol]
                return
            
            # Calculate price change
            price_change = (current_price - entry_price) / entry_price if entry_price > 0 else 0
            
            # Check price confirmation
            price_confirmed = False
            if self.entry_confirmation_type in ['price', 'both']:
                if direction == 'UP':
                    # For long, price should continue up
                    price_confirmed = price_change >= self.entry_confirmation_price_threshold
                else:  # DOWN
                    # For short, price should continue down
                    price_confirmed = price_change <= -self.entry_confirmation_price_threshold
                
                logger.info(
                    f"[ENTRY_CONFIRMATION] {symbol}: "
                    f"Price confirmation: {price_confirmed}, "
                    f"price_change={price_change*100:.2f}%, "
                    f"threshold={self.entry_confirmation_price_threshold*100:.2f}%"
                )
            
            # Check volume confirmation
            volume_confirmed = False
            if self.entry_confirmation_type in ['volume', 'both']:
                # Get volume info for current kline
                volume_valid, volume_info = self._check_volume_condition(symbol, current_kline)
                volume_confirmed = volume_valid and volume_info.get('ratio_5', 0) >= self.entry_confirmation_volume_threshold
                
                logger.info(
                    f"[ENTRY_CONFIRMATION] {symbol}: "
                    f"Volume confirmation: {volume_confirmed}, "
                    f"volume_ratio={volume_info.get('ratio_5', 0):.2f}, "
                    f"threshold={self.entry_confirmation_volume_threshold}"
                )
            
            # Determine if confirmation is met
            if self.entry_confirmation_type == 'price':
                confirmation_met = price_confirmed
            elif self.entry_confirmation_type == 'volume':
                confirmation_met = volume_confirmed
            else:  # both
                confirmation_met = price_confirmed and volume_confirmed
            
            if confirmation_met:
                logger.info(
                    f"[ENTRY_CONFIRMATION] {symbol}: "
                    f"Confirmation met, opening position..."
                )
                
                # Calculate stop loss price
                stop_loss_price = self._calculate_stop_loss_price(
                    symbol,
                    entry_kline,
                    direction,
                    pending['range_info'].get('current_range', 0)
                )
                
                # Calculate dynamic take profit
                take_profit_percent = self._calculate_take_profit_percent(symbol, direction)
                
                # Open position
                if direction == 'UP':
                    await self._open_long_position(
                        symbol,
                        pending['volume_info'],
                        pending['range_info'],
                        stop_loss_price,
                        entry_kline,
                        pending['kline_time'],
                        pending['signal_strength'],
                        take_profit_percent
                    )
                else:  # DOWN
                    await self._open_short_position(
                        symbol,
                        pending['volume_info'],
                        pending['range_info'],
                        stop_loss_price,
                        entry_kline,
                        pending['kline_time'],
                        pending['signal_strength'],
                        take_profit_percent
                    )
                
                # Send confirmation notification
                await self.telegram_client.send_message(
                    f"✅ 入场确认通过\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {direction}\n"
                    f"信号强度: {pending['signal_strength']}\n"
                    f"确认类型: {self.entry_confirmation_type}\n"
                    f"价格变化: {price_change*100:.2f}%\n"
                    f"当前价格: ${current_price:.2f}\n"
                    f"止损价格: ${stop_loss_price:.2f if stop_loss_price else 'N/A'}\n"
                    f"止盈比例: {take_profit_percent*100:.1f}%"
                )
                
                # Clear pending confirmation
                del self.pending_entry_confirmations[symbol]
            else:
                logger.info(
                    f"[ENTRY_CONFIRMATION] {symbol}: "
                    f"Confirmation not met, signal rejected"
                )
                
                # Send rejection notification
                await self.telegram_client.send_message(
                    f"❌ 入场确认失败\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {direction}\n"
                    f"信号强度: {pending['signal_strength']}\n"
                    f"确认类型: {self.entry_confirmation_type}\n"
                    f"价格变化: {price_change*100:.2f}%\n"
                    f"价格确认: {'✅' if price_confirmed else '❌'}\n"
                    f"成交量确认: {'✅' if volume_confirmed else '❌'}\n"
                    f"信号已拒绝，等待新信号"
                )
                
                # Clear pending confirmation
                del self.pending_entry_confirmations[symbol]
                
        except Exception as e:
            logger.error(f"Error checking entry confirmation for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Clear pending confirmation on error
            if symbol in self.pending_entry_confirmations:
                del self.pending_entry_confirmations[symbol]
    
    def _check_drawdown_protection(self) -> Tuple[bool, Optional[str]]:
        """
        Check if trading should be paused due to drawdown protection
        
        Returns:
            Tuple of (can_trade, reason) where reason is None if can_trade is True
        """
        try:
            if not self.drawdown_protection_enabled:
                return True, None
            
            import time
            current_time = int(time.time())
            
            # Check if trading is paused
            if self.trading_paused_until > current_time:
                remaining_time = self.trading_paused_until - current_time
                remaining_minutes = remaining_time / 60
                return False, f"交易暂停中，剩余 {remaining_minutes:.1f} 分钟"
            
            # Check daily loss limit
            if self.daily_start_balance > 0:
                daily_loss_percent = abs(self.daily_pnl) / self.daily_start_balance if self.daily_pnl < 0 else 0
                if daily_loss_percent >= self.max_daily_loss_percent:
                    return False, f"已达到日亏损限制 {self.max_daily_loss_percent*100:.1f}%，今日停止交易"
            
            # Check consecutive losses
            if self.consecutive_losses >= self.max_consecutive_losses:
                return False, f"连续亏损 {self.consecutive_losses} 次，已达到最大限制"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking drawdown protection: {e}")
            return True, None
    
    def _update_trade_result(self, pnl: float) -> None:
        """
        Update trade result for drawdown protection
        
        Args:
            pnl: Profit or loss from the trade
        """
        try:
            if not self.drawdown_protection_enabled:
                return
            
            # Update daily PnL
            self.daily_pnl += pnl
            
            # Update consecutive losses
            if pnl < 0:
                self.consecutive_losses += 1
                logger.warning(
                    f"[DRAWDOWN_PROTECTION] "
                    f"Consecutive losses: {self.consecutive_losses}/{self.max_consecutive_losses}, "
                    f"daily PnL: ${self.daily_pnl:.2f}"
                )
                
                # Check if position reduction should be activated
                if self.consecutive_losses >= self.max_consecutive_losses:
                    self.position_reduction_active = True
                    import time
                    self.trading_paused_until = int(time.time()) + self.trading_pause_duration
                    
                    logger.warning(
                        f"[DRAWDOWN_PROTECTION] "
                        f"Max consecutive losses reached, pausing trading for {self.trading_pause_duration/60:.1f} minutes"
                    )
                    
                    # Send notification
                    import asyncio
                    asyncio.create_task(self.telegram_client.send_message(
                        f"🛑 回撤保护触发\n\n"
                        f"连续亏损: {self.consecutive_losses} 次\n"
                        f"日盈亏: ${self.daily_pnl:.2f}\n"
                        f"交易暂停: {self.trading_pause_duration/60:.1f} 分钟\n"
                        f"仓位缩减: {self.position_reduction_on_loss*100:.1f}%"
                    ))
            else:
                # Reset consecutive losses on profit
                self.consecutive_losses = 0
                if self.position_reduction_active:
                    self.position_reduction_active = False
                    logger.info("[DRAWDOWN_PROTECTION] Position reduction deactivated")
            
            # Check daily loss limit
            if self.daily_start_balance > 0:
                daily_loss_percent = abs(self.daily_pnl) / self.daily_start_balance if self.daily_pnl < 0 else 0
                if daily_loss_percent >= self.max_daily_loss_percent:
                    logger.warning(
                        f"[DRAWDOWN_PROTECTION] "
                        f"Daily loss limit reached: {daily_loss_percent*100:.1f}% >= {self.max_daily_loss_percent*100:.1f}%"
                    )
                    
                    # Send notification
                    import asyncio
                    asyncio.create_task(self.telegram_client.send_message(
                        f"🛑 日亏损限制触发\n\n"
                        f"日盈亏: ${self.daily_pnl:.2f}\n"
                        f"日亏损比例: {daily_loss_percent*100:.1f}%\n"
                        f"限制比例: {self.max_daily_loss_percent*100:.1f}%\n"
                        f"今日停止交易"
                    ))
            
        except Exception as e:
            logger.error(f"Error updating trade result: {e}")
    
    def _get_position_ratio(self, signal_strength: str) -> float:
        """
        Get position ratio based on signal strength and drawdown protection
        
        Args:
            signal_strength: Signal strength (STRONG/MEDIUM/WEAK)
            
        Returns:
            Position ratio
        """
        try:
            # Get base position ratio based on signal strength
            if signal_strength == 'STRONG':
                base_ratio = self.strong_signal_position_ratio
            elif signal_strength == 'MEDIUM':
                base_ratio = self.medium_signal_position_ratio
            else:  # WEAK
                base_ratio = self.weak_signal_position_ratio
            
            # Apply position reduction if active
            if self.position_reduction_active:
                adjusted_ratio = base_ratio * self.position_reduction_on_loss
                logger.info(
                    f"[DRAWDOWN_PROTECTION] "
                    f"Position reduction active: {base_ratio*100:.1f}% -> {adjusted_ratio*100:.1f}%"
                )
                return adjusted_ratio
            
            return base_ratio
            
        except Exception as e:
            logger.error(f"Error getting position ratio: {e}")
            return 0.5  # Default to 50% on error
    
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
            
            # Check market environment filter if enabled
            market_env_valid = True
            market_env_info = None
            if self.market_env_filter_enabled:
                market_env_valid, market_env_info = self._check_market_environment_filter(symbol, direction_5m)
            
            # Check multi-timeframe trend if enabled
            multi_timeframe_valid = True
            multi_timeframe_info = None
            if self.multi_timeframe_enabled:
                multi_timeframe_valid, multi_timeframe_info = self._check_multi_timeframe_trend(symbol, direction_5m)
            
            # Check sentiment filter if enabled
            sentiment_valid = True
            sentiment_info = None
            if self.sentiment_filter_enabled:
                sentiment_valid, sentiment_info = self._check_sentiment_filter(direction_5m)
            
            # Check ML filter if enabled
            ml_valid = True
            ml_info = None
            if self.ml_filter_enabled:
                ml_valid, ml_info = self._check_ml_filter(symbol, direction_5m)
            
            # Determine if all conditions are met
            all_conditions_met = volume_valid and range_valid and body_valid and trend_valid and rsi_valid and macd_valid and adx_valid and market_env_valid and multi_timeframe_valid and sentiment_valid and ml_valid
            
            # Calculate signal strength
            signal_strength = self.technical_analyzer.calculate_signal_strength(
                volume_valid, range_valid, body_valid, trend_valid, rsi_valid, macd_valid, adx_valid
            )
            
            # Adjust signal strength based on market environment confidence
            if market_env_info and market_env_info.get('confidence', 0) < 70:
                # Lower confidence market environment reduces signal strength
                if signal_strength == 'STRONG':
                    signal_strength = 'MEDIUM'
                elif signal_strength == 'MEDIUM':
                    signal_strength = 'WEAK'
            
            logger.info(
                f"[STRATEGY] Condition check for {symbol}: "
                f"volume_valid={volume_valid}, "
                f"range_valid={range_valid}, "
                f"body_valid={body_valid}, "
                f"trend_valid={trend_valid}, "
                f"rsi_valid={rsi_valid}, "
                f"macd_valid={macd_valid}, "
                f"adx_valid={adx_valid}, "
                f"market_env_valid={market_env_valid}, "
                f"multi_timeframe_valid={multi_timeframe_valid}, "
                f"sentiment_valid={sentiment_valid}, "
                f"ml_valid={ml_valid}, "
                f"signal_strength={signal_strength}, "
                f"all_conditions_met={all_conditions_met}"
            )
            
            # Log market environment details if available
            if market_env_info:
                logger.info(
                    f"[MARKET_ENV] {symbol}: "
                    f"type={market_env_info.get('market_type')}, "
                    f"direction={market_env_info.get('trend_direction')}, "
                    f"strength={market_env_info.get('trend_strength')}, "
                    f"confidence={market_env_info.get('confidence')}%, "
                    f"volatility={market_env_info.get('volatility', 0):.2f}%"
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
                    market_env_info=market_env_info,
                    multi_timeframe_info=multi_timeframe_info,
                    sentiment_info=sentiment_info,
                    ml_info=ml_info,
                    signal_strength=signal_strength,
                    kline_time=kline_5m.get('close_time')
                )
                
                # Check if entry confirmation is enabled
                if self.entry_confirmation_enabled:
                    # Store pending entry confirmation
                    self.pending_entry_confirmations[symbol] = {
                        'direction': direction_5m,
                        'kline_time': kline_5m.get('close_time'),
                        'signal_strength': signal_strength,
                        'volume_info': volume_info,
                        'range_info': range_info,
                        'body_info': body_info,
                        'trend_info': trend_info,
                        'rsi_info': rsi_info,
                        'macd_info': macd_info,
                        'adx_info': adx_info,
                        'market_env_info': market_env_info,
                        'multi_timeframe_info': multi_timeframe_info,
                        'sentiment_info': sentiment_info,
                        'ml_info': ml_info,
                        'entry_kline': kline_5m
                    }
                    logger.info(
                        f"[ENTRY_CONFIRMATION] {symbol}: "
                        f"Signal detected, waiting for confirmation on next kline..."
                    )
                    await self.telegram_client.send_message(
                        f"⏳ 等待入场确认\n\n"
                        f"交易对: {symbol}\n"
                        f"方向: {direction_5m}\n"
                        f"信号强度: {signal_strength}\n"
                        f"确认类型: {self.entry_confirmation_type}\n"
                        f"等待K线数: {self.entry_confirmation_wait_klines}"
                    )
                else:
                    # Open position immediately without confirmation
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
                logger.info(f"Not all conditions met for {symbol}: volume={volume_valid}, range={range_valid}, body={body_valid}, trend={trend_valid}, rsi={rsi_valid}, macd={macd_valid}, adx={adx_valid}, market_env={market_env_valid}, multi_timeframe={multi_timeframe_valid}")
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
                    market_env_info=market_env_info,
                    multi_timeframe_info=multi_timeframe_info,
                    sentiment_info=sentiment_info,
                    ml_info=ml_info,
                    signal_strength=signal_strength,
                    kline_time=kline_5m.get('close_time')
                )
            
            # Add explicit log to confirm completion of check
            logger.info(f"[STRATEGY] _check_and_open_position completed for {symbol}")
                
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
    def _calculate_take_profit_percent(self, symbol: str, kline_direction: str) -> float:
        """
        Calculate dynamic take profit percentage based on trend strength (ADX) and volatility (ATR)
        
        优化后的动态止盈策略：
        1. 基于ADX判断趋势强度
        2. 基于ATR判断波动率，高波动时提高止盈目标
        3. 综合调整止盈比例
        
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
            
            # Calculate ATR for volatility
            atr_series = self.technical_analyzer.calculate_atr(df, period=self.atr_period)
            if atr_series is None or len(atr_series) == 0:
                logger.warning(f"Could not calculate ATR for {symbol}, using default take profit")
                return self.take_profit_percent
            
            # Get latest values
            latest_adx = adx_series.iloc[-1]
            latest_atr = atr_series.iloc[-1]
            latest_price = df['close'].iloc[-1]
            
            # Calculate ATR percentage (volatility)
            atr_percent = (latest_atr / latest_price) * 100 if latest_price > 0 else 0
            
            # Base take profit based on ADX trend strength
            if latest_adx >= self.adx_trend_threshold:
                # Strong trend - use higher base take profit
                base_take_profit = self.strong_trend_take_profit_percent
                trend_strength = "强趋势"
            else:
                # Weak trend - use lower base take profit
                base_take_profit = self.weak_trend_take_profit_percent
                trend_strength = "弱趋势"
            
            # Adjust take profit based on volatility (ATR)
            # High volatility: increase take profit target
            # Low volatility: decrease take profit target
            volatility_adjustment = 0
            if atr_percent > 2.0:  # High volatility (>2%)
                volatility_adjustment = 0.02  # Add 2%
                volatility_level = "高波动"
            elif atr_percent > 1.0:  # Medium volatility (1-2%)
                volatility_adjustment = 0.01  # Add 1%
                volatility_level = "中波动"
            else:  # Low volatility (<1%)
                volatility_adjustment = -0.01  # Subtract 1%
                volatility_level = "低波动"
            
            # Calculate final take profit
            take_profit_percent = base_take_profit + volatility_adjustment
            
            # Ensure take profit is within reasonable bounds
            min_take_profit = 0.02  # Minimum 2%
            max_take_profit = 0.10  # Maximum 10%
            take_profit_percent = max(min_take_profit, min(max_take_profit, take_profit_percent))
            
            logger.info(
                f"[DYNAMIC_TAKE_PROFIT] {symbol}: "
                f"ADX={latest_adx:.2f} ({trend_strength}), "
                f"ATR={latest_atr:.2f} ({atr_percent:.2f}%, {volatility_level}), "
                f"base_tp={base_take_profit*100:.1f}%, "
                f"adjustment={volatility_adjustment*100:+.1f}%, "
                f"final_tp={take_profit_percent*100:.1f}%"
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
        Calculate ATR-based stop loss distance with dynamic adjustment
        
        优化后的ATR止损距离计算：
        1. 基于ATR计算基础止损距离
        2. 根据波动率（ATR百分比）动态调整倍数
        3. 高波动时增加倍数，避免过早止损
        4. 低波动时减少倍数，更快止损
        
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
            
            # Calculate ATR percentage (volatility)
            atr_percent = (latest_atr / current_price) * 100 if current_price > 0 else 0
            
            # Dynamic multiplier adjustment based on volatility
            # High volatility: increase multiplier to avoid premature stop loss
            # Low volatility: decrease multiplier for tighter stop loss
            dynamic_multiplier = self.atr_stop_loss_multiplier
            
            if atr_percent > 2.0:  # High volatility (>2%)
                dynamic_multiplier = self.atr_stop_loss_multiplier * 1.3  # Increase by 30%
                volatility_level = "高波动"
            elif atr_percent > 1.0:  # Medium volatility (1-2%)
                dynamic_multiplier = self.atr_stop_loss_multiplier  # Use base multiplier
                volatility_level = "中波动"
            else:  # Low volatility (<1%)
                dynamic_multiplier = self.atr_stop_loss_multiplier * 0.8  # Decrease by 20%
                volatility_level = "低波动"
            
            # Calculate stop loss distance with dynamic multiplier
            stop_loss_distance = latest_atr * dynamic_multiplier
            
            # Ensure stop loss distance is within reasonable bounds
            min_distance = current_price * self.stop_loss_min_distance_percent
            max_distance = current_price * self.stop_loss_max_distance_percent
            stop_loss_distance = max(min_distance, min(max_distance, stop_loss_distance))
            
            logger.info(
                f"[DYNAMIC_ATR_STOP_LOSS] {symbol}: "
                f"ATR={latest_atr:.2f} ({atr_percent:.2f}%, {volatility_level}), "
                f"base_multiplier={self.atr_stop_loss_multiplier}, "
                f"dynamic_multiplier={dynamic_multiplier:.2f}, "
                f"distance={stop_loss_distance:.2f} ({stop_loss_distance/current_price*100:.2f}%), "
                f"bounds=[{min_distance:.2f}, {max_distance:.2f}]"
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
            
            # Check drawdown protection before opening position
            can_trade, drawdown_reason = self._check_drawdown_protection()
            if not can_trade:
                logger.warning(f"[DRAWDOWN_PROTECTION] Cannot open position for {symbol}: {drawdown_reason}")
                await self.telegram_client.send_message(
                    f"🛑 回撤保护阻止开仓\n\n"
                    f"交易对: {symbol}\n"
                    f"原因: {drawdown_reason}"
                )
                return
            
            # Calculate position size with risk management
            quantity = self.trading_executor.calculate_position_size(
                current_price,
                symbol,
                stop_loss_distance_percent=stop_loss_distance_percent
            )
            if quantity is None:
                logger.error(f"Could not calculate position size for {symbol}")
                return
            
            # Get position ratio based on signal strength and drawdown protection
            position_ratio = self._get_position_ratio(signal_strength)
            
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
            
            # Check drawdown protection before opening position
            can_trade, drawdown_reason = self._check_drawdown_protection()
            if not can_trade:
                logger.warning(f"[DRAWDOWN_PROTECTION] Cannot open position for {symbol}: {drawdown_reason}")
                await self.telegram_client.send_message(
                    f"🛑 回撤保护阻止开仓\n\n"
                    f"交易对: {symbol}\n"
                    f"原因: {drawdown_reason}"
                )
                return
            
            # Calculate position size with risk management
            quantity = self.trading_executor.calculate_position_size(
                current_price,
                symbol,
                stop_loss_distance_percent=stop_loss_distance_percent
            )
            if quantity is None:
                logger.error(f"Could not calculate position size for {symbol}")
                return
            
            # Get position ratio based on signal strength and drawdown protection
            position_ratio = self._get_position_ratio(signal_strength)
            
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
                    
                    # Update trade result for drawdown protection
                    self._update_trade_result(pnl)
                    
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
                    
                    # Update trade result for drawdown protection
                    self._update_trade_result(pnl)
                    
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
                    
                    # Update trade result for drawdown protection
                    self._update_trade_result(pnl)
                    
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
        Implements both fixed take profit and trailing take profit with dynamic adjustment
        
        优化后的止盈策略：
        1. 基于波动率（ATR）动态调整移动止盈距离
        2. 高波动时增加移动止盈距离，避免过早平仓
        3. 低波动时减少移动止盈距离，更快锁定利润
        
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
            
            # Calculate dynamic trailing take profit percent based on volatility
            dynamic_trailing_percent = self._calculate_dynamic_trailing_percent(symbol)
            
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
                    # Calculate trailing take profit threshold based on peak price and dynamic trailing percent
                    trailing_threshold = self.position_peak_prices[symbol] * (1 - dynamic_trailing_percent) if position_side == 'LONG' else self.position_peak_prices[symbol] * (1 + dynamic_trailing_percent)
                    
                    # Only close if price drops below trailing threshold
                    if position_side == 'LONG':
                        if current_price >= trailing_threshold:
                            logger.info(
                                f"[TAKE_PROFIT_WAITING] {symbol}: "
                                f"current={current_price:.2f} >= trailing={trailing_threshold:.2f}, "
                                f"trailing_percent={dynamic_trailing_percent*100:.2f}%, "
                                f"continuing to trail..."
                            )
                            return
                    else:  # SHORT
                        if current_price <= trailing_threshold:
                            logger.info(
                                f"[TAKE_PROFIT_WAITING] {symbol}: "
                                f"current={current_price:.2f} <= trailing={trailing_threshold:.2f}, "
                                f"trailing_percent={dynamic_trailing_percent*100:.2f}%, "
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
                                   f"移动止盈: {dynamic_trailing_percent*100:.2f}%\n"
                                   f"{'最高价' if position_side == 'LONG' else '最低价'}: ${self.position_peak_prices[symbol]:.2f}"
                    )
                    
                    # Update trade result for drawdown protection
                    self._update_trade_result(pnl)
                    
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
    
    def _calculate_dynamic_trailing_percent(self, symbol: str) -> float:
        """
        Calculate dynamic trailing take profit percentage based on volatility (ATR)
        
        优化后的移动止盈距离计算：
        - 高波动（ATR > 2%）：增加移动止盈距离到3%，避免过早平仓
        - 中波动（ATR 1-2%）：使用标准移动止盈距离2%
        - 低波动（ATR < 1%）：减少移动止盈距离到1.5%，更快锁定利润
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dynamic trailing take profit percentage
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}, using default trailing percent")
                return self.take_profit_trailing_percent
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.atr_period + 1:
                logger.warning(f"Not enough closed K-lines for ATR calculation: {len(closed_klines)}, using default trailing percent")
                return self.take_profit_trailing_percent
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Calculate ATR
            atr_series = self.technical_analyzer.calculate_atr(df, period=self.atr_period)
            if atr_series is None or len(atr_series) == 0:
                logger.warning(f"Could not calculate ATR for {symbol}, using default trailing percent")
                return self.take_profit_trailing_percent
            
            # Get latest ATR value and price
            latest_atr = atr_series.iloc[-1]
            latest_price = df['close'].iloc[-1]
            
            # Calculate ATR percentage (volatility)
            atr_percent = (latest_atr / latest_price) * 100 if latest_price > 0 else 0
            
            # Determine trailing percent based on volatility
            if atr_percent > 2.0:  # High volatility
                trailing_percent = 0.03  # 3%
                volatility_level = "高波动"
            elif atr_percent > 1.0:  # Medium volatility
                trailing_percent = self.take_profit_trailing_percent  # Use configured value (default 2%)
                volatility_level = "中波动"
            else:  # Low volatility
                trailing_percent = 0.015  # 1.5%
                volatility_level = "低波动"
            
            logger.debug(
                f"[DYNAMIC_TRAILING] {symbol}: "
                f"ATR={latest_atr:.2f} ({atr_percent:.2f}%, {volatility_level}), "
                f"trailing_percent={trailing_percent*100:.2f}%"
            )
            
            return trailing_percent
            
        except Exception as e:
            logger.error(f"Error calculating dynamic trailing percent for {symbol}: {e}")
            return self.take_profit_trailing_percent
    
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
                    
                    # Update trade result for drawdown protection
                    self._update_trade_result(pnl)
                    
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
        
        优化后的分批止盈：
        1. 使用部分平仓方法，而不是全仓平仓
        2. 更新持仓数量，支持多次分批止盈
        3. 记录每次分批止盈的盈亏
        
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
                    
                    # Calculate ratio to close
                    ratio = self.partial_take_profit_ratios[i] if i < len(self.partial_take_profit_ratios) else 0.5
                    
                    # Execute partial close using the new method
                    import asyncio
                    order = await asyncio.to_thread(
                        self.trading_executor.close_partial_position,
                        symbol,
                        ratio
                    )
                    
                    if order:
                        # Calculate PnL for this partial close
                        close_quantity = quantity * ratio
                        pnl = 0.0
                        if current_price and entry_price > 0:
                            if position_side == 'LONG':
                                pnl = (current_price - entry_price) * close_quantity
                            else:  # SHORT
                                pnl = (entry_price - current_price) * close_quantity
                        
                        # Update position quantity in position manager
                        position = self.position_manager.get_position(symbol)
                        if position:
                            new_quantity = quantity - close_quantity
                            position['quantity'] = new_quantity
                            logger.info(
                                f"Position quantity updated for {symbol}: "
                                f"{quantity:.6f} -> {new_quantity:.6f}"
                            )
                        
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
                            f"剩余数量: {position['quantity'] if position else 0:.4f}\n"
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