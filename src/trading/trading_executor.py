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
        
        logger.info(
            f"Trading executor initialized with {self.leverage}x leverage, "
            f"max_loss_per_trade={self.max_loss_per_trade_percent*100:.1f}%, "
            f"fee_rate={self.fee_rate:.4f}, safety_margin={self.safety_margin:.4f}"
        )
        
        # Initialize leverage for all configured symbols
        self._initialize_leverage()
        
        # Cancel all open orders on startup to clean up any stale orders
        self._cleanup_stale_orders()
    
    def _initialize_leverage(self) -> None:
        """Initialize leverage for all configured symbols"""
        symbols = self.config.binance_symbols
        
        logger.info(f"Initializing leverage for {len(symbols)} symbol(s)...")
        logger.info(f"Symbols to configure: {symbols}")
        
        for symbol in symbols:
            logger.info(f"Processing symbol: {symbol}")
            try:
                success = self.set_leverage(symbol)
                if success:
                    self.leverage_cache.add(symbol)
                    logger.info(f"✓ Leverage {self.leverage}x set for {symbol}")
                else:
                    logger.error(f"✗ Failed to set leverage for {symbol}")
            except Exception as e:
                logger.error(f"✗ Exception while setting leverage for {symbol}: {e}")
        
        logger.info(f"Leverage initialization complete. Set for {len(self.leverage_cache)}/{len(symbols)} symbols")
    
    def _cleanup_stale_orders(self) -> None:
        """Cancel all open orders on startup to clean up any stale orders"""
        symbols = self.config.binance_symbols
        
        logger.info(f"Cleaning up stale orders for {len(symbols)} symbol(s)...")
        
        for symbol in symbols:
            try:
                orders = self.get_open_orders(symbol)
                if orders:
                    logger.warning(f"Found {len(orders)} stale order(s) for {symbol}, cancelling...")
                    success = self.cancel_all_orders(symbol)
                    if success:
                        logger.info(f"✓ Cleaned up stale orders for {symbol}")
                    else:
                        logger.error(f"✗ Failed to clean up stale orders for {symbol}")
                else:
                    logger.info(f"No stale orders found for {symbol}")
            except Exception as e:
                logger.error(f"Error cleaning up stale orders for {symbol}: {e}")
        
        logger.info("Stale order cleanup complete")
    
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
            logger.info(f"Margin type set to {margin_type} for {symbol}")
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
            logger.info(f"Leverage set to {self.leverage}x for {symbol}")
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
            logger.info(f"✓ Listen key obtained: {listen_key}")
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
    
    def get_account_balance(self) -> Optional[float]:
        """
        Get available balance (USDT or USDC) via REST API (fallback method)
        
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
            
            logger.info(f"Available balance: {balance} USDC/USDT")
            return balance
        except BinanceAPIException as e:
            logger.error(f"Failed to get account balance: {e}")
            return None
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        Get trading pair information including min quantity and tick size
        
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
            
            logger.info(
                f"Quantity rounded: {quantity:.6f} -> {rounded_qty:.6f} "
                f"(step: {step_size:.6f}, min: {min_qty:.6f}, max: {max_qty:.6f}, precision: {precision})"
            )
            
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
            
            logger.info(
                f"Price rounded: {price:.6f} -> {rounded_price:.6f} "
                f"(tick: {tick_size:.6f}, precision: {precision})"
            )
            
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
            
            logger.info(
                f"Risk-based position sizing:\n"
                f"  Balance: {balance:.2f} USDC\n"
                f"  Max loss per trade: {self.max_loss_per_trade_percent*100:.1f}%\n"
                f"  Stop loss distance: {stop_loss_distance_percent*100:.2f}%\n"
                f"  Max position by risk: {max_position_value_by_risk:.2f} USDC\n"
                f"  Max position by leverage: {max_position_value_by_leverage:.2f} USDC\n"
                f"  Actual position value: {actual_position_value:.2f} USDC\n"
                f"  Effective leverage: {actual_position_value/balance:.2f}x"
            )
        else:
            # No stop loss distance provided, use full leverage (old behavior)
            actual_position_value = max_position_value_by_leverage
            
            logger.info(
                f"Full leverage position sizing (no stop loss distance provided):\n"
                f"  Balance: {balance:.2f} USDC\n"
                f"  Leverage: {self.leverage}x\n"
                f"  Position value: {actual_position_value:.2f} USDC"
            )
        
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
        
        logger.info(
            f"Position size calculation details:\n"
            f"  Opening fee: {opening_fee:.4f} USDC ({self.fee_rate*100:.2f}%)\n"
            f"  Safety margin: {safety_margin_amount:.4f} USDC ({self.safety_margin*100:.1f}%)\n"
            f"  Available position value: {available_position_value:.2f} USDC\n"
            f"  Required margin: {required_margin:.2f} USDC\n"
            f"  Closing fee (est): {closing_fee:.4f} USDC\n"
            f"  Raw quantity: {quantity:.6f}\n"
            f"  Current price: {current_price:.2f} USDC"
        )
        
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
        
        logger.info(f"Final quantity after rounding: {rounded_quantity:.6f}")
        
        return rounded_quantity
    
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
            
            logger.info(f"Re-verified balance before opening long position: {balance:.2f} USDC")
            
            # Ensure leverage is set (only if not already cached)
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # Get current price to recalculate position size with latest balance
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                logger.info(f"Current price for {symbol}: {current_price:.2f} USDC")
            except Exception as e:
                logger.error(f"Failed to get current price for {symbol}: {e}")
                return None
            
            # Recalculate position size with latest balance to ensure sufficient margin
            recalculated_quantity = self.calculate_position_size(current_price, symbol)
            if recalculated_quantity is None:
                logger.error(f"Failed to recalculate position size for {symbol}")
                return None
            
            # Use the recalculated quantity instead of the original one
            logger.info(f"Using recalculated quantity: {recalculated_quantity:.6f} (original: {quantity:.6f})")
            quantity = recalculated_quantity
            
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
            logger.info(f"[ORDER] Creating MARKET order for {symbol}: side=BUY, quantity={quantity:.6f}")
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"[ORDER] MARKET order created: orderId={order.get('orderId')}, status={order.get('status')}, type={order.get('type')}")
            logger.info(f"[ORDER] Order details: {order}")
            
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
            
            logger.info(f"Long position opened successfully for {symbol}")
            
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
            
            logger.info(f"Re-verified balance before opening short position: {balance:.2f} USDC")
            
            # Ensure leverage is set (only if not already cached)
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # Get current price to recalculate position size with latest balance
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                logger.info(f"Current price for {symbol}: {current_price:.2f} USDC")
            except Exception as e:
                logger.error(f"Failed to get current price for {symbol}: {e}")
                return None
            
            # Recalculate position size with latest balance to ensure sufficient margin
            recalculated_quantity = self.calculate_position_size(current_price, symbol)
            if recalculated_quantity is None:
                logger.error(f"Failed to recalculate position size for {symbol}")
                return None
            
            # Use the recalculated quantity instead of the original one
            logger.info(f"Using recalculated quantity: {recalculated_quantity:.6f} (original: {quantity:.6f})")
            quantity = recalculated_quantity
            
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
            logger.info(f"[ORDER] Creating MARKET order for {symbol}: side=SELL, quantity={quantity:.6f}")
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"[ORDER] MARKET order created: orderId={order.get('orderId')}, status={order.get('status')}, type={order.get('type')}")
            logger.info(f"[ORDER] Order details: {order}")
            
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
            
            logger.info(f"Short position opened successfully for {symbol}")
            
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
            
            logger.info(f"Closing long position: quantity={quantity:.6f} -> rounded={rounded_quantity:.6f}")
            
            # Place market order to close
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=rounded_quantity,
                reduceOnly=True
            )
            
            logger.info(f"Long position close order placed for {symbol}: {order}")
            
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
            
            logger.info(f"Long position closed successfully for {symbol}")
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
            
            logger.info(f"Closing short position: quantity={quantity:.6f} -> rounded={rounded_quantity:.6f}")
            
            # Place market order to close
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=rounded_quantity,
                reduceOnly=True
            )
            
            logger.info(f"Short position close order placed for {symbol}: {order}")
            
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
            
            logger.info(f"Short position closed successfully for {symbol}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"Failed to close short position for {symbol}: {e}")
            return None
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for a symbol
        
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
                logger.info(f"No positions to close for {symbol}")
                return True
            
            position_amt = float(position['positionAmt'])
            
            if position_amt > 0:
                # Close long position asynchronously
                await asyncio.to_thread(self.close_long_position, symbol)
            elif position_amt < 0:
                # Close short position asynchronously
                await asyncio.to_thread(self.close_short_position, symbol)
            
            logger.info(f"All positions closed for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close all positions for {symbol}: {e}")
            return False
    
    def get_open_orders(self, symbol: str) -> Optional[list]:
        """
        Get all open orders for a symbol
        
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
    
    def cancel_order(self, symbol: str, order_id: int) -> bool:
        """
        Cancel an order by order ID
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        try:
            self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order {order_id} cancelled for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order {order_id} for {symbol}: {e}")
            return False
    
    def cancel_all_stop_loss_orders(self, symbol: str) -> bool:
        """
        Cancel all stop loss orders for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        try:
            orders = self.get_open_orders(symbol)
            if not orders:
                logger.debug(f"No open orders to cancel for {symbol}")
                return True
            
            cancelled_count = 0
            for order in orders:
                # Check if it's a stop loss order (STOP_MARKET type and reduceOnly=True)
                if order.get('type') == 'STOP_MARKET' and order.get('reduceOnly', False):
                    order_id = order.get('orderId')
                    if order_id:
                        if self.cancel_order(symbol, order_id):
                            cancelled_count += 1
            
            logger.info(f"Cancelled {cancelled_count} stop loss order(s) for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel stop loss orders for {symbol}: {e}")
            return False
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """
        Cancel all open orders for a symbol (including stop loss orders)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        try:
            orders = self.get_open_orders(symbol)
            if not orders:
                logger.debug(f"No open orders to cancel for {symbol}")
                return True
            
            cancelled_count = 0
            for order in orders:
                order_id = order.get('orderId')
                if order_id:
                    if self.cancel_order(symbol, order_id):
                        cancelled_count += 1
            
            logger.info(f"Cancelled {cancelled_count} order(s) for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel all orders for {symbol}: {e}")
            return False
    
    def get_order_status(self, symbol: str, order_id: int) -> Optional[Dict]:
        """
        Get order status by order ID
        
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
            
            logger.info(
                f"Order {order_id} status: {status}, filled: {is_filled}, "
                f"executedQty: {order.get('executedQty', 0)}, origQty: {order.get('origQty', 0)}"
            )
            
            return is_filled
            
        except Exception as e:
            logger.error(f"Error checking if order {order_id} is filled: {e}")
            return False
    
    def has_stop_loss_order(self, symbol: str) -> bool:
        """
        Check if there is an active stop loss order for a symbol
        This checks both regular orders and conditional orders (algo orders)
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if stop loss order exists
        """
        try:
            # Check regular orders
            orders = self.get_open_orders(symbol)
            if orders:
                for order in orders:
                    if order.get('type') == 'STOP_MARKET' and order.get('reduceOnly', False):
                        return True
            
            # Check conditional orders (algo orders)
            algo_orders = self.get_open_algo_orders(symbol)
            if algo_orders:
                for order in algo_orders:
                    if (order.get('orderType') == 'STOP_MARKET' and
                        order.get('reduceOnly', False) and
                        order.get('algoStatus') == 'NEW'):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check stop loss order for {symbol}: {e}")
            return False
    
    def get_open_algo_orders(self, symbol: str) -> Optional[list]:
        """
        Get all open conditional (algo) orders for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            List of open algo orders or None
        """
        try:
            # Use futures_get_open_orders which returns both regular and conditional orders
            orders = self.client.futures_get_open_orders(symbol=symbol)
            if not orders:
                return []
            
            # Filter for conditional orders (those with algoId)
            algo_orders = [order for order in orders if 'algoId' in order]
            return algo_orders
            
        except BinanceAPIException as e:
            logger.error(f"Failed to get open algo orders for {symbol}: {e}")
            return None
    
    def cancel_algo_order(self, symbol: str, algo_id: int) -> bool:
        """
        Cancel a conditional (algo) order by algo ID
        
        Args:
            symbol: Trading pair symbol
            algo_id: Algo order ID to cancel
            
        Returns:
            True if successful
        """
        try:
            self.client.futures_cancel_order(symbol=symbol, orderId=algo_id)
            logger.info(f"Algo order {algo_id} cancelled for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel algo order {algo_id} for {symbol}: {e}")
            return False
    
    def cancel_all_stop_loss_orders(self, symbol: str) -> bool:
        """
        Cancel all stop loss orders for a symbol
        This cancels both regular orders and conditional (algo) orders
        It will retry until all stop loss orders are confirmed cancelled
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful (all stop loss orders cancelled)
        """
        try:
            import time
            max_retries = 3
            cancelled_count = 0
            
            for attempt in range(max_retries):
                cancelled_count = 0
                
                # Cancel regular stop loss orders
                orders = self.get_open_orders(symbol)
                if orders:
                    for order in orders:
                        # Check if it's a stop loss order (STOP_MARKET type and reduceOnly=True)
                        # and NOT a conditional order (no algoId)
                        if (order.get('type') == 'STOP_MARKET' and
                            order.get('reduceOnly', False) and
                            'algoId' not in order):
                            order_id = order.get('orderId')
                            if order_id:
                                if self.cancel_order(symbol, order_id):
                                    cancelled_count += 1
                
                # Cancel conditional stop loss orders
                algo_orders = self.get_open_algo_orders(symbol)
                if algo_orders:
                    for order in algo_orders:
                        if (order.get('orderType') == 'STOP_MARKET' and
                            order.get('reduceOnly', False) and
                            order.get('algoStatus') == 'NEW'):
                            algo_id = order.get('algoId')
                            if algo_id:
                                if self.cancel_algo_order(symbol, algo_id):
                                    cancelled_count += 1
                
                if cancelled_count > 0:
                    logger.info(f"Cancelled {cancelled_count} stop loss order(s) for {symbol} (attempt {attempt + 1}/{max_retries})")
                    # Wait for cancellation to be processed
                    time.sleep(0.5)
                
                # Verify that all stop loss orders are cancelled
                still_has_stop_loss = self.has_stop_loss_order(symbol)
                if not still_has_stop_loss:
                    logger.info(f"✓ Verified: All stop loss orders cancelled for {symbol}")
                    return True
                else:
                    logger.warning(
                        f"Stop loss orders still exist after cancellation (attempt {attempt + 1}/{max_retries})"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(1)
            
            # After all retries, log remaining orders for debugging
            logger.error(f"Failed to cancel all stop loss orders for {symbol} after {max_retries} attempts")
            
            # Log remaining orders
            orders = self.get_open_orders(symbol)
            if orders:
                logger.error(f"Remaining open orders for {symbol}:")
                for order in orders:
                    logger.error(f"  - Order: {order}")
            
            algo_orders = self.get_open_algo_orders(symbol)
            if algo_orders:
                logger.error(f"Remaining algo orders for {symbol}:")
                for order in algo_orders:
                    logger.error(f"  - Algo Order: {order}")
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cancel stop loss orders for {symbol}: {e}")
            return False