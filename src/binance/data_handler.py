"""
Binance Data Handler
Processes and manages market data from Binance WebSocket
"""

import logging
from typing import Dict, List, Optional
from collections import deque
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class BinanceDataHandler:
    """Handler for processing and storing Binance market data"""
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize data handler
        
        Args:
            max_history: Maximum number of data points to keep in history
        """
        self.max_history = max_history
        
        # Data storage for different symbols and intervals
        self.ticker_data: Dict[str, Dict] = {}
        self.kline_data: Dict[str, deque] = {}
        self.trade_data: Dict[str, deque] = {}
    
    def process_ticker(self, ticker_info: Dict) -> None:
        """
        Process ticker data
        
        Args:
            ticker_info: Ticker information dictionary
        """
        symbol = ticker_info['symbol']
        self.ticker_data[symbol] = ticker_info
        logger.debug(f"Updated ticker data for {symbol}")
    
    def process_kline(self, kline_info: Dict) -> None:
        """
        Process kline (candlestick) data
        
        Args:
            kline_info: Kline information dictionary
        """
        symbol = kline_info['symbol']
        interval = kline_info['interval']
        key = f"{symbol}_{interval}"
        
        if key not in self.kline_data:
            self.kline_data[key] = deque(maxlen=self.max_history)
        
        # Only add closed klines or update the last one if not closed
        if kline_info['is_closed']:
            self.kline_data[key].append(kline_info)
            logger.debug(f"Added closed kline for {symbol} {interval}")
        elif self.kline_data[key]:
            # Update the last kline if it's the same one
            last_kline = self.kline_data[key][-1]
            if last_kline['open_time'] == kline_info['open_time']:
                self.kline_data[key][-1] = kline_info
    
    def process_trade(self, trade_info: Dict) -> None:
        """
        Process trade data
        
        Args:
            trade_info: Trade information dictionary
        """
        symbol = trade_info['symbol']
        
        if symbol not in self.trade_data:
            self.trade_data[symbol] = deque(maxlen=self.max_history)
        
        self.trade_data[symbol].append(trade_info)
        logger.debug(f"Added trade data for {symbol}")
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Get latest ticker data for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Ticker data dictionary or None
        """
        return self.ticker_data.get(symbol)
    
    def get_klines(self, symbol: str, interval: str = '1m', count: Optional[int] = None) -> List[Dict]:
        """
        Get kline data for a symbol and interval
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval (1m, 5m, 15m, etc.)
            count: Number of klines to return (None for all)
            
        Returns:
            List of kline data dictionaries
        """
        key = f"{symbol}_{interval}"
        klines = list(self.kline_data.get(key, []))
        
        if count is not None and count > 0:
            return klines[-count:]
        
        return klines
    
    def get_trades(self, symbol: str, count: Optional[int] = None) -> List[Dict]:
        """
        Get trade data for a symbol
        
        Args:
            symbol: Trading pair symbol
            count: Number of trades to return (None for all)
            
        Returns:
            List of trade data dictionaries
        """
        trades = list(self.trade_data.get(symbol, []))
        
        if count is not None and count > 0:
            return trades[-count:]
        
        return trades
    
    def get_klines_dataframe(self, symbol: str, interval: str = '1m', count: Optional[int] = None) -> pd.DataFrame:
        """
        Get kline data as a pandas DataFrame
        
        Args:
            symbol: Trading pair symbol
            interval: Kline interval
            count: Number of klines to return
            
        Returns:
            DataFrame with kline data
        """
        klines = self.get_klines(symbol, interval, count)
        
        if not klines:
            return pd.DataFrame()
        
        data = {
            'open_time': pd.to_datetime([k['open_time'] for k in klines], unit='ms'),
            'close_time': pd.to_datetime([k['close_time'] for k in klines], unit='ms'),
            'open': [k['open'] for k in klines],
            'high': [k['high'] for k in klines],
            'low': [k['low'] for k in klines],
            'close': [k['close'] for k in klines],
            'volume': [k['volume'] for k in klines],
            'trades': [k['number_of_trades'] for k in klines]
        }
        
        df = pd.DataFrame(data)
        df.set_index('open_time', inplace=True)
        
        return df
    
    def get_price_change(self, symbol: str) -> Optional[float]:
        """
        Get price change percentage for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Price change percentage or None
        """
        ticker = self.get_ticker(symbol)
        if ticker:
            return ticker.get('price_change_percent')
        return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Current price or None
        """
        ticker = self.get_ticker(symbol)
        if ticker:
            return ticker.get('current_price')
        return None
    
    def get_volume(self, symbol: str) -> Optional[float]:
        """
        Get 24h volume for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            24h volume or None
        """
        ticker = self.get_ticker(symbol)
        if ticker:
            return ticker.get('volume')
        return None
    
    def clear_data(self, symbol: Optional[str] = None) -> None:
        """
        Clear stored data
        
        Args:
            symbol: Symbol to clear (None to clear all)
        """
        if symbol:
            self.ticker_data.pop(symbol, None)
            self.trade_data.pop(symbol, None)
            
            # Clear kline data for all intervals
            keys_to_remove = [key for key in self.kline_data.keys() if key.startswith(symbol)]
            for key in keys_to_remove:
                del self.kline_data[key]
        else:
            self.ticker_data.clear()
            self.kline_data.clear()
            self.trade_data.clear()
        
        logger.info(f"Cleared data for {symbol if symbol else 'all symbols'}")