"""
Technical Analyzer
Calculates technical indicators using TA-Lib
"""
import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import talib
from datetime import datetime

logger = logging.getLogger(__name__)

import logging
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import talib

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Technical analyzer for calculating trading indicators"""
    
    def __init__(self, config: Dict):
        """
        Initialize technical analyzer
        
        Args:
            config: Indicators configuration dictionary
        """
        self.config = config
        
        # Load indicator parameters from config
        self.ma_periods = config.get('ma_periods', [7, 25, 99])
        self.rsi_period = config.get('rsi_period', 14)
        self.rsi_overbought = config.get('rsi_overbought', 70)
        self.rsi_oversold = config.get('rsi_oversold', 30)
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        self.bb_period = config.get('bb_period', 20)
        self.bb_std = config.get('bb_std', 2)
        self.sar_acceleration = config.get('sar_acceleration', 0.02)
        self.sar_maximum = config.get('sar_maximum', 0.2)
        self.sar_history_count = config.get('sar_history_count', 50)
        
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Calculate all configured indicators
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary of indicator series
        """
        if df.empty or len(df) < max(self.ma_periods + [self.rsi_period, self.macd_slow, self.bb_period]):
            logger.warning("Not enough data to calculate indicators")
            return {}
        
        indicators = {}
        
        # Calculate Moving Averages
        for period in self.ma_periods:
            ma = self.calculate_ma(df['close'], period)
            if ma is not None:
                indicators[f'MA{period}'] = ma
        
        # Calculate RSI
        rsi = self.calculate_rsi(df['close'])
        if rsi is not None:
            indicators['RSI'] = rsi
        
        # Calculate MACD
        macd, macd_signal, macd_hist = self.calculate_macd(df['close'])
        if macd is not None:
            indicators['MACD'] = macd
            indicators['MACD_Signal'] = macd_signal
            indicators['MACD_Hist'] = macd_hist
        
        # Calculate Bollinger Bands
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df['close'])
        if bb_upper is not None:
            indicators['BB_Upper'] = bb_upper
            indicators['BB_Middle'] = bb_middle
            indicators['BB_Lower'] = bb_lower
        
        # Calculate additional indicators
        indicators['EMA_12'] = self.calculate_ema(df['close'], 12)
        indicators['EMA_26'] = self.calculate_ema(df['close'], 26)
        
        # Calculate ATR (Average True Range)
        atr = self.calculate_atr(df)
        if atr is not None:
            indicators['ATR'] = atr
        
        # Calculate Stochastic Oscillator
        slowk, slowd = self.calculate_stochastic(df)
        if slowk is not None:
            indicators['Stoch_K'] = slowk
            indicators['Stoch_D'] = slowd
        
        return indicators
    
    def calculate_ma(self, prices: pd.Series, period: int) -> Optional[pd.Series]:
        """
        Calculate Simple Moving Average (SMA)
        
        Args:
            prices: Price series
            period: MA period
            
        Returns:
            MA series or None
        """
        try:
            return talib.SMA(prices.values, timeperiod=period)
        except Exception as e:
            logger.error(f"Error calculating MA{period}: {e}")
            return None
    
    def calculate_ema(self, prices: pd.Series, period: int) -> Optional[pd.Series]:
        """
        Calculate Exponential Moving Average (EMA)
        
        Args:
            prices: Price series
            period: EMA period
            
        Returns:
            EMA series or None
        """
        try:
            return talib.EMA(prices.values, timeperiod=period)
        except Exception as e:
            logger.error(f"Error calculating EMA{period}: {e}")
            return None
    
    def calculate_rsi(self, prices: pd.Series) -> Optional[pd.Series]:
        """
        Calculate Relative Strength Index (RSI)
        
        Args:
            prices: Price series
            
        Returns:
            RSI series or None
        """
        try:
            return talib.RSI(prices.values, timeperiod=self.rsi_period)
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return None
    
    def calculate_macd(self, prices: pd.Series) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
        """
        Calculate MACD (Moving Average Convergence Divergence)
        
        Args:
            prices: Price series
            
        Returns:
            Tuple of (MACD, Signal, Histogram) series or (None, None, None)
        """
        try:
            macd, signal, hist = talib.MACD(
                prices.values,
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            return macd, signal, hist
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return None, None, None
    
    def calculate_bollinger_bands(self, prices: pd.Series) -> Tuple[Optional[pd.Series], Optional[pd.Series], Optional[pd.Series]]:
        """
        Calculate Bollinger Bands
        
        Args:
            prices: Price series
            
        Returns:
            Tuple of (Upper, Middle, Lower) bands or (None, None, None)
        """
        try:
            upper, middle, lower = talib.BBANDS(
                prices.values,
                timeperiod=self.bb_period,
                nbdevup=self.bb_std,
                nbdevdn=self.bb_std
            )
            return upper, middle, lower
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return None, None, None
    
    def calculate_atr(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Calculate Average True Range (ATR)
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            ATR series or None
        """
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            return talib.ATR(high, low, close, timeperiod=14)
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None
    
    def calculate_stochastic(self, df: pd.DataFrame) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
        """
        Calculate Stochastic Oscillator
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Tuple of (SlowK, SlowD) series or (None, None)
        """
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            slowk, slowd = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3)
            return slowk, slowd
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return None, None
    
    def calculate_sar(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Calculate Parabolic SAR (Stop and Reverse)
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            SAR series or None
        """
        try:
            high = df['high'].values
            low = df['low'].values
            return talib.SAR(high, low, acceleration=self.sar_acceleration, maximum=self.sar_maximum)
        except Exception as e:
            logger.error(f"Error calculating SAR: {e}")
            return None
    
    def get_sar_direction(self, df: pd.DataFrame) -> Optional[str]:
        """
        Get SAR direction based on current price vs SAR value
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            'UP' if price > SAR (bullish), 'DOWN' if price < SAR (bearish), or None
        """
        try:
            sar = self.calculate_sar(df)
            if sar is None or len(sar) == 0:
                return None
            
            current_price = df['close'].iloc[-1]
            current_sar = sar[-1]
            
            if current_price > current_sar:
                return 'UP'
            elif current_price < current_sar:
                return 'DOWN'
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error determining SAR direction: {e}")
            return None
    
    def get_sar_value(self, df: pd.DataFrame) -> Optional[float]:
        """
        Get current SAR value
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Current SAR value or None
        """
        try:
            sar = self.calculate_sar(df)
            if sar is None or len(sar) == 0:
                return None
            
            return float(sar[-1])
                
        except Exception as e:
            logger.error(f"Error getting SAR value: {e}")
            return None
    
    def get_latest_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Get latest values of all indicators
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary of latest indicator values
        """
        indicators = self.calculate_all_indicators(df)
        latest = {}
        
        for name, series in indicators.items():
            if series is not None and len(series) > 0:
                latest[name] = float(series[-1])
        
        return latest
    
    def analyze_trend(self, df: pd.DataFrame) -> str:
        """
        Analyze trend based on moving averages
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Trend direction (UPTREND, DOWNTREND, SIDEWAYS)
        """
        if len(self.ma_periods) < 2:
            return "SIDEWAYS"
        
        indicators = self.calculate_all_indicators(df)
        
        if not indicators:
            return "SIDEWAYS"
        
        # Get the two shortest MA periods
        sorted_periods = sorted(self.ma_periods)
        ma_short = f'MA{sorted_periods[0]}'
        ma_long = f'MA{sorted_periods[1]}'
        
        if ma_short in indicators and ma_long in indicators:
            short_ma = indicators[ma_short][-1]
            long_ma = indicators[ma_long][-1]
            
            if short_ma > long_ma:
                return "UPTREND"
            elif short_ma < long_ma:
                return "DOWNTREND"
        
        return "SIDEWAYS"
    
    def check_rsi_signals(self, df: pd.DataFrame) -> Optional[str]:
        """
        Check RSI for overbought/oversold signals
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Signal (OVERBOUGHT, OVERSOLD, NEUTRAL) or None
        """
        indicators = self.calculate_all_indicators(df)
        
        if 'RSI' not in indicators:
            return None
        
        rsi = indicators['RSI'][-1]
        
        if rsi >= self.rsi_overbought:
            return "OVERBOUGHT"
        elif rsi <= self.rsi_oversold:
            return "OVERSOLD"
        else:
            return "NEUTRAL"
    
    def check_macd_crossover(self, df: pd.DataFrame) -> Optional[str]:
        """
        Check for MACD crossover signals
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Signal (BULLISH_CROSS, BEARISH_CROSS, NO_CROSS) or None
        """
        indicators = self.calculate_all_indicators(df)
        
        if 'MACD' not in indicators or 'MACD_Signal' not in indicators:
            return None
        
        macd = indicators['MACD']
        signal = indicators['MACD_Signal']
        
        if len(macd) < 2:
            return None
        
        # Check for crossover
        prev_macd_above = macd[-2] > signal[-2]
        curr_macd_above = macd[-1] > signal[-1]
        
        if not prev_macd_above and curr_macd_above:
            return "BULLISH_CROSS"
        elif prev_macd_above and not curr_macd_above:
            return "BEARISH_CROSS"
        
        return "NO_CROSS"
    
    def generate_trading_signal(self, df: pd.DataFrame, buy_threshold: float = 0.7, sell_threshold: float = 0.3) -> Optional[str]:
        """
        Generate trading signal based on multiple indicators
        
        Args:
            df: DataFrame with OHLCV data
            buy_threshold: Threshold for buy signal (0-1)
            sell_threshold: Threshold for sell signal (0-1)
            
        Returns:
            Signal (BUY, SELL, HOLD) or None
        """
        if df.empty or len(df) < 50:
            return None
        
        indicators = self.calculate_all_indicators(df)
        
        if not indicators:
            return None
        
        score = 0
        total_signals = 0
        
        # Trend analysis
        trend = self.analyze_trend(df)
        if trend == "UPTREND":
            score += 1
        elif trend == "DOWNTREND":
            score -= 1
        total_signals += 1
        
        # RSI signal
        rsi_signal = self.check_rsi_signals(df)
        if rsi_signal == "OVERSOLD":
            score += 1
        elif rsi_signal == "OVERBOUGHT":
            score -= 1
        total_signals += 1
        
        # MACD crossover
        macd_signal = self.check_macd_crossover(df)
        if macd_signal == "BULLISH_CROSS":
            score += 1
        elif macd_signal == "BEARISH_CROSS":
            score -= 1
        total_signals += 1
        
        # Price vs Bollinger Bands
        if 'BB_Upper' in indicators and 'BB_Lower' in indicators:
            current_price = df['close'].iloc[-1]
            bb_upper = indicators['BB_Upper'][-1]
            bb_lower = indicators['BB_Lower'][-1]
            
            if current_price < bb_lower:
                score += 1
            elif current_price > bb_upper:
                score -= 1
            total_signals += 1
        
        # Calculate signal strength
        if total_signals > 0:
            signal_strength = (score + total_signals) / (2 * total_signals)
            
            if signal_strength >= buy_threshold:
                return "BUY"
            elif signal_strength <= sell_threshold:
                return "SELL"
        
        return "HOLD"
    
    def get_indicator_summary(self, df: pd.DataFrame) -> Dict:
        """
        Get a summary of all indicators and their current state
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with indicator summary
        """
        latest = self.get_latest_indicators(df)
        
        summary = {
            'trend': self.analyze_trend(df),
            'rsi_signal': self.check_rsi_signals(df),
            'macd_signal': self.check_macd_crossover(df),
            'trading_signal': self.generate_trading_signal(df),
            'indicators': latest
        }
        
        return summary
    
    def get_kline_direction(self, kline_info: Dict) -> Optional[str]:
        """
        Get K-line direction based on open and close prices
        
        Args:
            kline_info: K-line information dictionary
            
        Returns:
            'UP' if close > open, 'DOWN' if close < open, or None
        """
        try:
            open_price = kline_info.get('open', 0)
            close_price = kline_info.get('close', 0)
            
            if open_price == 0 or close_price == 0:
                return None
            
            if close_price > open_price:
                return 'UP'
            elif close_price < open_price:
                return 'DOWN'
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error determining K-line direction: {e}")
            return None