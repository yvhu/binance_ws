"""
5-Minute K-Line Trading Strategy
Implements the 5m K-line trading strategy with dynamic position management
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Tuple
from datetime import datetime
import pandas as pd

from ..config.config_manager import ConfigManager
from ..indicators.technical_analyzer import TechnicalAnalyzer
from ..trading.position_manager import PositionManager
from ..trading.trading_executor import TradingExecutor
from ..trading.limit_order_monitor import LimitOrderMonitor
from ..trading.order_persistence import OrderPersistence
from ..binance.data_handler import BinanceDataHandler
from ..telegram.telegram_client import TelegramClient
from ..data.trade_logger import TradeLogger

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
        
        # Initialize trade logger
        self.trade_logger = TradeLogger()
        
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
        
        # Profit drawdown protection configuration (利润回撤保护)
        self.profit_drawdown_protection_enabled = config.get_config(
            "strategy", "profit_drawdown_protection_enabled", default=True
        )
        self.profit_drawdown_threshold_percent = config.get_config(
            "strategy", "profit_drawdown_threshold_percent", default=0.01
        )
        self.max_profit_drawdown_percent = config.get_config(
            "strategy", "max_profit_drawdown_percent", default=0.005
        )
        
        # Dynamic trailing stop distance configuration (动态移动止损距离)
        self.dynamic_trailing_distance_enabled = config.get_config(
            "strategy", "dynamic_trailing_distance_enabled", default=True
        )
        self.trailing_profit_levels = config.get_config(
            "strategy", "trailing_profit_levels", default=[0.01, 0.015, 0.02]
        )
        self.trailing_distance_levels = config.get_config(
            "strategy", "trailing_distance_levels", default=[0.003, 0.005, 0.008]
        )
        
        # Track peak profit for drawdown protection
        self.position_peak_profits: Dict[str, float] = {}  # symbol -> peak profit percentage
        
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
        
        # Additional indicator filters
        self.rsi_filter_enabled = config.get_config("strategy", "rsi_filter_enabled", default=True)
        self.rsi_long_max = config.get_config("strategy", "rsi_long_max", default=70)
        self.rsi_short_min = config.get_config("strategy", "rsi_short_min", default=30)
        
        # Sideways market filter (横盘市场过滤)
        self.sideways_market_filter_enabled = config.get_config("strategy", "sideways_market_filter_enabled", default=True)
        self.sideways_market_adx_threshold = config.get_config("strategy", "sideways_market_adx_threshold", default=20)
        self.min_trend_strength = config.get_config("strategy", "min_trend_strength", default=0.3)
        
        # Signal confirmation (信号确认)
        self.signal_confirmation_enabled = config.get_config("strategy", "signal_confirmation_enabled", default=True)
        self.signal_confirmation_klines = config.get_config("strategy", "signal_confirmation_klines", default=2)
        self.min_signal_strength = config.get_config("strategy", "min_signal_strength", default="MEDIUM")
        
        # Volume confirmation (成交量确认)
        self.volume_confirmation_enabled = config.get_config("strategy", "volume_confirmation_enabled", default=True)
        self.volume_confirmation_klines = config.get_config("strategy", "volume_confirmation_klines", default=3)
        
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
        
        
        # Track trade data for logging
        self.active_trades: Dict[str, Dict] = {}  # symbol -> trade data
        
        # Track partial take profit status for each position
        self.partial_take_profit_status: Dict[str, Dict] = {}  # symbol -> {level_index: bool}
        
        # Limit order configuration
        self.limit_order_enabled = config.get_config("trading.limit_order", "enabled", default=True)
        self.limit_order_entry_enabled = config.get_config("trading.limit_order", "entry_enabled", default=True)
        self.limit_order_take_profit_enabled = config.get_config("trading.limit_order", "take_profit_enabled", default=True)
        self.limit_order_entry_price_offset_percent = config.get_config("trading.limit_order", "entry_price_offset_percent", default=0.001)
        self.limit_order_take_profit_price_offset_percent = config.get_config("trading.limit_order", "take_profit_price_offset_percent", default=0.001)
        self.limit_order_entry_timeout = config.get_config("trading.limit_order", "entry_limit_order_timeout", default=30)
        self.limit_order_take_profit_timeout = config.get_config("trading.limit_order", "take_profit_limit_order_timeout", default=60)
        self.limit_order_price_away_threshold_percent = config.get_config("trading.limit_order", "price_away_threshold_percent", default=0.002)
        self.limit_order_rapid_change_threshold_percent = config.get_config("trading.limit_order", "rapid_change_threshold_percent", default=0.003)
        self.limit_order_rapid_change_window = config.get_config("trading.limit_order", "rapid_change_window", default=5)
        self.limit_order_use_support_resistance = config.get_config("trading.limit_order", "use_support_resistance", default=True)
        self.limit_order_support_resistance_period = config.get_config("trading.limit_order", "support_resistance_period", default=20)
        
        # 未完成订单处理策略配置
        self.limit_order_action_on_timeout = config.get_config("trading.limit_order", "action_on_timeout", default="convert_to_market")
        self.limit_order_action_on_signal_reversal = config.get_config("trading.limit_order", "action_on_signal_reversal", default="cancel")
        self.limit_order_cancel_on_new_signal = config.get_config("trading.limit_order", "cancel_on_new_signal", default=True)
        self.limit_order_max_pending_orders = config.get_config("trading.limit_order", "max_pending_orders", default=1)
        self.limit_order_cancel_on_kline_close = config.get_config("trading.limit_order", "cancel_on_kline_close", default=False)
        self.limit_order_cancel_on_price_move_away = config.get_config("trading.limit_order", "cancel_on_price_move_away", default=True)
        
        # Track pending limit orders for each symbol
        self.pending_limit_orders: Dict[str, Dict] = {}  # symbol -> {order_id, side, order_price, quantity, timestamp}
        
        # Initialize order persistence
        self.order_persistence = OrderPersistence()
        
        # Load pending orders from database
        self.pending_limit_orders = self.order_persistence.load_pending_orders()
        
        # Initialize limit order monitor
        self.limit_order_monitor = LimitOrderMonitor(
            trading_executor=trading_executor,
            config=config
        )
        
        # Set price callback for limit order monitor
        self.limit_order_monitor.set_price_callback(self._get_current_price_for_monitor)
        
        # Sync orders with exchange on startup
        asyncio.create_task(self._sync_orders_with_exchange())
    
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
        
        # Check for real-time engulfing stop loss if position exists
        if self.position_manager.has_position(symbol):
            await self._check_engulfing_stop_loss_realtime(symbol, kline_info)
            # Check for real-time trend reversal
            await self._check_realtime_trend_reversal(symbol, kline_info)
        
        # Check for early entry if K-line is not closed (real-time entry)
        if not is_closed:
            await self._check_early_entry(symbol, kline_info)
    
    async def on_5m_kline_close(self, kline_info: Dict) -> None:
        """
        Handle 5-minute K-line close event (trigger for opening position and checking stop losses)
        
        Args:
            kline_info: K-line information
        """
        symbol = kline_info['symbol']
        interval = kline_info['interval']
        
        # Check for signal reversal and handle pending orders
        await self._check_signal_reversal(symbol, kline_info)
        
        # Check if pending orders should be cancelled on K-line close
        if self.limit_order_cancel_on_kline_close and symbol in self.pending_limit_orders:
            await self._check_and_cancel_pending_orders(
                symbol,
                "K线关闭，取消未成交限价单"
            )
        
        # Check for stop losses if position exists
        if self.position_manager.has_position(symbol):
            # Check engulfing stop loss
            await self._check_engulfing_stop_loss(symbol, kline_info)
            
            # Update trailing stop loss if enabled
            if self.trailing_stop_enabled:
                await self._update_trailing_stop_loss(symbol, kline_info)
        
        # Check if position can be opened (no existing position)
        if self.position_manager.has_position(symbol):
            return
        
        # Execute strategy logic
        await self._check_and_open_position(symbol, kline_info)
    
    def _check_volume_condition(self, symbol: str, current_kline: Dict) -> Tuple[bool, Dict]:
        """
        Check if the current 5m K-line volume meets the minimum requirement
        
        Args:
            symbol: Trading pair symbol
            current_kline: The current 5m K-line to check (may not be closed)
            
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
            
            # For real-time entry check, use all K-lines (including unclosed)
            # For K-line close check, use only closed K-lines
            is_closed = current_kline.get('is_closed', False)
            
            if is_closed:
                # K-line is closed, use only closed K-lines for calculation
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
            else:
                # K-line is not closed (real-time check), use all K-lines
                # Find the index of current K-line in all klines
                current_open_time = current_kline['open_time']
                current_index = -1
                for i, k in enumerate(all_klines):
                    if k['open_time'] == current_open_time:
                        current_index = i
                        break
                
                if current_index == -1:
                    logger.warning(f"Current K-line not found in all klines for {symbol}")
                    return False, {}
                
                # Use all K-lines up to current (including unclosed current)
                klines_for_ma = all_klines[:current_index + 1]
            
            if len(klines_for_ma) < 5:
                logger.warning(f"Not enough K-lines for volume check: {len(klines_for_ma)} (need at least 5)")
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
            current_kline: The current 5m K-line to check (may not be closed)
            
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
            
            # For real-time entry check, use all K-lines (including unclosed)
            # For K-line close check, use only closed K-lines
            is_closed = current_kline.get('is_closed', False)
            
            if is_closed:
                # K-line is closed, use only closed K-lines for calculation
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
            else:
                # K-line is not closed (real-time check), use all K-lines
                # Find the index of current K-line in all klines
                current_open_time = current_kline['open_time']
                current_index = -1
                for i, k in enumerate(all_klines):
                    if k['open_time'] == current_open_time:
                        current_index = i
                        break
                
                if current_index == -1:
                    logger.warning(f"Current K-line not found in all klines for {symbol}")
                    return False, {}
                
                # Use all K-lines up to current (including unclosed current)
                klines_for_ma = all_klines[:current_index + 1]
            
            if len(klines_for_ma) < 5:
                logger.warning(f"Not enough K-lines for range check: {len(klines_for_ma)} (need at least 5)")
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
    
    def _check_sideways_market_filter(self, symbol: str, kline_direction: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if the market is in sideways mode and filter out weak signals
        
        Args:
            symbol: Trading pair symbol
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, sideways_info)
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
                logger.warning(f"Not enough closed K-lines for sideways market filter: {len(closed_klines)}")
                return False, None
            
            # Convert to DataFrame for technical analysis
            df = pd.DataFrame(closed_klines)
            
            # Calculate ADX
            adx_series = self.technical_analyzer.calculate_adx(df, period=14)
            if adx_series is None or len(adx_series) == 0:
                logger.warning(f"Could not calculate ADX for {symbol}")
                return False, None
            
            # Get latest ADX value
            latest_adx = adx_series.iloc[-1]
            
            # Check if market is in sideways mode (ADX below threshold)
            is_sideways = latest_adx < self.sideways_market_adx_threshold
            
            # Calculate trend strength
            trend_strength = 0.0
            if len(closed_klines) >= self.trend_filter_ma_period:
                ma_series = self.technical_analyzer.calculate_ma(df['close'], self.trend_filter_ma_period)
                if len(ma_series) > 0:
                    latest_ma = ma_series.iloc[-1]
                    latest_price = df['close'].iloc[-1]
                    trend_strength = abs(latest_price - latest_ma) / latest_ma if latest_ma > 0 else 0
            
            # Filter out sideways market signals
            if is_sideways:
                logger.info(
                    f"[SIDEWAYS_MARKET_FILTER] {symbol}: "
                    f"ADX={latest_adx:.2f} < {self.sideways_market_adx_threshold}, "
                    f"trend_strength={trend_strength:.3f}, "
                    f"market is sideways, filtering signal"
                )
                return False, {
                    'adx_value': latest_adx,
                    'is_sideways': is_sideways,
                    'trend_strength': trend_strength,
                    'threshold': self.sideways_market_adx_threshold
                }
            
            # Check minimum trend strength
            if trend_strength < self.min_trend_strength:
                logger.info(
                    f"[TREND_STRENGTH_FILTER] {symbol}: "
                    f"trend_strength={trend_strength:.3f} < {self.min_trend_strength}, "
                    f"trend too weak, filtering signal"
                )
                return False, {
                    'adx_value': latest_adx,
                    'is_sideways': is_sideways,
                    'trend_strength': trend_strength,
                    'threshold': self.min_trend_strength
                }
            
            return True, {
                'adx_value': latest_adx,
                'is_sideways': is_sideways,
                'trend_strength': trend_strength,
                'threshold': self.sideways_market_adx_threshold
            }
            
        except Exception as e:
            logger.error(f"Error checking sideways market filter for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None
    
    def _check_signal_confirmation(self, symbol: str, direction: str, current_kline: Dict) -> bool:
        """
        Check if signal is confirmed by multiple K-lines
        
        Args:
            symbol: Trading pair symbol
            direction: 'UP' or 'DOWN'
            current_kline: Current K-line
            
        Returns:
            True if signal is confirmed, False otherwise
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.signal_confirmation_klines:
                logger.warning(f"Not enough closed K-lines for signal confirmation: {len(closed_klines)}")
                return False
            
            # Get recent K-lines for confirmation
            recent_klines = closed_klines[-self.signal_confirmation_klines:]
            
            # Check if all recent K-lines have the same direction
            confirmed_count = 0
            for kline in recent_klines:
                kline_direction = self.technical_analyzer.get_kline_direction(kline)
                if kline_direction == direction:
                    confirmed_count += 1
            
            # Check if enough K-lines confirm the signal
            confirmation_ratio = confirmed_count / len(recent_klines)
            min_confirmation_ratio = 0.7  # Require 70% confirmation
            
            if confirmation_ratio < min_confirmation_ratio:
                logger.info(
                    f"[SIGNAL_CONFIRMATION] {symbol}: "
                    f"direction={direction}, "
                    f"confirmed={confirmed_count}/{len(recent_klines)} ({confirmation_ratio*100:.1f}%), "
                    f"required={min_confirmation_ratio*100:.1f}%, "
                    f"signal not confirmed"
                )
                return False
            
            logger.info(
                f"[SIGNAL_CONFIRMATION] {symbol}: "
                f"direction={direction}, "
                f"confirmed={confirmed_count}/{len(recent_klines)} ({confirmation_ratio*100:.1f}%), "
                f"signal confirmed"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error checking signal confirmation for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _check_volume_confirmation(self, symbol: str) -> bool:
        """
        Check if volume is confirmed by multiple K-lines
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if volume is confirmed, False otherwise
        """
        try:
            # Get all 5m K-lines
            all_klines = self.data_handler.get_klines(symbol, "5m")
            if not all_klines:
                logger.warning(f"No 5m K-line data for {symbol}")
                return False
            
            # Filter only closed K-lines
            closed_klines = [k for k in all_klines if k.get('is_closed', False)]
            
            if len(closed_klines) < self.volume_confirmation_klines:
                logger.warning(f"Not enough closed K-lines for volume confirmation: {len(closed_klines)}")
                return False
            
            # Get recent K-lines for confirmation
            recent_klines = closed_klines[-self.volume_confirmation_klines:]
            
            # Calculate average volume for recent K-lines
            recent_volumes = [k['volume'] for k in recent_klines]
            avg_recent_volume = sum(recent_volumes) / len(recent_volumes)
            
            # Calculate average volume for previous K-lines
            if len(closed_klines) > self.volume_confirmation_klines * 2:
                previous_klines = closed_klines[-(self.volume_confirmation_klines * 2):-self.volume_confirmation_klines]
                previous_volumes = [k['volume'] for k in previous_klines]
                avg_previous_volume = sum(previous_volumes) / len(previous_volumes)
                
                # Check if recent volume is higher than previous volume
                volume_ratio = avg_recent_volume / avg_previous_volume if avg_previous_volume > 0 else 0
                
                if volume_ratio < 1.1:  # Require 10% volume increase
                    logger.info(
                        f"[VOLUME_CONFIRMATION] {symbol}: "
                        f"volume_ratio={volume_ratio:.2f} < 1.1, "
                        f"volume not confirmed"
                    )
                    return False
                
                logger.info(
                    f"[VOLUME_CONFIRMATION] {symbol}: "
                    f"volume_ratio={volume_ratio:.2f} >= 1.1, "
                    f"volume confirmed"
                )
                return True
            else:
                # Not enough historical data, skip confirmation
                return True
            
        except Exception as e:
            logger.error(f"Error checking volume confirmation for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _check_early_entry(self, symbol: str, kline: Dict) -> None:
        """
        实时检查开仓条件（WebSocket实时数据）
        每次K线更新时都检查，不等待K线关闭
        
        Args:
            symbol: Trading pair symbol
            kline: Current K-line (may not be closed)
        """
        try:
            # Check if position already exists
            if self.position_manager.has_position(symbol):
                return
            
            # 实时检查：每次K线更新都检查开仓条件
            # 不限制检查次数，让市场实时决定是否开仓
            
            
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
            
            # Check sideways market filter if enabled
            sideways_valid = True
            sideways_info = None
            if self.sideways_market_filter_enabled:
                sideways_valid, sideways_info = self._check_sideways_market_filter(symbol, direction)
            
            # Check signal confirmation if enabled
            signal_confirmed = True
            if self.signal_confirmation_enabled:
                signal_confirmed = self._check_signal_confirmation(symbol, direction, kline)
            
            # Check volume confirmation if enabled
            volume_confirmed = True
            if self.volume_confirmation_enabled:
                volume_confirmed = self._check_volume_confirmation(symbol)
            
            # Determine if all conditions are met
            all_conditions_met = (
                volume_valid and
                range_valid and
                body_valid and
                trend_valid and
                rsi_valid and
                sideways_valid and
                signal_confirmed and
                volume_confirmed
            )
            
            # Calculate signal strength
            signal_strength = self.technical_analyzer.calculate_signal_strength(
                volume_valid, range_valid, body_valid, trend_valid, rsi_valid, True, True
            )
            
            # If all conditions met, open position
            if all_conditions_met:
                
                # Get current price
                current_price = self.data_handler.get_current_price(symbol)
                
                # Calculate stop loss price
                stop_loss_price = self._calculate_stop_loss_price(
                    symbol,
                    kline,
                    direction,
                    range_info.get('current_range', 0)
                )
                
                # Open position
                if direction == 'UP':
                    await self._open_long_position(
                        symbol, volume_info, range_info, stop_loss_price, kline,
                        kline.get('close_time'), signal_strength, self.take_profit_percent
                    )
                else:  # DOWN
                    await self._open_short_position(
                        symbol, volume_info, range_info, stop_loss_price, kline,
                        kline.get('close_time'), signal_strength, self.take_profit_percent
                    )
                
                # Send notification
                await self.telegram_client.send_message(
                    f"⚡ 实时开仓执行\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {direction}\n"
                    f"信号强度: {signal_strength}\n"
                    f"当前价格: ${f'{current_price:.2f}' if current_price else 'N/A'}\n"
                    f"止损价格: ${f'{stop_loss_price:.2f}' if stop_loss_price else 'N/A'}\n"
                    f"止盈比例: {self.take_profit_percent*100:.1f}%\n"
                    f"⚡ WebSocket实时数据"
                )
        except Exception as e:
            logger.error(f"Error checking early entry for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
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
                    
                    # Close all open positions before pausing trading (async task)
                    import asyncio
                    asyncio.create_task(self._close_all_positions_on_drawdown())
                    
                    # Send notification
                    asyncio.create_task(self.telegram_client.send_message(
                        f"🛑 回撤保护触发\n\n"
                        f"连续亏损: {self.consecutive_losses} 次\n"
                        f"日盈亏: ${self.daily_pnl:.2f}\n"
                        f"交易暂停: {self.trading_pause_duration/60:.1f} 分钟\n"
                        f"仓位缩减: {self.position_reduction_on_loss*100:.1f}%\n"
                        f"已关闭所有持仓"
                    ))
            else:
                # Reset consecutive losses on profit
                self.consecutive_losses = 0
                if self.position_reduction_active:
                    self.position_reduction_active = False
            
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
    
    async def _close_all_positions_on_drawdown(self) -> None:
        """
        Close all open positions when drawdown protection is triggered
        This ensures no positions remain open when trading is paused
        
        This method is called when consecutive losses reach the maximum limit
        """
        try:
            # Get all symbols with open positions
            symbols_to_close = list(self.position_manager.positions.keys())
            
            if not symbols_to_close:
                logger.info("[DRAWDOWN_PROTECTION] No open positions to close")
                return
            
            logger.warning(
                f"[DRAWDOWN_PROTECTION] Closing {len(symbols_to_close)} open positions: {symbols_to_close}"
            )
            
            # Close each position
            for symbol in symbols_to_close:
                try:
                    # Get position details before closing
                    position = self.position_manager.get_position(symbol)
                    if not position:
                        logger.warning(f"[DRAWDOWN_PROTECTION] No position found for {symbol}")
                        continue
                    
                    # Get current price
                    current_price = self.data_handler.get_current_price(symbol)
                    if current_price is None:
                        logger.warning(f"[DRAWDOWN_PROTECTION] Could not get current price for {symbol}")
                        continue
                    
                    # Close position
                    success = await self.trading_executor.close_all_positions(symbol)
                    
                    if success:
                        # Calculate PnL
                        entry_price = position.get('entry_price', 0)
                        quantity = position.get('quantity', 0)
                        position_side = position.get('side', 'LONG')
                        
                        pnl = 0.0
                        if current_price and entry_price > 0:
                            if position_side == 'LONG':
                                pnl = (current_price - entry_price) * quantity
                            else:  # SHORT
                                pnl = (entry_price - current_price) * quantity
                        
                        # Send close notification
                        await self.telegram_client.send_close_notification(
                            symbol=symbol,
                            side=position_side,
                            entry_price=entry_price,
                            exit_price=current_price,
                            quantity=quantity,
                            pnl=pnl,
                            close_reason=f"回撤保护强制平仓\n"
                                       f"连续亏损达到上限\n"
                                       f"交易暂停 {self.trading_pause_duration/60:.1f} 分钟"
                        )
                        
                        # Log exit signal
                        self._log_signal(
                            symbol=symbol,
                            direction='UP' if position_side == 'LONG' else 'DOWN',
                            current_price=current_price,
                            kline={},
                            signal_strength='MEDIUM',
                            volume_info={},
                            range_info={},
                            body_info={},
                            signal_type="EXIT_DRAWDOWN_PROTECTION"
                        )
                        
                        # Log trade data
                        self._log_trade(symbol, position, current_price, "Drawdown Protection")
                        
                        # Clear local position state
                        self.position_manager.close_position(symbol, current_price)
                        
                        # Clear related state
                        if symbol in self.position_peak_prices:
                            del self.position_peak_prices[symbol]
                        if symbol in self.position_entry_times:
                            del self.position_entry_times[symbol]
                        if symbol in self.partial_take_profit_status:
                            del self.partial_take_profit_status[symbol]
                        if symbol in self.stop_loss_first_trigger_time:
                            del self.stop_loss_first_trigger_time[symbol]
                        
                        logger.info(
                            f"[DRAWDOWN_PROTECTION] Successfully closed position for {symbol}, "
                            f"PnL: ${pnl:.2f}"
                        )
                    else:
                        logger.error(f"[DRAWDOWN_PROTECTION] Failed to close position for {symbol}")
                        
                except Exception as e:
                    logger.error(f"[DRAWDOWN_PROTECTION] Error closing position for {symbol}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info("[DRAWDOWN_PROTECTION] All positions closed successfully")
            
        except Exception as e:
            logger.error(f"[DRAWDOWN_PROTECTION] Error in _close_all_positions_on_drawdown: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
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
            
            # Check sideways market filter if enabled
            sideways_valid = True
            sideways_info = None
            if self.sideways_market_filter_enabled:
                sideways_valid, sideways_info = self._check_sideways_market_filter(symbol, direction_5m)
            
            # Check signal confirmation if enabled
            signal_confirmed = True
            if self.signal_confirmation_enabled:
                signal_confirmed = self._check_signal_confirmation(symbol, direction_5m, kline_5m)
            
            # Check volume confirmation if enabled
            volume_confirmed = True
            if self.volume_confirmation_enabled:
                volume_confirmed = self._check_volume_confirmation(symbol)
            
            # Determine if all conditions are met
            all_conditions_met = (
                volume_valid and
                range_valid and
                body_valid and
                trend_valid and
                rsi_valid and
                sideways_valid and
                signal_confirmed and
                volume_confirmed
            )
            
            # Calculate signal strength
            signal_strength = self.technical_analyzer.calculate_signal_strength(
                volume_valid, range_valid, body_valid, trend_valid, rsi_valid, True, True
            )
            
            # Get current price for notification
            current_price = self.data_handler.get_current_price(symbol)
            
            # Send indicator analysis notification with all condition information
            if all_conditions_met:
                # All conditions met - send trade decision
                decision = 'LONG' if direction_5m == 'UP' else 'SHORT'
                
                # Log signal data for analysis (even if no actual trade)
                self._log_signal(
                    symbol=symbol,
                    direction=direction_5m,
                    current_price=current_price,
                    kline=kline_5m,
                    signal_strength=signal_strength,
                    volume_info=volume_info,
                    range_info=range_info,
                    body_info=body_info,
                    trend_info=trend_info,
                    rsi_info=rsi_info,
                )
                
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
                
                # Open position with volume info, range info, stop loss and entry kline
                # Check if limit order is enabled for entry
                use_limit_order = self.limit_order_enabled and self.limit_order_entry_enabled
                
                if direction_5m == 'UP':
                    if use_limit_order:
                        await self._open_long_position_with_limit_order(
                            symbol, volume_info, range_info, stop_loss_price, kline_5m,
                            kline_5m.get('close_time'), signal_strength, self.take_profit_percent
                        )
                    else:
                        await self._open_long_position(
                            symbol, volume_info, range_info, stop_loss_price, kline_5m,
                            kline_5m.get('close_time'), signal_strength, self.take_profit_percent
                        )
                else:  # DOWN
                    if use_limit_order:
                        await self._open_short_position_with_limit_order(
                            symbol, volume_info, range_info, stop_loss_price, kline_5m,
                            kline_5m.get('close_time'), signal_strength, self.take_profit_percent
                        )
                    else:
                        await self._open_short_position(
                            symbol, volume_info, range_info, stop_loss_price, kline_5m,
                            kline_5m.get('close_time'), signal_strength, self.take_profit_percent
                        )
            
        except Exception as e:
            logger.error(f"Error checking entry conditions for {symbol}: {e}")
    
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
                    
                    # Initialize peak profit tracking for drawdown protection
                    self.position_peak_profits[symbol] = 0.0
                    
                    # Record entry time for time-based stop loss
                    self.position_entry_times[symbol] = kline_time if kline_time else int(datetime.now().timestamp() * 1000)
                    
                    
                    # Initialize partial take profit status
                    self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
                    
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
                    
                    # Initialize peak profit tracking for drawdown protection
                    self.position_peak_profits[symbol] = 0.0
                    
                    # Record entry time for time-based stop loss
                    self.position_entry_times[symbol] = kline_time if kline_time else int(datetime.now().timestamp() * 1000)
                    
                    # Initialize partial take profit status
                    self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
                    
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
                    
                    # Log exit signal
                    self._log_signal(
                        symbol=symbol,
                        direction='UP' if position_side == 'LONG' else 'DOWN',
                        current_price=current_price if current_price else 0,
                        kline=current_kline,
                        signal_strength='MEDIUM',
                        volume_info={},
                        range_info={},
                        body_info={},
                        signal_type="EXIT_ENGULFING_STOP_LOSS"
                    )
                    
                    # Log trade data
                    self._log_trade(symbol, position, current_price if current_price else 0, "Engulfing Stop Loss")
                    
                    # Clear local position state to prevent duplicate notifications
                    self.position_manager.close_position(symbol, current_price if current_price else 0)
                    
                else:
                    logger.error(f"Failed to close position due to engulfing stop loss for {symbol}")
            else:
                pass
                
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
                    
                    # Log exit signal
                    self._log_signal(
                        symbol=symbol,
                        direction='UP' if position_side == 'LONG' else 'DOWN',
                        current_price=current_price if current_price else 0,
                        kline=current_kline,
                        signal_strength='MEDIUM',
                        volume_info={},
                        range_info={},
                        body_info={},
                        signal_type="EXIT_REALTIME_ENGULFING_STOP_LOSS"
                    )
                    
                    # Log trade data
                    self._log_trade(symbol, position, current_price if current_price else 0, "Realtime Engulfing Stop Loss")
                    
                    # 清除本地持仓状态
                    self.position_manager.close_position(symbol, current_price if current_price else 0)
                    
                    # 清除相关状态
                    if symbol in self.position_peak_prices:
                        del self.position_peak_prices[symbol]
                    if symbol in self.position_entry_times:
                        del self.position_entry_times[symbol]
                    if symbol in self.partial_take_profit_status:
                        del self.partial_take_profit_status[symbol]
                else:
                    logger.error(f"Failed to close position due to realtime engulfing stop loss for {symbol}")
            else:
                pass
                
        except Exception as e:
            logger.error(f"Error checking realtime engulfing stop loss for {symbol}: {e}")
    
    async def _check_realtime_trend_reversal(self, symbol: str, current_kline: Dict) -> None:
        """
        实时检测趋势反转，提前平仓
        当检测到强吞没形态时立即平仓，不等待K线关闭
        
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
                return
            
            # 检查是否是强吞没形态（实体比例大于阈值）
            if engulfing_ratio >= self.engulfing_body_ratio_threshold:
                # 检查是否与持仓方向相反
                is_reversal = False
                reversal_reason = ""
                
                if position_side == 'LONG' and current_direction == 'DOWN':
                    # 多头持仓，当前是阴线吞没
                    is_reversal = True
                    reversal_reason = "强阴线吞没反转"
                elif position_side == 'SHORT' and current_direction == 'UP':
                    # 空头持仓，当前是阳线吞没
                    is_reversal = True
                    reversal_reason = "强阳线吞没反转"
                
                if is_reversal:
                    logger.warning(
                        f"[REALTIME_TREND_REVERSAL] {symbol}: "
                        f"position_side={position_side}, "
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
                            close_reason=f"实时趋势反转平仓\n"
                                       f"原因: {reversal_reason}\n"
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
                        
                        # Log exit signal
                        self._log_signal(
                            symbol=symbol,
                            direction='UP' if position_side == 'LONG' else 'DOWN',
                            current_price=current_price if current_price else 0,
                            kline=current_kline,
                            signal_strength='MEDIUM',
                            volume_info={},
                            range_info={},
                            body_info={},
                            signal_type="EXIT_REALTIME_TREND_REVERSAL"
                        )
                        
                        # Log trade data
                        self._log_trade(symbol, position, current_price if current_price else 0, "Realtime Trend Reversal")
                        
                        # 清除本地持仓状态
                        self.position_manager.close_position(symbol, current_price if current_price else 0)
                        
                        # 清除相关状态
                        if symbol in self.position_peak_prices:
                            del self.position_peak_prices[symbol]
                        if symbol in self.position_entry_times:
                            del self.position_entry_times[symbol]
                        if symbol in self.partial_take_profit_status:
                            del self.partial_take_profit_status[symbol]
                        if symbol in self.stop_loss_first_trigger_time:
                            del self.stop_loss_first_trigger_time[symbol]
                    else:
                        logger.error(f"Failed to close position due to realtime trend reversal for {symbol}")
            
        except Exception as e:
            logger.error(f"Error checking realtime trend reversal for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
                    return
                
                logger.info(
                    f"Trailing stop updated for {symbol} (SHORT): "
                    f"current_stop={current_stop_loss:.2f} -> new_stop={new_stop_loss:.2f}, "
                    f"highest_in_recent={highest_price:.2f}, "
                    f"improvement={((current_stop_loss - new_stop_loss) / current_stop_loss * 100):.2f}%"
                )
            
            # Update stop loss price in position
            position['stop_loss_price'] = new_stop_loss
            
        except Exception as e:
            logger.error(f"Error updating trailing stop loss for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _calculate_dynamic_trailing_distance(self, pnl_percent: float) -> float:
        """
        Calculate dynamic trailing stop distance based on profit level
        根据利润水平动态计算移动止损距离
        
        Args:
            pnl_percent: Current profit percentage
            
        Returns:
            Dynamic trailing stop distance
        """
        try:
            if not self.dynamic_trailing_distance_enabled:
                # Use default trailing distance if dynamic is disabled
                return 0.005  # Default 0.5%
            
            # Find the appropriate trailing distance based on profit level
            trailing_distance = 0.005  # Default 0.5%
            
            for i, profit_level in enumerate(self.trailing_profit_levels):
                if pnl_percent >= profit_level:
                    trailing_distance = self.trailing_distance_levels[i]
                else:
                    break
            
            return trailing_distance
            
        except Exception as e:
            logger.error(f"Error calculating dynamic trailing distance: {e}")
            return 0.005  # Default 0.5% on error
    
    def _check_profit_drawdown_protection(self, symbol: str, current_price: float, 
                                         entry_price: float, position_side: str) -> Tuple[bool, Optional[float]]:
        """
        Check if profit drawdown protection should be triggered
        检查是否应该触发利润回撤保护
        
        Args:
            symbol: Trading pair symbol
            current_price: Current price
            entry_price: Entry price
            position_side: 'LONG' or 'SHORT'
            
        Returns:
            Tuple of (should_close, new_stop_loss_price)
        """
        try:
            if not self.profit_drawdown_protection_enabled:
                return False, None
            
            # Calculate current profit percentage
            if position_side == 'LONG':
                current_pnl_percent = (current_price - entry_price) / entry_price if entry_price > 0 else 0
            else:  # SHORT
                current_pnl_percent = (entry_price - current_price) / entry_price if entry_price > 0 else 0
            
            # Update peak profit
            if symbol not in self.position_peak_profits:
                self.position_peak_profits[symbol] = 0.0
            
            if current_pnl_percent > self.position_peak_profits[symbol]:
                self.position_peak_profits[symbol] = current_pnl_percent
                logger.info(
                    f"[PROFIT_PEAK] {symbol}: "
                    f"new_peak={current_pnl_percent*100:.2f}%, "
                    f"current_price={current_price:.2f}"
                )
            
            peak_profit = self.position_peak_profits[symbol]
            
            # Check if profit has reached the threshold for drawdown protection
            if peak_profit < self.profit_drawdown_threshold_percent:
                return False, None
            
            # Calculate drawdown from peak
            drawdown = peak_profit - current_pnl_percent
            
            # Check if drawdown exceeds maximum allowed
            if drawdown >= self.max_profit_drawdown_percent:
                logger.warning(
                    f"[PROFIT_DRAWDOWN] {symbol}: "
                    f"peak_profit={peak_profit*100:.2f}%, "
                    f"current_profit={current_pnl_percent*100:.2f}%, "
                    f"drawdown={drawdown*100:.2f}% >= {self.max_profit_drawdown_percent*100:.2f}%, "
                    f"triggering protection"
                )
                
                # Calculate new stop loss price to lock in remaining profit
                if position_side == 'LONG':
                    # For long: stop loss at current price - small buffer
                    new_stop_loss = current_price * (1 - 0.001)  # 0.1% buffer
                else:  # SHORT
                    # For short: stop loss at current price + small buffer
                    new_stop_loss = current_price * (1 + 0.001)  # 0.1% buffer
                
                return True, new_stop_loss
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking profit drawdown protection: {e}")
            return False, None
    
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
                    pass
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
                    
                    # Log exit signal
                    self._log_signal(
                        symbol=symbol,
                        direction='UP' if position_side == 'LONG' else 'DOWN',
                        current_price=current_price,
                        kline={},
                        signal_strength='MEDIUM',
                        volume_info={},
                        range_info={},
                        body_info={},
                        signal_type="EXIT_PRICE_STOP_LOSS"
                    )
                    
                    # Log trade data
                    self._log_trade(symbol, position, current_price, "Price Stop Loss")
                    
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
                
                # Check if limit order is enabled for take profit
                use_limit_order = self.limit_order_enabled and self.limit_order_take_profit_enabled
                
                if use_limit_order:
                    # Calculate limit order price for take profit
                    limit_price = self.trading_executor.calculate_take_profit_limit_price(
                        symbol=symbol,
                        side=position_side,
                        current_price=current_price,
                        offset_percent=self.limit_order_take_profit_price_offset_percent
                    )
                    
                    if limit_price:
                        logger.info(
                            f"[LIMIT_ORDER_TAKE_PROFIT] {symbol}: "
                            f"current_price={current_price:.2f}, "
                            f"limit_price={limit_price:.2f}, "
                            f"offset={((limit_price - current_price) / current_price * 100):.3f}%, "
                            f"quantity={quantity:.4f}"
                        )
                        
                        # Execute limit order for take profit
                        if position_side == 'LONG':
                            result = self.trading_executor.close_long_position_limit(
                                symbol=symbol,
                                quantity=quantity,
                                price=limit_price
                            )
                        else:  # SHORT
                            result = self.trading_executor.close_short_position_limit(
                                symbol=symbol,
                                quantity=quantity,
                                price=limit_price
                            )
                        
                        if result:
                            # Start monitoring the limit order
                            monitor_task = asyncio.create_task(
                                self.limit_order_monitor.start_monitor(
                                    symbol=symbol,
                                    order_id=result['order']['orderId'],
                                    side=position_side,
                                    order_price=limit_price,
                                    quantity=quantity,
                                    stop_loss_price=None,
                                    take_profit_percent=0,
                                    volume_info=None,
                                    range_info=None,
                                    entry_kline=None,
                                    kline_time=None,
                                    signal_strength='MEDIUM',
                                    is_take_profit=True
                                )
                            )
                            return
                        else:
                            logger.warning(f"Failed to place limit order for take profit on {symbol}, falling back to market order")
                
                # Close position for take profit (market order fallback)
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
                    
                    # Log exit signal
                    self._log_signal(
                        symbol=symbol,
                        direction='UP' if position_side == 'LONG' else 'DOWN',
                        current_price=current_price,
                        kline={},
                        signal_strength='MEDIUM',
                        volume_info={},
                        range_info={},
                        body_info={},
                        signal_type="EXIT_TAKE_PROFIT"
                    )
                    
                    # Log trade data
                    self._log_trade(symbol, position, current_price, "Take Profit")
                    
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
            
            pass

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
                    
                    # Log exit signal
                    self._log_signal(
                        symbol=symbol,
                        direction='UP' if position_side == 'LONG' else 'DOWN',
                        current_price=current_price,
                        kline={},
                        signal_strength='MEDIUM',
                        volume_info={},
                        range_info={},
                        body_info={},
                        signal_type="EXIT_TIME_STOP_LOSS"
                    )
                    
                    # Log trade data
                    self._log_trade(symbol, position, current_price, "Time Stop Loss")
                    
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
                else:
                    logger.error(f"Failed to close position due to time stop loss for {symbol}")
            else:
                pass
                
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
    
    def _log_trade(self, symbol: str, position: Dict, exit_price: float, close_reason: str) -> None:
        """
        Log trade data to CSV file
        
        Args:
            symbol: Trading pair symbol
            position: Position information
            exit_price: Exit price
            close_reason: Reason for closing position
        """
        try:
            entry_price = position.get('entry_price', 0)
            quantity = position.get('quantity', 0)
            side = position.get('side', 'UNKNOWN')
            
            # Calculate PnL
            pnl = 0.0
            if exit_price and entry_price > 0:
                if side == 'LONG':
                    pnl = (exit_price - entry_price) * quantity
                else:  # SHORT
                    pnl = (entry_price - exit_price) * quantity
            
            # Calculate PnL percentage
            pnl_percent = 0.0
            if entry_price > 0 and quantity > 0:
                pnl_percent = (pnl / (entry_price * quantity)) * 100
            
            # Calculate holding time
            entry_time = position.get('entry_time', 0)
            holding_time_minutes = 0
            if entry_time > 0:
                import time
                current_time = int(time.time() * 1000)
                holding_time_minutes = (current_time - entry_time) / 60000  # Convert to minutes
            
            # Log trade
            self.trade_logger.log_trade({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'holding_time_minutes': holding_time_minutes,
                'entry_time': datetime.fromtimestamp(entry_time / 1000).isoformat() if entry_time > 0 else datetime.now().isoformat(),
                'exit_time': datetime.now().isoformat(),
                'close_reason': close_reason,
                'signal_strength': 'MEDIUM',
                'stop_loss_price': 0,
                'take_profit_percent': 0,
                'volume_ratio': 0,
                'body_ratio': 0,
                'range_ratio': 0,
                'rsi': 0,
                'macd': 0,
                'adx': 0,
                'market_type': 'UNKNOWN',
                'trend_strength': 'SIDEWAYS',
                'position_ratio': 0,
                'leverage': 0
            })
            
        except Exception as e:
            logger.error(f"Error logging trade for {symbol}: {e}")
    
    
    def _log_signal(self, symbol: str, direction: str, current_price: float, kline: Dict,
                    signal_strength: str, volume_info: Dict, range_info: Dict, body_info: Dict,
                    trend_info: Optional[Dict] = None, rsi_info: Optional[Dict] = None,
                    macd_info: Optional[Dict] = None, adx_info: Optional[Dict] = None,
                    market_env_info: Optional[Dict] = None, multi_timeframe_info: Optional[Dict] = None,
                    sentiment_info: Optional[Dict] = None, ml_info: Optional[Dict] = None,
                    signal_type: str = "ENTRY") -> None:
        """
        Log trading signal data for analysis (works even without real trading)
        
        Args:
            symbol: Trading pair symbol
            direction: 'UP' or 'DOWN'
            current_price: Current price
            kline: K-line data
            signal_strength: Signal strength (STRONG/MEDIUM/WEAK)
            volume_info: Volume information
            range_info: Range information
            body_info: Body information
            trend_info: Trend information (optional)
            rsi_info: RSI information (optional)
            macd_info: MACD information (optional)
            adx_info: ADX information (optional)
            market_env_info: Market environment information (optional)
            multi_timeframe_info: Multi-timeframe information (optional)
            sentiment_info: Sentiment information (optional)
            ml_info: ML information (optional)
            signal_type: Signal type (ENTRY/EXIT)
        """
        try:
            # Extract indicator values
            rsi_value = rsi_info.get('rsi_value', 0) if rsi_info else 0
            adx_value = adx_info.get('adx_value', 0) if adx_info else 0
            macd_value = macd_info.get('macd_value', 0) if macd_info else 0
            macd_signal_value = macd_info.get('signal_value', 0) if macd_info else 0
            macd_hist_value = macd_info.get('histogram', 0) if macd_info else 0
            
            # Calculate ATR
            atr_value = 0
            try:
                all_klines = self.data_handler.get_klines(symbol, "5m")
                if all_klines:
                    closed_klines = [k for k in all_klines if k.get('is_closed', False)]
                    if len(closed_klines) >= self.atr_period + 1:
                        df = pd.DataFrame(closed_klines)
                        atr_series = self.technical_analyzer.calculate_atr(df, period=self.atr_period)
                        if atr_series is not None and len(atr_series) > 0:
                            atr_value = atr_series.iloc[-1]
            except:
                pass
            
            # Extract other values
            volume_ratio = volume_info.get('ratio_5', 0) if volume_info else 0
            body_ratio = body_info.get('body_ratio', 0) if body_info else 0
            shadow_ratio = max(body_info.get('upper_shadow_ratio', 0), body_info.get('lower_shadow_ratio', 0)) if body_info else 0
            
            # Calculate EMAs
            ema_20 = 0
            ema_50 = 0
            ema_200 = 0
            try:
                all_klines = self.data_handler.get_klines(symbol, "5m")
                if all_klines:
                    closed_klines = [k for k in all_klines if k.get('is_closed', False)]
                    if len(closed_klines) >= 200:
                        df = pd.DataFrame(closed_klines)
                        ema_20 = self.technical_analyzer.calculate_ma(df['close'], 20).iloc[-1] if len(self.technical_analyzer.calculate_ma(df['close'], 20)) > 0 else 0
                        ema_50 = self.technical_analyzer.calculate_ma(df['close'], 50).iloc[-1] if len(self.technical_analyzer.calculate_ma(df['close'], 50)) > 0 else 0
                        ema_200 = self.technical_analyzer.calculate_ma(df['close'], 200).iloc[-1] if len(self.technical_analyzer.calculate_ma(df['close'], 200)) > 0 else 0
            except:
                pass
            
            # Determine trend
            higher_trend = 'SIDEWAYS'
            if ema_20 > ema_50 > ema_200:
                higher_trend = 'UP'
            elif ema_20 < ema_50 < ema_200:
                higher_trend = 'DOWN'
            
            # Market environment
            market_type = market_env_info.get('market_type', 'UNKNOWN') if market_env_info else 'UNKNOWN'
            
            # Sentiment
            sentiment_score = sentiment_info.get('fear_greed_value', 50) if sentiment_info else 50
            sentiment_label = sentiment_info.get('fear_greed_classification', 'NEUTRAL') if sentiment_info else 'NEUTRAL'
            
            # ML prediction
            ml_prediction = ml_info.get('prediction', 'NEUTRAL') if ml_info else 'NEUTRAL'
            ml_confidence = ml_info.get('confidence', 0) if ml_info else 0
            
            # Log signal
            self.trade_logger.log_trade({
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'side': 'LONG' if direction == 'UP' else 'SHORT',
                'entry_price': current_price,
                'exit_price': current_price,
                'quantity': 0,
                'pnl': 0,
                'pnl_percent': 0,
                'holding_time_minutes': 0,
                'entry_time': datetime.now().isoformat(),
                'exit_time': datetime.now().isoformat(),
                'close_reason': signal_type,
                'signal_strength': signal_strength,
                'stop_loss_price': 0,
                'take_profit_percent': 0,
                'volume_ratio': volume_ratio,
                'body_ratio': body_ratio,
                'range_ratio': 0,
                'rsi': rsi_value,
                'macd': macd_value,
                'adx': adx_value,
                'market_type': market_type,
                'trend_strength': higher_trend,
                'position_ratio': 0,
                'leverage': 0
            })
            
        except Exception as e:
            logger.error(f"Error logging signal for {symbol}: {e}")
    
    def _get_current_price_for_monitor(self, symbol: str) -> Optional[float]:
        """
        Get current price for limit order monitor
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current price or None
        """
        try:
            return self.data_handler.get_current_price(symbol)
        except Exception as e:
            logger.error(f"Error getting current price for monitor: {e}")
            return None
    
    async def _open_long_position_with_limit_order(self, symbol: str, volume_info: Optional[Dict] = None,
                                                   range_info: Optional[Dict] = None, stop_loss_price: Optional[float] = None,
                                                   entry_kline: Optional[Dict] = None, kline_time: Optional[int] = None,
                                                   signal_strength: str = 'MEDIUM', take_profit_percent: float = 0.05) -> None:
        """
        Open a long position using limit order
        
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
                calculated_stop_loss_distance = current_price - stop_loss_price
                min_stop_loss_distance = current_price * self.stop_loss_min_distance_percent
                actual_stop_loss_distance = max(calculated_stop_loss_distance, min_stop_loss_distance)
                max_stop_loss_distance = current_price * self.stop_loss_max_distance_percent
                actual_stop_loss_distance = min(actual_stop_loss_distance, max_stop_loss_distance)
                stop_loss_distance_percent = actual_stop_loss_distance / current_price
                
                if actual_stop_loss_distance != calculated_stop_loss_distance:
                    stop_loss_price = current_price - actual_stop_loss_distance
            
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
            quantity = adjusted_quantity
            
            # Check if there are pending orders and cancel if configured
            if self.limit_order_cancel_on_new_signal and symbol in self.pending_limit_orders:
                await self._check_and_cancel_pending_orders(
                    symbol,
                    "检测到新信号，取消旧限价单"
                )
            
            # Check max pending orders
            if symbol in self.pending_limit_orders and len(self.pending_limit_orders[symbol]) >= self.limit_order_max_pending_orders:
                logger.warning(f"Max pending orders reached for {symbol}, cancelling oldest order")
                oldest_order_id = next(iter(self.pending_limit_orders[symbol]))
                await self._convert_limit_to_market(
                    symbol,
                    oldest_order_id,
                    self.pending_limit_orders[symbol][oldest_order_id],
                    "达到最大挂单数量"
                )
            
            # Calculate limit order price
            limit_price = self.trading_executor.calculate_entry_limit_price(
                symbol=symbol,
                current_price=current_price,
                side='LONG'
            )
            
            if limit_price is None:
                logger.warning(f"Could not calculate limit price for {symbol}, falling back to market order")
                await self._open_long_position(symbol, volume_info, range_info, stop_loss_price, entry_kline,
                                               kline_time, signal_strength, take_profit_percent)
                return
            
            logger.info(
                f"[LIMIT_ORDER] {symbol}: "
                f"current_price={current_price:.2f}, "
                f"limit_price={limit_price:.2f}, "
                f"offset={((limit_price - current_price) / current_price * 100):.3f}%, "
                f"quantity={quantity:.4f}"
            )
            
            # Execute limit order
            result = self.trading_executor.open_long_position_limit(
                symbol=symbol,
                quantity=quantity,
                price=limit_price
            )
            
            if result:
                order = result.get('order')
                final_quantity = result.get('final_quantity', quantity)
                final_price = result.get('final_price', limit_price)
                
                # Record pending order
                import time
                if symbol not in self.pending_limit_orders:
                    self.pending_limit_orders[symbol] = {}
                
                order_info = {
                    'side': 'LONG',
                    'order_price': limit_price,
                    'original_quantity': final_quantity,      # 原始数量
                    'filled_quantity': 0,                     # 已成交数量
                    'remaining_quantity': final_quantity,     # 剩余数量
                    'avg_fill_price': 0,                      # 平均成交价
                    'partial_fills': [],                      # 部分成交记录
                    'timestamp': time.time(),
                    'stop_loss_price': stop_loss_price,
                    'take_profit_percent': take_profit_percent,
                    'volume_info': volume_info,
                    'range_info': range_info,
                    'entry_kline': entry_kline,
                    'kline_time': kline_time,
                    'signal_strength': signal_strength
                }
                
                self.pending_limit_orders[symbol][order['orderId']] = order_info
                
                # Save to persistence
                self.order_persistence.save_order(order['orderId'], symbol, order_info)
                
                # Start monitoring the limit order
                monitor_task = asyncio.create_task(
                    self.limit_order_monitor.start_monitor(
                        symbol=symbol,
                        order_id=order['orderId'],
                        side='LONG',
                        order_price=limit_price,
                        quantity=final_quantity,
                        stop_loss_price=stop_loss_price,
                        take_profit_percent=take_profit_percent,
                        volume_info=volume_info,
                        range_info=range_info,
                        entry_kline=entry_kline,
                        kline_time=kline_time,
                        signal_strength=signal_strength
                    )
                )
            else:
                logger.error(f"Failed to place limit order for {symbol}, falling back to market order")
                await self._open_long_position(symbol, volume_info, range_info, stop_loss_price, entry_kline,
                                               kline_time, signal_strength, take_profit_percent)
                
        except Exception as e:
            logger.error(f"Error opening long position with limit order for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _open_short_position_with_limit_order(self, symbol: str, volume_info: Optional[Dict] = None,
                                                    range_info: Optional[Dict] = None, stop_loss_price: Optional[float] = None,
                                                    entry_kline: Optional[Dict] = None, kline_time: Optional[int] = None,
                                                    signal_strength: str = 'MEDIUM', take_profit_percent: float = 0.05) -> None:
        """
        Open a short position using limit order
        
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
                calculated_stop_loss_distance = stop_loss_price - current_price
                min_stop_loss_distance = current_price * self.stop_loss_min_distance_percent
                actual_stop_loss_distance = max(calculated_stop_loss_distance, min_stop_loss_distance)
                max_stop_loss_distance = current_price * self.stop_loss_max_distance_percent
                actual_stop_loss_distance = min(actual_stop_loss_distance, max_stop_loss_distance)
                stop_loss_distance_percent = actual_stop_loss_distance / current_price
                
                if actual_stop_loss_distance != calculated_stop_loss_distance:
                    stop_loss_price = current_price + actual_stop_loss_distance
            
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
            quantity = adjusted_quantity
            
            # Check if there are pending orders and cancel if configured
            if self.limit_order_cancel_on_new_signal and symbol in self.pending_limit_orders:
                await self._check_and_cancel_pending_orders(
                    symbol,
                    "检测到新信号，取消旧限价单"
                )
            
            # Check max pending orders
            if symbol in self.pending_limit_orders and len(self.pending_limit_orders[symbol]) >= self.limit_order_max_pending_orders:
                logger.warning(f"Max pending orders reached for {symbol}, cancelling oldest order")
                oldest_order_id = next(iter(self.pending_limit_orders[symbol]))
                await self._convert_limit_to_market(
                    symbol,
                    oldest_order_id,
                    self.pending_limit_orders[symbol][oldest_order_id],
                    "达到最大挂单数量"
                )
            
            # Calculate limit order price
            limit_price = self.trading_executor.calculate_entry_limit_price(
                symbol=symbol,
                current_price=current_price,
                side='SHORT'
            )
            
            if limit_price is None:
                logger.warning(f"Could not calculate limit price for {symbol}, falling back to market order")
                await self._open_short_position(symbol, volume_info, range_info, stop_loss_price, entry_kline,
                                                kline_time, signal_strength, take_profit_percent)
                return
            
            logger.info(
                f"[LIMIT_ORDER] {symbol}: "
                f"current_price={current_price:.2f}, "
                f"limit_price={limit_price:.2f}, "
                f"offset={((limit_price - current_price) / current_price * 100):.3f}%, "
                f"quantity={quantity:.4f}"
            )
            
            # Execute limit order
            result = self.trading_executor.open_short_position_limit(
                symbol=symbol,
                quantity=quantity,
                price=limit_price
            )
            
            if result:
                order = result.get('order')
                final_quantity = result.get('final_quantity', quantity)
                final_price = result.get('final_price', limit_price)
                
                # Record pending order
                import time
                if symbol not in self.pending_limit_orders:
                    self.pending_limit_orders[symbol] = {}
                
                order_info = {
                    'side': 'SHORT',
                    'order_price': limit_price,
                    'original_quantity': final_quantity,      # 原始数量
                    'filled_quantity': 0,                     # 已成交数量
                    'remaining_quantity': final_quantity,     # 剩余数量
                    'avg_fill_price': 0,                      # 平均成交价
                    'partial_fills': [],                      # 部分成交记录
                    'timestamp': time.time(),
                    'stop_loss_price': stop_loss_price,
                    'take_profit_percent': take_profit_percent,
                    'volume_info': volume_info,
                    'range_info': range_info,
                    'entry_kline': entry_kline,
                    'kline_time': kline_time,
                    'signal_strength': signal_strength
                }
                
                self.pending_limit_orders[symbol][order['orderId']] = order_info
                
                # Save to persistence
                self.order_persistence.save_order(order['orderId'], symbol, order_info)
                
                # Start monitoring the limit order
                monitor_task = asyncio.create_task(
                    self.limit_order_monitor.start_monitor(
                        symbol=symbol,
                        order_id=order['orderId'],
                        side='SHORT',
                        order_price=limit_price,
                        quantity=final_quantity,
                        stop_loss_price=stop_loss_price,
                        take_profit_percent=take_profit_percent,
                        volume_info=volume_info,
                        range_info=range_info,
                        entry_kline=entry_kline,
                        kline_time=kline_time,
                        signal_strength=signal_strength
                    )
                )
            else:
                logger.error(f"Failed to place limit order for {symbol}, falling back to market order")
                await self._open_short_position(symbol, volume_info, range_info, stop_loss_price, entry_kline,
                                                kline_time, signal_strength, take_profit_percent)
                
        except Exception as e:
            logger.error(f"Error opening short position with limit order for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def emergency_close_position(self, symbol: str, reason: str) -> bool:
        """
        Emergency close position - uses market order immediately
        This is used when limit order monitoring detects critical conditions
        
        Args:
            symbol: Trading pair symbol
            reason: Reason for emergency close
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.warning(f"[EMERGENCY_CLOSE] {symbol}: {reason}")
            
            # Get position information
            position = self.position_manager.get_position(symbol)
            if not position:
                logger.warning(f"No position found for {symbol}")
                return False
            
            position_side = position['side']
            quantity = position['quantity']
            entry_price = position.get('entry_price', 0)
            
            # Cancel all pending orders for this symbol
            import asyncio
            await asyncio.to_thread(self.trading_executor.cancel_all_orders, symbol)
            
            # Close position with market order
            success = await self.trading_executor.close_all_positions(symbol)
            
            if success:
                current_price = self.data_handler.get_current_price(symbol)
                
                # Calculate PnL
                pnl = 0.0
                if current_price and entry_price > 0:
                    if position_side == 'LONG':
                        pnl = (current_price - entry_price) * quantity
                    else:  # SHORT
                        pnl = (entry_price - current_price) * quantity
                
                # Send emergency close notification
                await self.telegram_client.send_message(
                    f"🚨 紧急平仓\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {position_side}\n"
                    f"原因: {reason}\n"
                    f"当前价格: ${f'{current_price:.2f}' if current_price else 'N/A'}\n"
                    f"开仓价格: ${entry_price:.2f}\n"
                    f"盈亏: ${pnl:.2f}"
                )
                
                # Update trade result for drawdown protection
                self._update_trade_result(pnl)
                
                # Log trade data
                self._log_trade(symbol, position, current_price if current_price else 0, f"Emergency Close: {reason}")
                
                # Clear local position state
                self.position_manager.close_position(symbol, current_price if current_price else 0)
                
                # Clear tracking state
                if symbol in self.position_peak_prices:
                    del self.position_peak_prices[symbol]
                if symbol in self.position_entry_times:
                    del self.position_entry_times[symbol]
                if symbol in self.partial_take_profit_status:
                    del self.partial_take_profit_status[symbol]
                if symbol in self.stop_loss_first_trigger_time:
                    del self.stop_loss_first_trigger_time[symbol]
                
                return True
            else:
                logger.error(f"Failed to emergency close position for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error in emergency close for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _check_and_cancel_pending_orders(self, symbol: str, reason: str) -> None:
        """
        Check and cancel pending limit orders for a symbol
        
        Args:
            symbol: Trading pair symbol
            reason: Reason for cancellation
        """
        try:
            if symbol not in self.pending_limit_orders:
                return
            
            pending_orders = self.pending_limit_orders[symbol]
            if not pending_orders:
                return
            
            pass
            
            # Cancel all pending orders
            import asyncio
            await asyncio.to_thread(self.trading_executor.cancel_all_orders, symbol)
            
            # Send notification
            await self.telegram_client.send_message(
                f"🚫 取消限价单\n\n"
                f"交易对: {symbol}\n"
                f"原因: {reason}\n"
                f"取消订单数: {len(pending_orders)}"
            )
            
            # Clear pending orders
            del self.pending_limit_orders[symbol]
            
        except Exception as e:
            logger.error(f"Error canceling pending orders for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _check_signal_reversal(self, symbol: str, current_kline: Dict) -> None:
        """
        Check if signal has reversed and handle pending orders accordingly
        
        Args:
            symbol: Trading pair symbol
            current_kline: Current K-line data
        """
        try:
            # Check if there are pending orders
            if symbol not in self.pending_limit_orders:
                return
            
            pending_orders = self.pending_limit_orders[symbol]
            if not pending_orders:
                return
            
            # Get current K-line direction
            current_direction = self.technical_analyzer.get_kline_direction(current_kline)
            if current_direction is None:
                return
            
            # Check each pending order
            for order_id, order_info in pending_orders.items():
                order_side = order_info.get('side')
                
                # Check if signal has reversed
                signal_reversed = False
                if order_side == 'LONG' and current_direction == 'DOWN':
                    signal_reversed = True
                elif order_side == 'SHORT' and current_direction == 'UP':
                    signal_reversed = True
                
                if signal_reversed:
                    logger.warning(
                        f"[SIGNAL_REVERSAL] {symbol}: "
                        f"Order side={order_side}, current direction={current_direction}, "
                        f"signal reversed"
                    )
                    
                    # Handle based on configuration
                    if self.limit_order_action_on_signal_reversal == "cancel":
                        await self._check_and_cancel_pending_orders(
                            symbol, 
                            f"信号反转: {order_side} -> {current_direction}"
                        )
                    elif self.limit_order_action_on_signal_reversal == "convert_to_market":
                        # Convert to market order
                        await self._convert_limit_to_market(symbol, order_id, order_info, "信号反转")
                    
                    break  # Only need to check one order
                    
        except Exception as e:
            logger.error(f"Error checking signal reversal for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _convert_limit_to_market(self, symbol: str, order_id: int, order_info: Dict, reason: str) -> bool:
        """
        Convert a limit order to market order
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to convert
            order_info: Order information
            reason: Reason for conversion
            
        Returns:
            True if successful, False otherwise
        """
        try:
            pass
            
            # Cancel the limit order
            import asyncio
            cancel_result = await asyncio.to_thread(
                self.trading_executor.cancel_order,
                symbol,
                order_id
            )
            
            if not cancel_result:
                logger.error(f"Failed to cancel limit order {order_id} for {symbol}")
                return False
            
            # Execute market order
            side = order_info.get('side')
            quantity = order_info.get('quantity')
            
            if side == 'LONG':
                result = self.trading_executor.open_long_position(symbol, quantity)
            else:  # SHORT
                result = self.trading_executor.open_short_position(symbol, quantity)
            
            if result:
                # Remove from pending orders
                if symbol in self.pending_limit_orders and order_id in self.pending_limit_orders[symbol]:
                    del self.pending_limit_orders[symbol][order_id]
                
                # Send notification
                await self.telegram_client.send_message(
                    f"🔄 限价单转市价单\n\n"
                    f"交易对: {symbol}\n"
                    f"方向: {side}\n"
                    f"原因: {reason}\n"
                    f"数量: {quantity:.4f}"
                )
                
                pass
                return True
            else:
                logger.error(f"Failed to execute market order for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error converting limit order to market for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def _sync_orders_with_exchange(self):
        """与交易所同步订单状态和持仓状态"""
        try:
            # 首先同步持仓状态
            await self._sync_positions_with_exchange()
            
            # 然后同步订单状态
            for symbol in list(self.pending_limit_orders.keys()):
                try:
                    # 获取交易所的未完成订单
                    open_orders = await asyncio.to_thread(
                        self.trading_executor.get_open_orders,
                        symbol
                    )
                    
                    if open_orders is None:
                        logger.warning(f"Failed to get open orders for {symbol}")
                        continue
                    
                    exchange_order_ids = {order['orderId'] for order in open_orders}
                    local_order_ids = set(self.pending_limit_orders[symbol].keys())
                    
                    # 处理本地有但交易所没有的订单（可能已成交或取消）
                    for order_id in local_order_ids - exchange_order_ids:
                        pass
                        
                        # 尝试获取订单状态
                        order_status = await asyncio.to_thread(
                            self.trading_executor.get_order_status,
                            symbol,
                            order_id
                        )
                        
                        if order_status == 'FILLED':
                            self.order_persistence.update_order_status(order_id, 'FILLED')
                            del self.pending_limit_orders[symbol][order_id]
                        elif order_status == 'CANCELED':
                            self.order_persistence.update_order_status(order_id, 'CANCELLED')
                            del self.pending_limit_orders[symbol][order_id]
                        else:
                            logger.warning(f"Order {order_id} status unknown: {order_status}, removing from tracking")
                            self.order_persistence.update_order_status(order_id, 'UNKNOWN')
                            del self.pending_limit_orders[symbol][order_id]
                    
                    # 处理交易所有但本地没有的订单（程序重启前创建的）
                    for order_id in exchange_order_ids - local_order_ids:
                        pass
                        
                        # 从交易所获取订单详情
                        order_detail = await asyncio.to_thread(
                            self.trading_executor.get_order,
                            symbol,
                            order_id
                        )
                        
                        if order_detail:
                            self._add_order_to_tracking(symbol, order_detail)
                    
                    pass
                    
                except Exception as e:
                    logger.error(f"Error syncing orders for {symbol}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            pass
            
        except Exception as e:
            logger.error(f"Error in order synchronization: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _sync_positions_with_exchange(self):
        """与交易所同步持仓状态，初始化跟踪数据"""
        try:
            import time
            
            # 获取所有配置的交易对
            symbols = self.config.binance_symbols
            
            for symbol in symbols:
                try:
                    # 从交易所获取持仓信息
                    position = await asyncio.to_thread(
                        self.trading_executor.get_position,
                        symbol
                    )
                    
                    if position is None:
                        # 没有持仓，跳过
                        continue
                    
                    position_amt = float(position.get('positionAmt', 0))
                    
                    if position_amt == 0:
                        # 持仓数量为0，跳过
                        continue
                    
                    # 有持仓，检查本地是否已有跟踪数据
                    if symbol not in self.position_entry_times:
                        # 初始化持仓入场时间
                        # 使用当前时间作为默认值（因为无法从交易所获取准确的入场时间）
                        self.position_entry_times[symbol] = int(time.time() * 1000)
                        logger.info(f"Initialized entry time for existing position {symbol}")
                    
                    if symbol not in self.partial_take_profit_status:
                        # 初始化分批止盈状态
                        self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
                        logger.info(f"Initialized partial take profit status for existing position {symbol}")
                    
                    if symbol not in self.position_peak_prices:
                        # 初始化峰值价格跟踪
                        current_price = self.data_handler.get_current_price(symbol)
                        if current_price:
                            self.position_peak_prices[symbol] = current_price
                            logger.info(f"Initialized peak price for existing position {symbol}: {current_price}")
                    
                    # 确保position_manager中也有这个持仓
                    if not self.position_manager.has_position(symbol):
                        # 从交易所数据重建持仓信息
                        entry_price = float(position.get('entryPrice', 0))
                        quantity = abs(position_amt)
                        side = 'LONG' if position_amt > 0 else 'SHORT'
                        
                        self.position_manager.open_position(
                            symbol=symbol,
                            side=side,
                            entry_price=entry_price,
                            quantity=quantity,
                            entry_kline=None
                        )
                        logger.info(f"Reconstructed position {symbol} from exchange: {side} {quantity} @ {entry_price}")
                    
                except Exception as e:
                    logger.error(f"Error syncing position for {symbol}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info("Position synchronization completed")
            
        except Exception as e:
            logger.error(f"Error in position synchronization: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _add_order_to_tracking(self, symbol: str, order_detail: Dict):
        """添加订单到跟踪"""
        try:
            order_id = order_detail['orderId']
            
            # 构建订单信息
            order_info = {
                'side': 'LONG' if order_detail['side'] == 'BUY' else 'SHORT',
                'order_price': float(order_detail['price']),
                'quantity': float(order_detail['origQty']),
                'timestamp': order_detail['time'] / 1000,  # 转换为秒
                'stop_loss_price': None,
                'take_profit_percent': 0.05,
                'volume_info': {},
                'range_info': {},
                'entry_kline': None,
                'kline_time': None,
                'signal_strength': 'MEDIUM'
            }
            
            # 添加到跟踪
            if symbol not in self.pending_limit_orders:
                self.pending_limit_orders[symbol] = {}
            
            self.pending_limit_orders[symbol][order_id] = order_info
            
            # 保存到持久化
            self.order_persistence.save_order(order_id, symbol, order_info)
            
            pass
            
        except Exception as e:
            logger.error(f"Error adding order to tracking: {e}")
    
    async def handle_partial_fill(self, symbol: str, order_id: int, fill_info: Dict):
        """
        处理部分成交
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            fill_info: 成交信息
        """
        try:
            if symbol not in self.pending_limit_orders:
                logger.warning(f"Symbol {symbol} not in pending orders")
                return
            
            if order_id not in self.pending_limit_orders[symbol]:
                logger.warning(f"Order {order_id} not found in pending orders for {symbol}")
                return
            
            order = self.pending_limit_orders[symbol][order_id]
            fill_qty = float(fill_info['executedQty'])
            fill_price = float(fill_info['price'])
            
            # 更新成交信息
            order['filled_quantity'] += fill_qty
            order['remaining_quantity'] -= fill_qty
            
            # 计算平均成交价
            if order['filled_quantity'] > 0:
                total_value = order['avg_fill_price'] * (order['filled_quantity'] - fill_qty)
                total_value += fill_price * fill_qty
                order['avg_fill_price'] = total_value / order['filled_quantity']
            
            # 记录部分成交
            order['partial_fills'].append({
                'quantity': fill_qty,
                'price': fill_price,
                'time': datetime.now().isoformat()
            })
            
            # 更新持久化
            self.order_persistence.save_order(order_id, symbol, order)
            
            # 发送部分成交通知
            await self.telegram_client.send_message(
                f"📊 部分成交\n\n"
                f"交易对: {symbol}\n"
                f"订单ID: {order_id}\n"
                f"成交数量: {fill_qty:.4f}\n"
                f"成交价格: ${fill_price:.2f}\n"
                f"已成交: {order['filled_quantity']:.4f}\n"
                f"剩余: {order['remaining_quantity']:.4f}\n"
                f"平均价: ${order['avg_fill_price']:.2f}"
            )
            
            pass
            
            # 如果完全成交，处理持仓
            if order['remaining_quantity'] <= 0.0001:  # 考虑精度
                await self.on_order_fully_filled(symbol, order_id)
                
        except Exception as e:
            logger.error(f"Error handling partial fill: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def on_order_fully_filled(self, symbol: str, order_id: int):
        """
        订单完全成交时的处理
        
        Args:
            symbol: 交易对
            order_id: 订单ID
        """
        try:
            order = self.pending_limit_orders[symbol][order_id]
            
            # 更新订单状态
            self.order_persistence.update_order_status(order_id, 'FILLED')
            
            # 创建持仓
            self.position_manager.open_position(
                symbol=symbol,
                side=order['side'],
                entry_price=order['avg_fill_price'],
                quantity=order['filled_quantity'],
                entry_kline=order.get('entry_kline')
            )
            
            # 设置止损
            position = self.position_manager.get_position(symbol)
            if position and order.get('stop_loss_price'):
                position['stop_loss_price'] = order['stop_loss_price']
            
            # 初始化跟踪
            self.position_peak_prices[symbol] = order['avg_fill_price']
            self.position_entry_times[symbol] = order.get('kline_time', int(time.time() * 1000))
            self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
            
            # 发送成交通知
            await self.telegram_client.send_trade_notification(
                symbol=symbol,
                side=order['side'],
                price=order['avg_fill_price'],
                quantity=order['filled_quantity'],
                leverage=self.config.leverage,
                volume_info=order.get('volume_info'),
                range_info=order.get('range_info'),
                stop_loss_price=order.get('stop_loss_price'),
                position_calc_info=None,
                kline_time=order.get('kline_time')
            )
            
            # 清理订单跟踪
            del self.pending_limit_orders[symbol][order_id]
            
            pass
            
        except Exception as e:
            logger.error(f"Error handling fully filled order: {e}")
            import traceback
            logger.error(traceback.format_exc())