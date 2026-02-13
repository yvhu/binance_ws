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
        
        logger.info(f"Trading executor initialized with {self.leverage}x leverage (full position)")
    
    def set_leverage(self, symbol: str) -> bool:
        """
        Set leverage for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if successful
        """
        try:
            self.client.futures_change_leverage(
                leverage=self.leverage,
                symbol=symbol
            )
            logger.info(f"Leverage set to {self.leverage}x for {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            return False
    
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
    
    def calculate_position_size(self, current_price: float) -> Optional[float]:
        """
        Calculate position size based on account balance and percentage
        
        Args:
            current_price: Current price of the asset
            
        Returns:
            Position quantity or None
        """
        balance = self.get_account_balance()
        if balance is None:
            return None
        
        # Calculate position value (100% of balance)
        position_value = balance  # Full position
        
        # Calculate quantity (considering leverage)
        quantity = (position_value * self.leverage) / current_price
        
        logger.info(f"Full position size calculated: {quantity:.4f} (value: {position_value:.2f} USDT)")
        
        return quantity
    
    def open_long_position(self, symbol: str, quantity: float) -> Optional[Dict]:
        """
        Open a long position (BUY)
        
        Args:
            symbol: Trading pair symbol
            quantity: Position quantity
            
        Returns:
            Order result or None
        """
        try:
            # Set leverage first
            self.set_leverage(symbol)
            
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
            quantity: Position quantity
            
        Returns:
            Order result or None
        """
        try:
            # Set leverage first
            self.set_leverage(symbol)
            
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