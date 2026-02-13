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
        self.position_size_percent = 100  # Full position (100% of account balance)
        
        # Trading configuration
        self.fee_rate = config.get_config("trading", "fee_rate", default=0.0004)  # 0.04% for market orders
        self.safety_margin = config.get_config("trading", "safety_margin", default=0.01)  # 1% safety margin
        
        # Cache for leverage settings
        self.leverage_cache = set()  # Track symbols with leverage already set
        
        logger.info(
            f"Trading executor initialized with {self.leverage}x leverage (full position), "
            f"fee_rate={self.fee_rate:.4f}, safety_margin={self.safety_margin:.4f}"
        )
        
        # Initialize leverage for all configured symbols
        self._initialize_leverage()
    
    def _initialize_leverage(self) -> None:
        """Initialize leverage for all configured symbols"""
        symbols = self.config.binance_symbols
        
        logger.info(f"Initializing leverage for {len(symbols)} symbol(s)...")
        
        for symbol in symbols:
            success = self.set_leverage(symbol)
            if success:
                self.leverage_cache.add(symbol)
                logger.info(f"✓ Leverage {self.leverage}x set for {symbol}")
            else:
                logger.error(f"✗ Failed to set leverage for {symbol}")
        
        logger.info(f"Leverage initialization complete. Set for {len(self.leverage_cache)}/{len(symbols)} symbols")
    
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
    
    def get_account_balance(self) -> Optional[float]:
        """
        Get available USDT balance
        
        Returns:
            Available balance or None
        """
        try:
            account = self.client.futures_account()
            balance = float(account['availableBalance'])
            logger.info(f"Available balance: {balance} USDT")
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
            
            # Round down to step size
            rounded_qty = int(quantity / step_size) * step_size
            
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
            
            logger.debug(
                f"Quantity rounded: {quantity:.6f} -> {rounded_qty:.6f} "
                f"(step: {step_size:.6f}, min: {min_qty:.6f}, max: {max_qty:.6f})"
            )
            
            return rounded_qty
            
        except Exception as e:
            logger.error(f"Error rounding quantity for {symbol}: {e}")
            return None
    
    def calculate_position_size(self, current_price: float, symbol: str = "BTCUSDT") -> Optional[float]:
        """
        Calculate position size based on account balance, fees, and safety margin
        
        Args:
            current_price: Current price of the asset
            symbol: Trading pair symbol (default: BTCUSDT)
            
        Returns:
            Position quantity or None
        """
        balance = self.get_account_balance()
        if balance is None:
            return None
        
        # Calculate position value (100% of balance)
        position_value = balance  # Full position
        
        # Calculate total cost including fees and safety margin
        # Total cost = Position value + Opening fee + Closing fee + Safety margin
        # Opening fee = Position value * fee_rate
        # Closing fee = Position value * fee_rate (estimated)
        # Safety margin = Position value * safety_margin
        
        opening_fee = position_value * self.fee_rate
        closing_fee = position_value * self.fee_rate  # Estimated
        safety_margin_amount = position_value * self.safety_margin
        
        total_cost = position_value + opening_fee + closing_fee + safety_margin_amount
        
        # Calculate quantity (considering leverage)
        # Quantity = Total cost * Leverage / Current price
        quantity = (total_cost * self.leverage) / current_price
        
        logger.info(
            f"Position size calculated:\n"
            f"  Balance: {balance:.2f} USDT\n"
            f"  Position value: {position_value:.2f} USDT\n"
            f"  Opening fee: {opening_fee:.4f} USDT ({self.fee_rate*100:.2f}%)\n"
            f"  Closing fee (est): {closing_fee:.4f} USDT\n"
            f"  Safety margin: {safety_margin_amount:.4f} USDT ({self.safety_margin*100:.1f}%)\n"
            f"  Total cost: {total_cost:.2f} USDT\n"
            f"  Raw quantity: {quantity:.6f} BTC\n"
            f"  Leverage: {self.leverage}x"
        )
        
        # Round quantity to match symbol precision
        rounded_quantity = self.round_quantity(quantity, symbol)
        if rounded_quantity is None:
            logger.error(f"Failed to round quantity for {symbol}")
            return None
        
        logger.info(f"Final quantity after rounding: {rounded_quantity:.6f} BTC")
        
        return rounded_quantity
    
    def open_long_position(self, symbol: str, quantity: float) -> Optional[Dict]:
        """
        Open a long position (BUY)
        
        Args:
            symbol: Trading pair symbol
            quantity: Position quantity (already rounded)
            
        Returns:
            Order result or None
        """
        try:
            # Ensure leverage is set (only if not already cached)
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # Place market order
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"Long position opened for {symbol}: {order}")
            return order
            
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
            Order result or None
        """
        try:
            # Ensure leverage is set (only if not already cached)
            if not self.ensure_leverage(symbol):
                logger.error(f"Failed to ensure leverage for {symbol}")
                return None
            
            # Place market order
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"Short position opened for {symbol}: {order}")
            return order
            
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
            
            # Place market order to close
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                reduceOnly=True
            )
            
            logger.info(f"Long position closed for {symbol}: {order}")
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
            
            # Place market order to close
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
                reduceOnly=True
            )
            
            logger.info(f"Short position closed for {symbol}: {order}")
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
    
    def close_all_positions(self, symbol: str) -> bool:
        """
        Close all positions for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        try:
            position = self.get_position(symbol)
            if not position:
                logger.info(f"No positions to close for {symbol}")
                return True
            
            position_amt = float(position['positionAmt'])
            
            if position_amt > 0:
                # Close long position
                self.close_long_position(symbol)
            elif position_amt < 0:
                # Close short position
                self.close_short_position(symbol)
            
            logger.info(f"All positions closed for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close all positions for {symbol}: {e}")
            return False