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
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """
        Calculate Average True Range (ATR)
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period (default: 14)
            
        Returns:
            ATR series or None
        """
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            return talib.ATR(high, low, close, timeperiod=period)
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return None
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        """
        Calculate Average Directional Index (ADX) for trend strength
        
        Args:
            df: DataFrame with OHLC data
            period: ADX period (default: 14)
            
        Returns:
            ADX series or None
        """
        try:
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            return talib.ADX(high, low, close, timeperiod=period)
        except Exception as e:
            logger.error(f"Error calculating ADX: {e}")
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
    
    def check_trend_filter(self, df: pd.DataFrame, kline_direction: str, ma_period: int = 20) -> Tuple[bool, Dict]:
        """
        Check if the kline direction aligns with the trend based on MA
        
        Args:
            df: DataFrame with OHLCV data
            kline_direction: 'UP' or 'DOWN'
            ma_period: MA period for trend filter (default: 20)
            
        Returns:
            Tuple of (is_valid, trend_info) where trend_info contains:
            - current_price: Current close price
            - ma_value: MA value
            - ma_direction: 'UP' or 'DOWN' based on MA slope
            - price_vs_ma: 'ABOVE' or 'BELOW'
            - trend_aligned: True if kline direction aligns with trend
        """
        try:
            if df.empty or len(df) < ma_period + 1:
                return False, {'error': 'Not enough data for trend filter'}
            
            # Calculate MA
            ma = self.calculate_ma(df['close'], ma_period)
            if ma is None or len(ma) < 2:
                return False, {'error': 'Failed to calculate MA'}
            
            # Get current price and MA values
            current_price = df['close'].iloc[-1]
            current_ma = ma[-1]
            previous_ma = ma[-2]
            
            # Determine MA direction (slope)
            ma_direction = 'UP' if current_ma > previous_ma else 'DOWN'
            
            # Determine price position relative to MA
            price_vs_ma = 'ABOVE' if current_price > current_ma else 'BELOW'
            
            # Check if kline direction aligns with trend
            # For LONG: kline should be UP, price should be ABOVE MA, MA should be trending UP
            # For SHORT: kline should be DOWN, price should be BELOW MA, MA should be trending DOWN
            trend_aligned = False
            
            if kline_direction == 'UP':
                # Long position: need price above MA and MA trending up
                trend_aligned = (price_vs_ma == 'ABOVE' and ma_direction == 'UP')
            elif kline_direction == 'DOWN':
                # Short position: need price below MA and MA trending down
                trend_aligned = (price_vs_ma == 'BELOW' and ma_direction == 'DOWN')
            
            trend_info = {
                'current_price': current_price,
                'ma_value': current_ma,
                'ma_direction': ma_direction,
                'price_vs_ma': price_vs_ma,
                'trend_aligned': trend_aligned,
                'ma_period': ma_period
            }
            
            logger.info(
                f"Trend filter check: "
                f"direction={kline_direction}, "
                f"price={current_price:.2f}, "
                f"MA{ma_period}={current_ma:.2f}, "
                f"MA_direction={ma_direction}, "
                f"price_vs_MA={price_vs_ma}, "
                f"trend_aligned={trend_aligned}"
            )
            
            return trend_aligned, trend_info
            
        except Exception as e:
            logger.error(f"Error checking trend filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {'error': str(e)}
    
    def check_rsi_filter(self, df: pd.DataFrame, kline_direction: str,
                         rsi_long_max: float = 70, rsi_short_min: float = 30) -> Tuple[bool, Dict]:
        """
        Check if RSI conditions are met for entry
        
        Args:
            df: DataFrame with OHLCV data
            kline_direction: 'UP' or 'DOWN'
            rsi_long_max: Maximum RSI for long entry (default: 70)
            rsi_short_min: Minimum RSI for short entry (default: 30)
            
        Returns:
            Tuple of (is_valid, rsi_info) where rsi_info contains:
            - rsi_value: Current RSI value
            - condition: RSI condition description
        """
        try:
            if df.empty or len(df) < self.rsi_period + 1:
                return False, {'error': 'Not enough data for RSI filter'}
            
            rsi = self.calculate_rsi(df['close'])
            if rsi is None or len(rsi) == 0:
                return False, {'error': 'Failed to calculate RSI'}
            
            rsi_value = float(rsi[-1])
            is_valid = False
            condition = ""
            
            if kline_direction == 'UP':
                # For long: RSI should not be overbought
                is_valid = rsi_value < rsi_long_max
                condition = f"RSI {rsi_value:.2f} < {rsi_long_max} (not overbought)"
            else:  # DOWN
                # For short: RSI should not be oversold
                is_valid = rsi_value > rsi_short_min
                condition = f"RSI {rsi_value:.2f} > {rsi_short_min} (not oversold)"
            
            rsi_info = {
                'rsi_value': rsi_value,
                'condition': condition,
                'is_valid': is_valid
            }
            
            logger.info(
                f"RSI filter check: "
                f"direction={kline_direction}, "
                f"RSI={rsi_value:.2f}, "
                f"condition={condition}, "
                f"valid={is_valid}"
            )
            
            return is_valid, rsi_info
            
        except Exception as e:
            logger.error(f"Error checking RSI filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {'error': str(e)}
    
    def check_macd_filter(self, df: pd.DataFrame, kline_direction: str) -> Tuple[bool, Dict]:
        """
        Check if MACD conditions are met for entry
        
        Args:
            df: DataFrame with OHLCV data
            kline_direction: 'UP' or 'DOWN'
            
        Returns:
            Tuple of (is_valid, macd_info) where macd_info contains:
            - macd_value: Current MACD value
            - signal_value: Current MACD signal value
            - histogram: Current MACD histogram value
            - crossover: Crossover signal if any
            - condition: MACD condition description
        """
        try:
            if df.empty or len(df) < self.macd_slow + self.macd_signal + 1:
                return False, {'error': 'Not enough data for MACD filter'}
            
            macd, signal, hist = self.calculate_macd(df['close'])
            if macd is None or len(macd) < 2:
                return False, {'error': 'Failed to calculate MACD'}
            
            macd_value = float(macd[-1])
            signal_value = float(signal[-1])
            histogram = float(hist[-1])
            
            # Check for crossover
            prev_macd_above = macd[-2] > signal[-2]
            curr_macd_above = macd[-1] > signal[-1]
            
            crossover = None
            if not prev_macd_above and curr_macd_above:
                crossover = 'BULLISH_CROSS'
            elif prev_macd_above and not curr_macd_above:
                crossover = 'BEARISH_CROSS'
            
            is_valid = False
            condition = ""
            
            if kline_direction == 'UP':
                # For long: histogram > 0 OR bullish crossover
                is_valid = (histogram > 0) or (crossover == 'BULLISH_CROSS')
                if histogram > 0:
                    condition = f"MACD histogram {histogram:.4f} > 0 (bullish)"
                elif crossover == 'BULLISH_CROSS':
                    condition = f"MACD bullish crossover detected"
                else:
                    condition = f"MACD histogram {histogram:.4f} <= 0 (bearish)"
            else:  # DOWN
                # For short: histogram < 0 OR bearish crossover
                is_valid = (histogram < 0) or (crossover == 'BEARISH_CROSS')
                if histogram < 0:
                    condition = f"MACD histogram {histogram:.4f} < 0 (bearish)"
                elif crossover == 'BEARISH_CROSS':
                    condition = f"MACD bearish crossover detected"
                else:
                    condition = f"MACD histogram {histogram:.4f} >= 0 (bullish)"
            
            macd_info = {
                'macd_value': macd_value,
                'signal_value': signal_value,
                'histogram': histogram,
                'crossover': crossover,
                'condition': condition,
                'is_valid': is_valid
            }
            
            logger.info(
                f"MACD filter check: "
                f"direction={kline_direction}, "
                f"MACD={macd_value:.4f}, "
                f"Signal={signal_value:.4f}, "
                f"Histogram={histogram:.4f}, "
                f"Crossover={crossover}, "
                f"condition={condition}, "
                f"valid={is_valid}"
            )
            
            return is_valid, macd_info
            
        except Exception as e:
            logger.error(f"Error checking MACD filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {'error': str(e)}
    
    def check_adx_filter(self, df: pd.DataFrame, adx_min_trend: float = 20,
                         adx_sideways: float = 20) -> Tuple[bool, Dict]:
        """
        Check ADX for trend strength and market type
        
        Args:
            df: DataFrame with OHLCV data
            adx_min_trend: Minimum ADX for trend market (default: 20)
            adx_sideways: ADX threshold for sideways market (default: 20)
            
        Returns:
            Tuple of (is_valid, adx_info) where adx_info contains:
            - adx_value: Current ADX value
            - market_type: 'TREND' or 'SIDEWAYS'
            - trend_strength: 'STRONG', 'MODERATE', or 'WEAK'
            - condition: ADX condition description
        """
        try:
            if df.empty or len(df) < 14 + 1:
                return False, {'error': 'Not enough data for ADX filter'}
            
            adx = self.calculate_adx(df, period=14)
            if adx is None or len(adx) == 0:
                return False, {'error': 'Failed to calculate ADX'}
            
            adx_value = float(adx[-1])
            
            # Determine market type and trend strength
            if adx_value >= adx_min_trend:
                market_type = 'TREND'
                if adx_value >= 40:
                    trend_strength = 'STRONG'
                elif adx_value >= 25:
                    trend_strength = 'MODERATE'
                else:
                    trend_strength = 'WEAK'
            else:
                market_type = 'SIDEWAYS'
                trend_strength = 'WEAK'
            
            # For trading, we prefer trend markets but can trade weak trends
            is_valid = adx_value >= adx_sideways
            
            condition = f"ADX {adx_value:.2f}, Market: {market_type}, Strength: {trend_strength}"
            
            adx_info = {
                'adx_value': adx_value,
                'market_type': market_type,
                'trend_strength': trend_strength,
                'condition': condition,
                'is_valid': is_valid
            }
            
            logger.info(
                f"ADX filter check: "
                f"ADX={adx_value:.2f}, "
                f"market_type={market_type}, "
                f"trend_strength={trend_strength}, "
                f"valid={is_valid}"
            )
            
            return is_valid, adx_info
            
        except Exception as e:
            logger.error(f"Error checking ADX filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, {'error': str(e)}
    
    def calculate_signal_strength(self, volume_valid: bool, range_valid: bool, body_valid: bool,
                                  trend_valid: bool, rsi_valid: bool, macd_valid: bool,
                                  adx_valid: bool) -> str:
        """
        Calculate overall signal strength based on all filter conditions
        
        Args:
            volume_valid: Volume condition met
            range_valid: Range condition met
            body_valid: Body condition met
            trend_valid: Trend filter met
            rsi_valid: RSI filter met
            macd_valid: MACD filter met
            adx_valid: ADX filter met
            
        Returns:
            Signal strength: 'STRONG', 'MEDIUM', or 'WEAK'
        """
        # Count valid conditions
        valid_count = sum([volume_valid, range_valid, body_valid, trend_valid, rsi_valid, macd_valid, adx_valid])
        total_count = 7
        
        # Calculate percentage of valid conditions
        valid_percent = valid_count / total_count
        
        # Determine signal strength
        if valid_percent >= 0.85:  # 85% or more conditions met
            return 'STRONG'
        elif valid_percent >= 0.70:  # 70% or more conditions met
            return 'MEDIUM'
        else:
            return 'WEAK'