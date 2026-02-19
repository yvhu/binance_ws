"""
Trading Executor
Executes trading operations on Binance Futures
"""

import logging
from typing import Optional, Dict
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

from ..config.config_manager import ConfigManager
from ..utils.retry_decorator import async_retry, sync_retry, should_retry_exception, log_retry_attempt
from .order_risk_control import OrderRiskControl

logger = logging.getLogger(__name__)


class TradingExecutor:
    """Executor for trading operations on Binance Futures"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize trading executor
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        
        # Initialize Binance client
        self.client = Client(
            config.binance_api_key,
            config.binance_api_secret,
            testnet=False  # Set to True for testnet
        )
        
        self.leverage = config.leverage
        
        # Risk management configuration
        self.max_loss_per_trade_percent = config.get_config(
            "trading",
            "max_loss_per_trade_percent",
            default=0.30
        )  # 30% maximum loss per trade
        
        # Trading configuration
        self.fee_rate = config.get_config("trading", "fee_rate", default=0.0004)  # 0.04% for market orders
        self.safety_margin = config.get_config("trading", "safety_margin", default=0.01)  # 1% safety margin
        
        # Cache for leverage settings
        self.leverage_cache = set()  # Track symbols with leverage already set
        
        
        # Initialize leverage for all configured symbols
        # 延迟杠杆初始化，等待WebSocket连接后再执行
        self._cleanup_stale_orders()
        
        # 标记杠杆初始化状态
        self.leverage_initialized = False
        
        # 初始化订单风险控制
        self.risk_control = OrderRiskControl(config)
    
    def _initialize_leverage(self) -> None:
        """Initialize leverage for all configured symbols"""
        symbols = self.config.binance_symbols
        
        for symbol in symbols:
            try:
                import time
                
                # Cancel all open orders before setting leverage
                # This prevents "Position side cannot be changed if there exists open orders" error
                self.cancel_all_orders(symbol)
                
                # Wait for cancellations to be processed
                time.sleep(1)
                
                # Verify all orders are cancelled before setting leverage
                # Retry up to 3 times to ensure all orders are cancelled
                max_retries = 3
                for attempt in range(max_retries):
                    orders = self.get_open_orders(symbol)
                    
                    total_orders = len(orders) if orders else 0
                    
                    if total_orders == 0:
                        break
                    
                    logger.warning(
                        f"Found {total_orders} open order(s) for {symbol} after cancellation attempt {attempt + 1}/{max_retries}. "
                        f"Retrying cancellation..."
                    )
                    
                    # Log remaining orders for debugging
                    if orders:
                        logger.warning(f"Remaining open orders for {symbol}:")
                        for i, order in enumerate(orders, 1):
                            logger.warning(f"  {i}. Order: orderId={order.get('orderId')}, type={order.get('type')}, side={order.get('side')}, status={order.get('status')}")
                    
                    # Retry cancellation
                    self.cancel_all_orders(symbol)
                    time.sleep(1)
                    
                    # If this was the last retry and orders still exist, skip this symbol
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed to cancel all orders for {symbol} after {max_retries} attempts. "
                            f"Remaining: {total_orders} open orders. Cannot set leverage."
                        )
                        continue
                
                # Only set leverage if all orders are cancelled
                orders = self.get_open_orders(symbol)
                total_orders = len(orders) if orders else 0
                
                if total_orders > 0:
                    logger.error(
                        f"Skipping leverage setup for {symbol} due to remaining orders: "
                        f"{total_orders} open orders"
                    )
                    continue
                
                success = self.set_leverage(symbol)
                if success:
                    self.leverage_cache.add(symbol)
                else:
                    logger.error(f"✗ Failed to set leverage for {symbol}")
            except Exception as e:
                logger.error(f"✗ Exception while setting leverage for {symbol}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
    
    def _cleanup_stale_orders(self) -> None:
        """Cancel all open orders on startup to clean up any stale orders"""
        symbols = self.config.binance_symbols
        
        
        for symbol in symbols:
            try:
                orders = self.get_open_orders(symbol)
                if orders:
                    logger.warning(f"Found {len(orders)} stale order(s) for {symbol}, cancelling...")
                    success = self.cancel_all_orders(symbol)
                    if not success:
                        logger.error(f"✗ Failed to clean up stale orders for {symbol}")
            except Exception as e:
                logger.error(f"Error cleaning up stale orders for {symbol}: {e}")
        
    
    def set_margin_type(self, symbol: str, margin_type: str = 'CROSSED') -> bool:
        """
        Set margin type for a symbol (must be set before leverage)
        
        Args:
            symbol: Trading pair symbol
            margin_type: 'CROSSED' (全仓) or 'ISOLATED' (逐仓)
            
        Returns:
            True if successful
        """
        try:
            self.client.futures_change_margin_type(
                marginType=margin_type,
                symbol=symbol
            )
            return True
        except BinanceAPIException as e:
            # If margin type is already set, it's not an error
            if 'No need to change margin type' in str(e):
                logger.debug(f"Margin type already set for {symbol}")
                return True
            logger.error(f"Failed to set margin type for {symbol}: {e}")
            return False
    
    def set_leverage(self, symbol: str) -> bool:
        """
        Set leverage for a symbol (must set margin type first)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        try:
            # Set margin type first (required by Binance API)
            if not self.set_margin_type(symbol, margin_type='CROSSED'):
                logger.error(f"Failed to set margin type for {symbol}")
                return False
            
            # Then set leverage
            self.client.futures_change_leverage(
                leverage=self.leverage,
                symbol=symbol
            )
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False
    
    def ensure_leverage(self, symbol: str) -> bool:
        """
        Ensure leverage is set for a symbol (only sets if not already cached)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if leverage is set or already cached
        """
        if symbol in self.leverage_cache:
            logger.debug(f"Leverage already set for {symbol}, skipping")
            return True
        
        success = self.set_leverage(symbol)
        if success:
            self.leverage_cache.add(symbol)
        
        return success
    
    def get_listen_key(self) -> Optional[str]:
        """
        Get listen key for user data stream
        
        Returns:
            Listen key or None
        """
        try:
            # futures_stream_get_listen_key returns the listen key string directly
            listen_key = self.client.futures_stream_get_listen_key()
            return listen_key
        except BinanceAPIException as e:
            logger.error(f"Failed to get listen key: {e}")
            return None
    
    def keep_alive_listen_key(self, listen_key: str) -> bool:
        """
        Keep the listen key alive (must be called every 30 minutes)
        
        Args:
            listen_key: The listen key to keep alive
            
        Returns:
            True if successful
        """
        try:
            self.client.futures_stream_keepalive(listenKey=listen_key)
            logger.debug("Listen key kept alive")
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to keep listen key alive: {e}")
            return False
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def get_account_balance(self) -> Optional[float]:
        """
        Get available balance (USDT or USDC) via REST API (fallback method)
        With retry mechanism for network errors
        
        Returns:
            Available balance or None
        """
        try:
            account = self.client.futures_account()
            
            # 检查所有资产余额
            balance = 0.0
            if 'assets' in account:
                for asset in account['assets']:
                    asset_name = asset.get('asset', 'N/A')
                    available_balance = float(asset.get('availableBalance', 0))
                    
                    # 优先使用 USDC，如果没有则使用 USDT
                    if asset_name == 'USDC' and available_balance > 0:
                        balance = available_balance
                    elif asset_name == 'USDT' and available_balance > 0 and balance == 0:
                        balance = available_balance
            
            return balance
        except BinanceAPIException as e:
            logger.error(f"Failed to get account balance: {e}")
            return None
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get trading pair information including min quantity and tick size
        With retry mechanism for network errors
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Symbol information or None
        """
        try:
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    return s
            return None
        except BinanceAPIException as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None
    
    def round_quantity(self, quantity: float, symbol: str) -> Optional[float]:
        """
        Round quantity to match symbol's precision requirements
        
        Args:
            quantity: Calculated quantity
            symbol: Trading pair symbol
            
        Returns:
            Rounded quantity or None
        """
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Could not get symbol info for {symbol}")
                return None
            
            # Find LOT_SIZE filter
            lot_size_filter = None
            for f in symbol_info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    lot_size_filter = f
                    break
            
            if not lot_size_filter:
                logger.error(f"LOT_SIZE filter not found for {symbol}")
                return None
            
            min_qty = float(lot_size_filter['minQty'])
            max_qty = float(lot_size_filter['maxQty'])
            step_size = float(lot_size_filter['stepSize'])
            
            # Calculate precision (number of decimal places)
            precision = 0
            if step_size < 1:
                precision = len(str(step_size).rstrip('0').split('.')[1])
            
            # Round down to step size using proper precision
            # Use floor division to avoid floating point precision issues
            steps = int(quantity / step_size)
            rounded_qty = steps * step_size
            
            # Format to exact precision to avoid floating point representation issues
            rounded_qty = float(f"{rounded_qty:.{precision}f}")
            
            # Ensure quantity is within limits
            if rounded_qty < min_qty:
                logger.error(
                    f"Calculated quantity {quantity:.6f} is below minimum {min_qty:.6f} for {symbol}"
                )
                return None
            
            if rounded_qty > max_qty:
                logger.error(
                    f"Calculated quantity {quantity:.6f} exceeds maximum {max_qty:.6f} for {symbol}"
                )
                return None
            
            
            return rounded_qty
            
        except Exception as e:
            logger.error(f"Error rounding quantity for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def round_price(self, price: float, symbol: str) -> Optional[float]:
        """
        Round price to match symbol's precision requirements
        
        Args:
            price: Calculated price
            symbol: Trading pair symbol
            
        Returns:
            Rounded price or None
        """
        try:
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Could not get symbol info for {symbol}")
                return None
            
            # Find PRICE_FILTER filter
            price_filter = None
            for f in symbol_info['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    price_filter = f
                    break
            
            if not price_filter:
                logger.error(f"PRICE_FILTER not found for {symbol}")
                return None
            
            tick_size = float(price_filter['tickSize'])
            
            # Calculate precision (number of decimal places)
            precision = 0
            if tick_size < 1:
                precision = len(str(tick_size).rstrip('0').split('.')[1])
            
            # Round down to tick size using proper precision
            # Use floor division to avoid floating point precision issues
            ticks = int(price / tick_size)
            rounded_price = ticks * tick_size
            
            # Format to exact precision to avoid floating point representation issues
            rounded_price = float(f"{rounded_price:.{precision}f}")
            
            return rounded_price
            
        except Exception as e:
            logger.error(f"Error rounding price for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def calculate_position_size(
        self,
        current_price: float,
        symbol: str,
        stop_loss_distance_percent: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate position size based on risk management (max loss per trade)
        
        Position size is calculated based on:
        1. Maximum loss per trade limit (e.g., 5% of account balance)
        2. Stop loss distance (percentage from entry to stop loss)
        3. Available leverage
        4. Trading fees and safety margin
        
        Formula:
        - Max position value by risk = (Balance × Max loss %) / Stop loss distance %
        - Max position value by leverage = Balance × Leverage
        - Actual position value = min(Max by risk, Max by leverage)
        
        Args:
            current_price: Current price of the asset
            symbol: Trading pair symbol (from configuration)
            stop_loss_distance_percent: Stop loss distance as percentage (e.g., 0.005 for 0.5%)
                                         If None, uses full leverage (old behavior)
            
        Returns:
            Position quantity or None
        """
        balance = self.get_account_balance()
        if balance is None:
            return None
        
        # Calculate maximum position value based on leverage
        max_position_value_by_leverage = balance * self.leverage
        
        # Calculate maximum position value based on risk management
        if stop_loss_distance_percent is not None and stop_loss_distance_percent > 0:
            # Risk-based position sizing
            # Position value = (Balance × Max loss %) / Stop loss distance %
            max_position_value_by_risk = (
                balance * self.max_loss_per_trade_percent / stop_loss_distance_percent
            )
            
            # Use the smaller of the two limits
            actual_position_value = min(max_position_value_by_risk, max_position_value_by_leverage)
            
        else:
            # No stop loss distance provided, use full leverage (old behavior)
            actual_position_value = max_position_value_by_leverage
            
        
        # Calculate opening fee based on position value
        opening_fee = actual_position_value * self.fee_rate
        
        # Calculate safety margin based on position value
        safety_margin_amount = actual_position_value * self.safety_margin
        
        # Calculate actual available position value after deducting fees and safety margin
        available_position_value = actual_position_value - opening_fee - safety_margin_amount
        
        # Calculate quantity
        quantity = available_position_value / current_price
        
        # Estimate closing fee for information only
        closing_fee = available_position_value * self.fee_rate
        
        # Calculate required margin
        required_margin = available_position_value / self.leverage
        
        
        # Validate that required margin doesn't exceed balance
        if required_margin > balance:
            logger.error(
                f"Required margin {required_margin:.2f} USDC exceeds balance {balance:.2f} USDC. "
                f"Cannot open position."
            )
            return None
        
        # Round quantity to match symbol precision
        rounded_quantity = self.round_quantity(quantity, symbol)
        if rounded_quantity is None:
            logger.error(f"Failed to round quantity for {symbol}")
            return None
        
        
        return rounded_quantity
    
    def check_available_margin(self, symbol: str, quantity: float, price: float) -> tuple[bool, float, float]:
        """
        检查可用保证金是否充足
        
        Args:
            symbol: 交易对
            quantity: 数量
            price: 价格
            
        Returns:
            Tuple of (is_sufficient, required_margin, available_margin)
        """
        try:
            # 获取账户余额
            balance = self.get_account_balance()
            if balance is None:
                logger.error("Failed to get account balance for margin check")
                return False, 0, 0
            
            # 计算持仓价值
            position_value = quantity * price
            
            # 计算所需保证金
            required_margin = position_value / self.leverage
            
            # 计算手续费
            opening_fee = position_value * self.fee_rate
            
            # 计算安全边际
            safety_margin = position_value * self.safety_margin
            
            # 总需求 = 保证金 + 手续费 + 安全边际
            total_required = required_margin + opening_fee + safety_margin
            
            # 检查是否充足
            is_sufficient = balance >= total_required
            
            return is_sufficient, required_margin, balance
            
        except Exception as e:
            logger.error(f"Error checking available margin for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, 0, 0
    
    def optimize_order_quantity(
        self,
        symbol: str,
        desired_quantity: float,
        current_price: float
    ) -> Optional[float]:
        """
        优化订单数量，确保在保证金范围内
        
        Args:
            symbol: 交易对
            desired_quantity: 期望数量
            current_price: 当前价格
            
        Returns:
            优化后的数量或None
        """
        try:
            # 检查保证金是否充足
            is_sufficient, required_margin, available_balance = self.check_available_margin(
                symbol, desired_quantity, current_price
            )
            
            if is_sufficient:
                # 保证金充足，使用期望数量
                return desired_quantity
            
            # 保证金不足，计算最大可用数量
            logger.warning(f"Margin insufficient for {symbol}, optimizing quantity...")
            
            # 计算可用价值（扣除手续费和安全边际）
            # 总价值 = 保证金 * 杠杆
            # 可用价值 = (余额 - 手续费 - 安全边际) * 杠杆
            # 但手续费和安全边际都基于价值，所以需要迭代计算
            
            # 简化计算：假设手续费和安全边际占总价值的比例
            fee_and_safety_ratio = self.fee_rate + self.safety_margin
            effective_leverage = self.leverage * (1 - fee_and_safety_ratio)
            
            # 可用价值 = 余额 * 有效杠杆
            available_value = available_balance * effective_leverage
            
            # 最大数量 = 可用价值 / 价格
            max_quantity = available_value / current_price
            
            # 四舍五入到交易对精度
            rounded_quantity = self.round_quantity(max_quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round optimized quantity for {symbol}")
                return None
            
            
            # 再次验证优化后的数量
            is_sufficient, _, _ = self.check_available_margin(symbol, rounded_quantity, current_price)
            if not is_sufficient:
                logger.error(f"Optimized quantity still insufficient for {symbol}")
                return None
            
            return rounded_quantity
            
        except Exception as e:
            logger.error(f"Error optimizing order quantity for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def check_margin_sufficient(
        self,
        symbol: str,
        quantity: float,
        current_price: float
    ) -> tuple[bool, Optional[float], Optional[float]]:
        """
        Check if there is sufficient margin to open a position
        
        Args:
            symbol: Trading pair symbol
            quantity: Position quantity
            current_price: Current price of the asset
            
        Returns:
            Tuple of (is_sufficient, required_margin, available_balance)
            - is_sufficient: True if margin is sufficient
            - required_margin: Required margin for the position
            - available_balance: Available balance in the account
        """
        try:
            # Get available balance
            balance = self.get_account_balance()
            if balance is None:
                logger.error("Failed to get account balance for margin check")
                return False, None, None
            
            # Calculate position value
            position_value = quantity * current_price
            
            # Calculate required margin (position value / leverage)
            required_margin = position_value / self.leverage
            
            # Calculate opening fee
            opening_fee = position_value * self.fee_rate
            
            # Calculate safety margin
            safety_margin_amount = position_value * self.safety_margin
            
            # Total required = required margin + opening fee + safety margin
            total_required = required_margin + opening_fee + safety_margin_amount
            
            # Check if balance is sufficient
            is_sufficient = balance >= total_required
            
            if not is_sufficient:
                logger.warning(
                    f"⚠️ Insufficient margin for {symbol}: "
                    f"required {total_required:.2f} USDC, available {balance:.2f} USDC "
                    f"(shortage: {total_required - balance:.2f} USDC)"
                )
            
            return is_sufficient, required_margin, balance
            
        except Exception as e:
            logger.error(f"Error checking margin sufficiency for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, None, None
    
    def open_long_position(self, symbol: str, quantity: float) -> Optional[Dict]:
        """
        Open a long position (BUY)
        
        Args:
            symbol: Trading pair symbol
            quantity: Position quantity (already rounded)
            
        Returns:
            Dictionary containing order result and position calculation info, or None
        """
        try:
            # Re-check balance before opening position to ensure sufficient margin
            balance = self.get_account_balance()
            if balance is None:
                logger.error(f"Failed to get account balance before opening long position for {symbol}")
                return None
            
            
            # Ensure leverage is set (only if not already cached)
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # Get current price to recalculate position size with latest balance
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
            except Exception as e:
                logger.error(f"Failed to get current price for {symbol}: {e}")
                return None
            
            # Recalculate position size with latest balance to ensure sufficient margin
            recalculated_quantity = self.calculate_position_size(current_price, symbol)
            if recalculated_quantity is None:
                logger.error(f"Failed to recalculate position size for {symbol}")
                return None
            
            # Use the recalculated quantity instead of the original one
            quantity = recalculated_quantity
            
            # Check if margin is sufficient before placing order
            is_margin_sufficient, required_margin, available_balance = self.check_margin_sufficient(
                symbol, quantity, current_price
            )
            
            if not is_margin_sufficient:
                logger.error(
                    f"Cannot open long position for {symbol}: Insufficient margin. "
                    f"Required: {required_margin:.2f} USDC, Available: {available_balance:.2f} USDC"
                )
                return None
            
            # Calculate position info for notification
            max_position_value = balance * self.leverage
            opening_fee = max_position_value * self.fee_rate
            safety_margin = max_position_value * self.safety_margin
            available_position_value = max_position_value - opening_fee - safety_margin
            required_margin = available_position_value / self.leverage
            
            position_calc_info = {
                'balance': balance,
                'max_position_value': max_position_value,
                'opening_fee': opening_fee,
                'safety_margin': safety_margin,
                'available_position_value': available_position_value,
                'required_margin': required_margin
            }
            
            # Place market order
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            
            # Check if order is filled
            order_id = order.get('orderId')
            if order_id:
                import time
                time.sleep(1)  # Wait a moment for order to be processed
                
                is_filled = self.check_order_filled(symbol, order_id)
                if not is_filled:
                    logger.error(f"Long position order {order_id} for {symbol} was not filled!")
                    # Cancel any remaining open orders
                    self.cancel_all_orders(symbol)
                    return None
            
            
            # Return both order and position calculation info
            return {
                'order': order,
                'position_calc_info': position_calc_info,
                'final_quantity': quantity,
                'final_price': current_price
            }
            
        except BinanceAPIException as e:
            logger.error(f"Failed to open long position for {symbol}: {e}")
            return None
    
    def open_short_position(self, symbol: str, quantity: float) -> Optional[Dict]:
        """
        Open a short position (SELL)
        
        Args:
            symbol: Trading pair symbol
            quantity: Position quantity (already rounded)
            
        Returns:
            Dictionary containing order result and position calculation info, or None
        """
        try:
            # Re-check balance before opening position to ensure sufficient margin
            balance = self.get_account_balance()
            if balance is None:
                logger.error(f"Failed to get account balance before opening short position for {symbol}")
                return None
            
            
            # Ensure leverage is set (only if not already cached)
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # Get current price to recalculate position size with latest balance
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
            except Exception as e:
                logger.error(f"Failed to get current price for {symbol}: {e}")
                return None
            
            # Recalculate position size with latest balance to ensure sufficient margin
            recalculated_quantity = self.calculate_position_size(current_price, symbol)
            if recalculated_quantity is None:
                logger.error(f"Failed to recalculate position size for {symbol}")
                return None
            
            # Use the recalculated quantity instead of the original one
            quantity = recalculated_quantity
            
            # Check if margin is sufficient before placing order
            is_margin_sufficient, required_margin, available_balance = self.check_margin_sufficient(
                symbol, quantity, current_price
            )
            
            if not is_margin_sufficient:
                logger.error(
                    f"Cannot open short position for {symbol}: Insufficient margin. "
                    f"Required: {required_margin:.2f} USDC, Available: {available_balance:.2f} USDC"
                )
                return None
            
            # Calculate position info for notification
            max_position_value = balance * self.leverage
            opening_fee = max_position_value * self.fee_rate
            safety_margin = max_position_value * self.safety_margin
            available_position_value = max_position_value - opening_fee - safety_margin
            required_margin = available_position_value / self.leverage
            
            position_calc_info = {
                'balance': balance,
                'max_position_value': max_position_value,
                'opening_fee': opening_fee,
                'safety_margin': safety_margin,
                'available_position_value': available_position_value,
                'required_margin': required_margin
            }
            
            # Place market order
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            
            # Check if order is filled
            order_id = order.get('orderId')
            if order_id:
                import time
                time.sleep(1)  # Wait a moment for order to be processed
                
                is_filled = self.check_order_filled(symbol, order_id)
                if not is_filled:
                    logger.error(f"Short position order {order_id} for {symbol} was not filled!")
                    # Cancel any remaining open orders
                    self.cancel_all_orders(symbol)
                    return None
            
            
            # Return both order and position calculation info
            return {
                'order': order,
                'position_calc_info': position_calc_info,
                'final_quantity': quantity,
                'final_price': current_price
            }
            
        except BinanceAPIException as e:
            logger.error(f"Failed to open short position for {symbol}: {e}")
            return None
    
    def close_long_position(self, symbol: str) -> Optional[Dict]:
        """
        Close a long position (SELL)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Order result or None
        """
        try:
            # Get current position
            position = self.get_position(symbol)
            if not position or float(position['positionAmt']) <= 0:
                logger.warning(f"No long position to close for {symbol}")
                return None
            
            quantity = abs(float(position['positionAmt']))
            
            # Round quantity to match symbol precision (unified precision handling)
            rounded_quantity = self.round_quantity(quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round quantity for closing long position {symbol}")
                return None
            
            
            # Place market order to close
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=rounded_quantity,
                reduceOnly=True
            )
            
            
            # Check if order is filled
            order_id = order.get('orderId')
            if order_id:
                import time
                time.sleep(1)  # Wait a moment for order to be processed
                
                is_filled = self.check_order_filled(symbol, order_id)
                if not is_filled:
                    logger.error(f"Long position close order {order_id} for {symbol} was not filled!")
                    # Cancel any remaining open orders
                    self.cancel_all_orders(symbol)
                    return None
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to close long position for {symbol}: {e}")
            return None
    
    def close_short_position(self, symbol: str) -> Optional[Dict]:
        """
        Close a short position (BUY)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Order result or None
        """
        try:
            # Get current position
            position = self.get_position(symbol)
            if not position or float(position['positionAmt']) >= 0:
                logger.warning(f"No short position to close for {symbol}")
                return None
            
            quantity = abs(float(position['positionAmt']))
            
            # Round quantity to match symbol precision (unified precision handling)
            rounded_quantity = self.round_quantity(quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round quantity for closing short position {symbol}")
                return None
            
            
            # Place market order to close
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=rounded_quantity,
                reduceOnly=True
            )
            
            
            # Check if order is filled
            order_id = order.get('orderId')
            if order_id:
                import time
                time.sleep(1)  # Wait a moment for order to be processed
                
                is_filled = self.check_order_filled(symbol, order_id)
                if not is_filled:
                    logger.error(f"Short position close order {order_id} for {symbol} was not filled!")
                    # Cancel any remaining open orders
                    self.cancel_all_orders(symbol)
                    return None
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to close short position for {symbol}: {e}")
            return None
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for a symbol
        With retry mechanism for network errors
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Position information or None
        """
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            for pos in positions:
                if pos['symbol'] == symbol and float(pos['positionAmt']) != 0:
                    return pos
            return None
        except BinanceAPIException as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            return None
    
    def close_partial_position(self, symbol: str, close_ratio: float) -> Optional[Dict]:
        """
        Close a partial position by ratio (for partial take profit)
        
        Args:
            symbol: Trading pair symbol
            close_ratio: Ratio of position to close (0.0 to 1.0)
            
        Returns:
            Order result or None
        """
        try:
            # Get current position
            position = self.get_position(symbol)
            if not position:
                logger.warning(f"No position to close for {symbol}")
                return None
            
            position_amt = float(position['positionAmt'])
            position_side = 'LONG' if position_amt > 0 else 'SHORT'
            
            # Calculate quantity to close
            close_quantity = abs(position_amt) * close_ratio
            
            # Round quantity to match symbol precision
            rounded_quantity = self.round_quantity(close_quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round quantity for partial close of {symbol}")
                return None
            
            
            # Place market order to close partial position
            if position_side == 'LONG':
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_MARKET,
                    quantity=rounded_quantity,
                    reduceOnly=True
                )
            else:  # SHORT
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_MARKET,
                    quantity=rounded_quantity,
                    reduceOnly=True
                )
            
            
            # Check if order is filled
            order_id = order.get('orderId')
            if order_id:
                import time
                time.sleep(1)  # Wait a moment for order to be processed
                
                is_filled = self.check_order_filled(symbol, order_id)
                if not is_filled:
                    logger.error(f"Partial close order {order_id} for {symbol} was not filled!")
                    # Cancel any remaining open orders
                    self.cancel_all_orders(symbol)
                    return None
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to close partial position for {symbol}: {e}")
            return None
    
    async def close_all_positions(self, symbol: str) -> bool:
        """
        Close all positions for a symbol asynchronously
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        import asyncio
        try:
            position = await asyncio.to_thread(self.get_position, symbol)
            if not position:
                return True
            
            position_amt = float(position['positionAmt'])
            
            if position_amt > 0:
                # Close long position asynchronously
                await asyncio.to_thread(self.close_long_position, symbol)
            elif position_amt < 0:
                # Close short position asynchronously
                await asyncio.to_thread(self.close_short_position, symbol)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to close all positions for {symbol}: {e}")
            return False
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def get_open_orders(self, symbol: str) -> Optional[list]:
        """
        Get all open orders for a symbol
        With retry mechanism for network errors
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            List of open orders or None
        """
        try:
            orders = self.client.futures_get_open_orders(symbol=symbol)
            return orders
        except BinanceAPIException as e:
            logger.error(f"Failed to get open orders for {symbol}: {e}")
            return None
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Cancel an order by order ID
        With retry mechanism for network errors
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        try:
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            return True
        except BinanceAPIException as e:
            logger.error(f"[CANCEL_ORDER] ✗ Failed to cancel order {order_id} for {symbol}: {e}")
            return False
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def cancel_all_orders(self, symbol: str) -> bool:
        """
        Cancel all open orders for a symbol
        Uses batch cancellation API for efficiency
        With retry mechanism for network errors
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        try:
            # Use the batch cancellation API
            result = self.client.futures_cancel_all_open_orders(symbol=symbol)
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel all orders for {symbol}: {e}")
            return False
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def get_order_status(self, symbol: str, order_id: int) -> Optional[Dict]:
        """
        Get order status by order ID
        With retry mechanism for network errors
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID
            
        Returns:
            Order information or None
        """
        try:
            order = self.client.futures_get_order(symbol=symbol, orderId=order_id)
            return order
        except BinanceAPIException as e:
            logger.error(f"Failed to get order status for {symbol} order {order_id}: {e}")
            return None
    
    def check_order_filled(self, symbol: str, order_id: int) -> bool:
        """
        Check if an order is filled
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID
            
        Returns:
            True if order is filled
        """
        try:
            order = self.get_order_status(symbol, order_id)
            if not order:
                return False
            
            status = order.get('status', '')
            is_filled = status == 'FILLED'
            
            return is_filled
            
        except Exception as e:
            logger.error(f"Error checking if order {order_id} is filled: {e}")
            return False
    
    # ==================== Limit Order Methods ====================
    
    def open_long_position_limit(self, symbol: str, quantity: float, limit_price: float) -> Optional[Dict]:
        """
        使用限价单开多仓
        
        Args:
            symbol: 交易对
            quantity: 数量（已四舍五入）
            limit_price: 限价单价格
            
        Returns:
            订单结果字典或None
        """
        try:
            # 确保杠杆已设置
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # 优化订单数量，确保在保证金范围内
            optimized_quantity = self.optimize_order_quantity(symbol, quantity, limit_price)
            if optimized_quantity is None:
                logger.error(f"Failed to optimize order quantity for {symbol}")
                return None
            
            # 使用优化后的数量
            if optimized_quantity != quantity:
                quantity = optimized_quantity
            
            # 检查保证金是否充足
            is_margin_sufficient, required_margin, available_balance = self.check_margin_sufficient(
                symbol, quantity, limit_price
            )
            
            if not is_margin_sufficient:
                logger.error(
                    f"Cannot open long position for {symbol}: Insufficient margin. "
                    f"Required: {required_margin:.2f} USDC, Available: {available_balance:.2f} USDC"
                )
                return None
            
            # 获取当前价格用于风险检查
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
            except Exception as e:
                logger.error(f"Failed to get current price for risk check: {e}")
                current_price = limit_price
            
            # 执行订单风险检查
            is_risk_safe, risk_reason, risk_info = self.risk_control.check_order_risk(
                symbol=symbol,
                side='LONG',
                order_price=limit_price,
                current_price=current_price,
                klines=None  # 如果有K线数据可以传入
            )
            
            if not is_risk_safe:
                logger.warning(
                    f"Order risk check failed for {symbol}: {risk_reason}. "
                    f"Risk info: {self.risk_control.get_risk_summary(risk_info)}"
                )
                return None
            
            # 下达限价单
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=limit_price,
                timeInForce='GTC'  # Good Till Cancel
            )
            
            
            
            return {
                'order': order,
                'final_quantity': quantity,
                'final_price': limit_price
            }
            
        except BinanceAPIException as e:
            logger.error(f"Failed to open long position limit order for {symbol}: {e}")
            return None
    
    def open_short_position_limit(self, symbol: str, quantity: float, limit_price: float) -> Optional[Dict]:
        """
        使用限价单开空仓
        
        Args:
            symbol: 交易对
            quantity: 数量（已四舍五入）
            limit_price: 限价单价格
            
        Returns:
            订单结果字典或None
        """
        try:
            # 确保杠杆已设置
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # 优化订单数量，确保在保证金范围内
            optimized_quantity = self.optimize_order_quantity(symbol, quantity, limit_price)
            if optimized_quantity is None:
                logger.error(f"Failed to optimize order quantity for {symbol}")
                return None
            
            # 使用优化后的数量
            if optimized_quantity != quantity:
                quantity = optimized_quantity
            
            # 检查保证金是否充足
            is_margin_sufficient, required_margin, available_balance = self.check_margin_sufficient(
                symbol, quantity, limit_price
            )
            
            if not is_margin_sufficient:
                logger.error(
                    f"Cannot open short position for {symbol}: Insufficient margin. "
                    f"Required: {required_margin:.2f} USDC, Available: {available_balance:.2f} USDC"
                )
                return None
            
            # 获取当前价格用于风险检查
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
            except Exception as e:
                logger.error(f"Failed to get current price for risk check: {e}")
                current_price = limit_price
            
            # 执行订单风险检查
            is_risk_safe, risk_reason, risk_info = self.risk_control.check_order_risk(
                symbol=symbol,
                side='SHORT',
                order_price=limit_price,
                current_price=current_price,
                klines=None  # 如果有K线数据可以传入
            )
            
            if not is_risk_safe:
                logger.warning(
                    f"Order risk check failed for {symbol}: {risk_reason}. "
                    f"Risk info: {self.risk_control.get_risk_summary(risk_info)}"
                )
                return None
            
            # 下达限价单
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                quantity=quantity,
                price=limit_price,
                timeInForce='GTC'  # Good Till Cancel
            )
            
            
            
            return {
                'order': order,
                'final_quantity': quantity,
                'final_price': limit_price
            }
            
        except BinanceAPIException as e:
            logger.error(f"Failed to open short position limit order for {symbol}: {e}")
            return None
    
    def close_long_position_limit(self, symbol: str, limit_price: float) -> Optional[Dict]:
        """
        使用限价单平多仓
        
        Args:
            symbol: 交易对
            limit_price: 限价单价格
            
        Returns:
            订单结果或None
        """
        try:
            # 获取当前持仓
            position = self.get_position(symbol)
            if not position or float(position['positionAmt']) <= 0:
                logger.warning(f"No long position to close for {symbol}")
                return None
            
            quantity = abs(float(position['positionAmt']))
            
            # 四舍五入数量
            rounded_quantity = self.round_quantity(quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round quantity for closing long position {symbol}")
                return None
            
            
            # 下达限价单平仓
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                quantity=rounded_quantity,
                price=limit_price,
                reduceOnly=True,
                timeInForce='GTC'
            )
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to close long position with limit order for {symbol}: {e}")
            return None
    
    def close_short_position_limit(self, symbol: str, limit_price: float) -> Optional[Dict]:
        """
        使用限价单平空仓
        
        Args:
            symbol: 交易对
            limit_price: 限价单价格
            
        Returns:
            订单结果或None
        """
        try:
            # 获取当前持仓
            position = self.get_position(symbol)
            if not position or float(position['positionAmt']) >= 0:
                logger.warning(f"No short position to close for {symbol}")
                return None
            
            quantity = abs(float(position['positionAmt']))
            
            # 四舍五入数量
            rounded_quantity = self.round_quantity(quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round quantity for closing short position {symbol}")
                return None
            
            
            # 下达限价单平仓
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_LIMIT,
                quantity=rounded_quantity,
                price=limit_price,
                reduceOnly=True,
                timeInForce='GTC'
            )
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to close short position with limit order for {symbol}: {e}")
            return None
    
    def calculate_entry_limit_price(
        self,
        symbol: str,
        current_price: float,
        side: str,
        klines: Optional[list] = None
    ) -> Optional[float]:
        """
        计算开仓限价单价格
        
        Args:
            symbol: 交易对
            current_price: 当前价格
            side: 'LONG' or 'SHORT'
            klines: K线数据（用于计算支撑/阻力位）
            
        Returns:
            限价单价格或None
        """
        try:
            # 获取配置参数
            price_offset_percent = self.config.get_config(
                "trading.limit_order", "entry_price_offset_percent", default=0.001
            )
            price_offset_max_percent = self.config.get_config(
                "trading.limit_order", "entry_price_offset_max_percent", default=0.002
            )
            use_support_resistance = self.config.get_config(
                "trading.limit_order", "entry_use_support_resistance", default=True
            )
            lookback = self.config.get_config(
                "trading.limit_order", "entry_support_resistance_lookback", default=5
            )
            
            # 基础价格偏移
            if side == 'LONG':
                # 做多：等待价格回调
                base_limit_price = current_price * (1 - price_offset_percent)
            else:  # SHORT
                # 做空：等待价格反弹
                base_limit_price = current_price * (1 + price_offset_percent)
            
            # 如果使用支撑/阻力位
            if use_support_resistance and klines and len(klines) >= lookback:
                support_resistance_price = self._calculate_support_resistance_price(
                    klines, side, lookback
                )
                
                if support_resistance_price is not None:
                    if side == 'LONG':
                        # 做多：使用支撑位（取较小值）
                        limit_price = min(base_limit_price, support_resistance_price)
                    else:  # SHORT
                        # 做空：使用阻力位（取较大值）
                        limit_price = max(base_limit_price, support_resistance_price)
                    
                else:
                    limit_price = base_limit_price
            else:
                limit_price = base_limit_price
            
            # 确保价格不超过最大偏移
            if side == 'LONG':
                max_limit_price = current_price * (1 - price_offset_max_percent)
                limit_price = min(limit_price, max_limit_price)
            else:  # SHORT
                max_limit_price = current_price * (1 + price_offset_max_percent)
                limit_price = max(limit_price, max_limit_price)
            
            # 四舍五入价格
            rounded_price = self.round_price(limit_price, symbol)
            if rounded_price is None:
                logger.error(f"Failed to round limit price for {symbol}")
                return None
            
            return rounded_price
            
        except Exception as e:
            logger.error(f"Error calculating entry limit price for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def calculate_take_profit_limit_price(
        self,
        symbol: str,
        entry_price: float,
        side: str,
        take_profit_percent: float
    ) -> Optional[float]:
        """
        计算止盈限价单价格
        
        Args:
            symbol: 交易对
            entry_price: 入场价格
            side: 'LONG' or 'SHORT'
            take_profit_percent: 止盈百分比
            
        Returns:
            止盈限价单价格或None
        """
        try:
            # 获取配置参数
            price_offset = self.config.get_config(
                "trading.limit_order", "take_profit_price_offset", default=0.001
            )
            
            # 计算止盈价格
            if side == 'LONG':
                # 做多止盈：入场价 * (1 + 止盈百分比 - 偏移)
                limit_price = entry_price * (1 + take_profit_percent - price_offset)
            else:  # SHORT
                # 做空止盈：入场价 * (1 - 止盈百分比 + 偏移)
                limit_price = entry_price * (1 - take_profit_percent + price_offset)
            
            # 四舍五入价格
            rounded_price = self.round_price(limit_price, symbol)
            if rounded_price is None:
                logger.error(f"Failed to round take profit limit price for {symbol}")
                return None
            
            return rounded_price
            
        except Exception as e:
            logger.error(f"Error calculating take profit limit price for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _calculate_support_resistance_price(
        self,
        klines: list,
        side: str,
        lookback: int
    ) -> Optional[float]:
        """
        计算支撑/阻力位价格
        
        Args:
            klines: K线数据
            side: 'LONG' or 'SHORT'
            lookback: 回看K线数
            
        Returns:
            支撑/阻力位价格或None
        """
        try:
            if len(klines) < lookback:
                return None
            
            # 获取最近N根K线
            recent_klines = klines[-lookback:]
            
            if side == 'LONG':
                # 做多：使用最低点作为支撑位
                lows = [float(k['low']) for k in recent_klines]
                support_price = min(lows)
                return support_price
            else:  # SHORT
                # 做空：使用最高点作为阻力位
                highs = [float(k['high']) for k in recent_klines]
                resistance_price = max(highs)
                return resistance_price
            
        except Exception as e:
            logger.error(f"Error calculating support/resistance price: {e}")
            return None
    
    
    # ==================== Order Modification Methods ====================
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def modify_limit_order_price(
        self,
        symbol: str,
        order_id: int,
        new_price: float
    ) -> Optional[Dict]:
        """
        修改限价单价格
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            new_price: 新价格
            
        Returns:
            修改后的订单信息或None
        """
        try:
            # 获取当前订单状态
            current_order = self.get_order_status(symbol, order_id)
            if not current_order:
                logger.error(f"Cannot find order {order_id} for {symbol}")
                return None
            
            # 检查订单状态
            status = current_order.get('status', '')
            if status in ['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED']:
                logger.warning(
                    f"Cannot modify order {order_id} for {symbol}: "
                    f"order is {status}"
                )
                return None
            
            # 获取订单数量
            orig_qty = float(current_order.get('origQty', 0))
            side = current_order.get('side', '')
            
            # 四舍五入新价格
            rounded_price = self.round_price(new_price, symbol)
            if rounded_price is None:
                logger.error(f"Failed to round new price for {symbol}")
                return None
            
            
            # 取消原订单
            cancel_success = self.cancel_order(symbol, order_id)
            if not cancel_success:
                logger.error(f"Failed to cancel order {order_id} for modification")
                return None
            
            # 等待取消完成
            import time
            time.sleep(0.5)
            
            # 重新下单
            if side == 'BUY':
                new_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    quantity=orig_qty,
                    price=rounded_price,
                    timeInForce='GTC'
                )
            else:  # SELL
                new_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_LIMIT,
                    quantity=orig_qty,
                    price=rounded_price,
                    timeInForce='GTC'
                )
            
            
            return new_order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to modify order price for {symbol}: {e}")
            return None
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def modify_limit_order_quantity(
        self,
        symbol: str,
        order_id: int,
        new_quantity: float
    ) -> Optional[Dict]:
        """
        修改限价单数量
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            new_quantity: 新数量
            
        Returns:
            修改后的订单信息或None
        """
        try:
            # 获取当前订单状态
            current_order = self.get_order_status(symbol, order_id)
            if not current_order:
                logger.error(f"Cannot find order {order_id} for {symbol}")
                return None
            
            # 检查订单状态
            status = current_order.get('status', '')
            if status in ['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED']:
                logger.warning(
                    f"Cannot modify order {order_id} for {symbol}: "
                    f"order is {status}"
                )
                return None
            
            # 获取已成交数量
            executed_qty = float(current_order.get('executedQty', 0))
            orig_qty = float(current_order.get('origQty', 0))
            remaining_qty = orig_qty - executed_qty
            
            # 新数量不能小于已成交数量
            if new_quantity < executed_qty:
                logger.error(
                    f"Cannot reduce quantity below executed amount: "
                    f"new_quantity={new_quantity}, executed_qty={executed_qty}"
                )
                return None
            
            # 计算需要增加的数量
            additional_qty = new_quantity - orig_qty
            
            # 四舍五入新数量
            rounded_quantity = self.round_quantity(new_quantity, symbol)
            if rounded_quantity is None:
                logger.error(f"Failed to round new quantity for {symbol}")
                return None
            
            
            # 如果新数量等于原数量，无需修改
            if rounded_quantity == orig_qty:
                return current_order
            
            # 取消原订单
            cancel_success = self.cancel_order(symbol, order_id)
            if not cancel_success:
                logger.error(f"Failed to cancel order {order_id} for modification")
                return None
            
            # 等待取消完成
            import time
            time.sleep(0.5)
            
            # 重新下单
            side = current_order.get('side', '')
            price = float(current_order.get('price', 0))
            
            if side == 'BUY':
                new_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_LIMIT,
                    quantity=rounded_quantity,
                    price=price,
                    timeInForce='GTC'
                )
            else:  # SELL
                new_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_LIMIT,
                    quantity=rounded_quantity,
                    price=price,
                    timeInForce='GTC'
                )
            
            
            return new_order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to modify order quantity for {symbol}: {e}")
            return None
    
    def smart_adjust_limit_order_price(
        self,
        symbol: str,
        order_id: int,
        current_price: float,
        side: str,
        klines: Optional[list] = None
    ) -> Optional[Dict]:
        """
        智能调整限价单价格（根据市场情况自动调整）
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            current_price: 当前价格
            side: 'LONG' or 'SHORT'
            klines: K线数据（可选）
            
        Returns:
            修改后的订单信息或None
        """
        try:
            # 获取当前订单状态
            current_order = self.get_order_status(symbol, order_id)
            if not current_order:
                logger.error(f"Cannot find order {order_id} for {symbol}")
                return None
            
            # 检查订单状态
            status = current_order.get('status', '')
            if status in ['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED']:
                logger.warning(
                    f"Cannot adjust order {order_id} for {symbol}: "
                    f"order is {status}"
                )
                return None
            
            # 获取当前订单价格
            current_order_price = float(current_order.get('price', 0))
            
            # 计算价格偏差
            price_deviation = abs(current_order_price - current_price) / current_price
            
            # 获取配置参数
            price_away_threshold = self.config.get_config(
                "trading.limit_order", "entry_price_away_threshold", default=0.005
            )
            
            # 如果价格偏差在合理范围内，无需调整
            if price_deviation <= price_away_threshold:
                return current_order
            
            # 计算新的限价单价格
            new_limit_price = self.calculate_entry_limit_price(
                symbol, current_price, side, klines
            )
            
            if new_limit_price is None:
                logger.error(f"Failed to calculate new limit price for {symbol}")
                return None
            
            # 如果新价格与当前价格相同，无需调整
            if abs(new_limit_price - current_order_price) < 0.0001:
                return current_order
            
            
            # 修改订单价格
            modified_order = self.modify_limit_order_price(symbol, order_id, new_limit_price)
            
            return modified_order
            
        except Exception as e:
            logger.error(f"Error in smart adjust limit order price for {symbol}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None