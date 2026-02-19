"""
Machine Learning Predictor
Uses machine learning to predict price direction based on technical indicators
"""

import logging
import numpy as np
from typing import Optional, Dict, Tuple, List
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class MLPredictor:
    """Machine learning predictor for price direction"""
    
    def __init__(self):
        """Initialize ML predictor"""
        self.model = None
        self.is_trained = False
        self.feature_columns = [
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'adx', 'ma20', 'ma50', 'volume_ratio', 'range_ratio',
            'body_ratio', 'upper_shadow_ratio', 'lower_shadow_ratio'
        ]
        self.min_samples = 50  # Minimum samples required for training
        self.prediction_window = 5  # Predict price direction for next 5 candles
        
    
    def prepare_features(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Prepare features for ML model
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with features or None if insufficient data
        """
        try:
            if len(df) < 50:
                logger.warning(f"Insufficient data for feature preparation: {len(df)} < 50")
                return None
            
            # Calculate technical indicators
            features = pd.DataFrame()
            
            # RSI
            features['rsi'] = self._calculate_rsi(df['close'], 14)
            
            # MACD
            macd, macd_signal, macd_histogram = self._calculate_macd(df['close'])
            features['macd'] = macd
            features['macd_signal'] = macd_signal
            features['macd_histogram'] = macd_histogram
            
            # ADX
            features['adx'] = self._calculate_adx(df)
            
            # Moving averages
            features['ma20'] = df['close'].rolling(window=20).mean()
            features['ma50'] = df['close'].rolling(window=50).mean()
            
            # Volume ratio
            features['volume_ratio'] = df['volume'] / df['volume'].rolling(window=5).mean()
            
            # Range ratio
            features['range_ratio'] = (df['high'] - df['low']) / (df['high'] - df['low']).rolling(window=5).mean()
            
            # Body ratio
            features['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'])
            
            # Shadow ratios
            features['upper_shadow_ratio'] = (df['high'] - df[['open', 'close']].max(axis=1)) / (df['high'] - df['low'])
            features['lower_shadow_ratio'] = (df[['open', 'close']].min(axis=1) - df['low']) / (df['high'] - df['low'])
            
            # Drop NaN values
            features = features.dropna()
            
            if len(features) < self.min_samples:
                logger.warning(f"Insufficient features after cleaning: {len(features)} < {self.min_samples}")
                return None
            
            return features
            
        except Exception as e:
            logger.error(f"Error preparing features: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def prepare_labels(self, df: pd.DataFrame, features: pd.DataFrame) -> Optional[pd.Series]:
        """
        Prepare labels for ML model (price direction prediction)
        
        Args:
            df: DataFrame with OHLCV data
            features: DataFrame with features
            
        Returns:
            Series with labels (1 for UP, 0 for DOWN) or None
        """
        try:
            # Align features with price data
            # We want to predict if price will go UP or DOWN in the next prediction_window candles
            labels = []
            
            for i in range(len(features)):
                # Get current index in original df
                current_idx = features.index[i]
                
                # Get future price
                future_idx = current_idx + self.prediction_window
                if future_idx >= len(df):
                    labels.append(0)  # Default to DOWN if not enough data
                    continue
                
                current_price = df.loc[current_idx, 'close']
                future_price = df.loc[future_idx, 'close']
                
                # Label: 1 if price goes UP, 0 if price goes DOWN
                if future_price > current_price:
                    labels.append(1)
                else:
                    labels.append(0)
            
            return pd.Series(labels, index=features.index)
            
        except Exception as e:
            logger.error(f"Error preparing labels: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def train_model(self, df: pd.DataFrame) -> bool:
        """
        Train ML model with historical data
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            True if training successful, False otherwise
        """
        try:
            
            # Prepare features
            features = self.prepare_features(df)
            if features is None:
                logger.error("Failed to prepare features")
                return False
            
            # Prepare labels
            labels = self.prepare_labels(df, features)
            if labels is None:
                logger.error("Failed to prepare labels")
                return False
            
            # Use a simple rule-based model for now
            # In production, you would use scikit-learn or TensorFlow
            # For this implementation, we'll use a weighted voting system
            
            self.model = {
                'type': 'weighted_voting',
                'weights': {
                    'rsi': 0.15,
                    'macd': 0.15,
                    'macd_histogram': 0.10,
                    'adx': 0.10,
                    'ma_trend': 0.20,
                    'volume_ratio': 0.10,
                    'range_ratio': 0.10,
                    'body_ratio': 0.10
                },
                'threshold': 0.5  # Prediction threshold
            }
            
            # Calculate feature importance based on historical performance
            self._calculate_feature_importance(features, labels)
            
            self.is_trained = True
            
            return True
            
        except Exception as e:
            logger.error(f"Error training model: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _calculate_feature_importance(self, features: pd.DataFrame, labels: pd.Series) -> None:
        """
        Calculate feature importance based on historical performance
        
        Args:
            features: DataFrame with features
            labels: Series with labels
        """
        try:
            # Simple correlation-based importance
            importance = {}
            
            for col in features.columns:
                if col in self.model['weights']:
                    # Calculate correlation with labels
                    corr = features[col].corr(labels)
                    importance[col] = abs(corr) if not np.isnan(corr) else 0
            
            # Normalize weights
            total = sum(importance.values())
            if total > 0:
                for col in importance:
                    if col in self.model['weights']:
                        self.model['weights'][col] = importance[col] / total
            
            
        except Exception as e:
            logger.error(f"Error calculating feature importance: {e}")
    
    def predict(self, df: pd.DataFrame) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Predict price direction
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Tuple of (prediction, prediction_info) where:
            - prediction: 'UP', 'DOWN', or None
            - prediction_info: Dictionary with prediction details
        """
        try:
            if not self.is_trained or self.model is None:
                logger.warning("ML model not trained, returning neutral prediction")
                return None, None
            
            # Prepare features
            features = self.prepare_features(df)
            if features is None or len(features) == 0:
                logger.warning("Failed to prepare features for prediction")
                return None, None
            
            # Get latest features
            latest_features = features.iloc[-1]
            
            # Calculate prediction score
            score = 0.0
            
            # RSI signal
            rsi = latest_features.get('rsi', 50)
            if rsi < 30:  # Oversold - bullish
                score += self.model['weights'].get('rsi', 0)
            elif rsi > 70:  # Overbought - bearish
                score -= self.model['weights'].get('rsi', 0)
            
            # MACD signal
            macd = latest_features.get('macd', 0)
            macd_signal = latest_features.get('macd_signal', 0)
            if macd > macd_signal:  # Bullish crossover
                score += self.model['weights'].get('macd', 0)
            else:  # Bearish crossover
                score -= self.model['weights'].get('macd', 0)
            
            # MACD histogram
            macd_histogram = latest_features.get('macd_histogram', 0)
            if macd_histogram > 0:  # Bullish momentum
                score += self.model['weights'].get('macd_histogram', 0)
            else:  # Bearish momentum
                score -= self.model['weights'].get('macd_histogram', 0)
            
            # ADX trend strength
            adx = latest_features.get('adx', 0)
            if adx > 25:  # Strong trend
                score += self.model['weights'].get('adx', 0) * 0.5
            
            # MA trend
            ma20 = latest_features.get('ma20', 0)
            ma50 = latest_features.get('ma50', 0)
            current_price = df['close'].iloc[-1]
            if current_price > ma20 > ma50:  # Strong uptrend
                score += self.model['weights'].get('ma_trend', 0)
            elif current_price < ma20 < ma50:  # Strong downtrend
                score -= self.model['weights'].get('ma_trend', 0)
            
            # Volume ratio
            volume_ratio = latest_features.get('volume_ratio', 1)
            if volume_ratio > 1.2:  # High volume - supports current trend
                score += self.model['weights'].get('volume_ratio', 0) * 0.3
            
            # Range ratio
            range_ratio = latest_features.get('range_ratio', 1)
            if range_ratio > 1.2:  # High volatility
                score += self.model['weights'].get('range_ratio', 0) * 0.2
            
            # Body ratio
            body_ratio = latest_features.get('body_ratio', 0.5)
            if body_ratio > 0.6:  # Strong candle
                score += self.model['weights'].get('body_ratio', 0) * 0.3
            
            # Normalize score to 0-1 range
            normalized_score = (score + 1) / 2  # Convert from [-1, 1] to [0, 1]
            
            # Make prediction
            threshold = self.model.get('threshold', 0.5)
            if normalized_score > threshold:
                prediction = 'UP'
            elif normalized_score < (1 - threshold):
                prediction = 'DOWN'
            else:
                prediction = 'NEUTRAL'
            
            prediction_info = {
                'score': normalized_score,
                'confidence': abs(normalized_score - 0.5) * 2,  # Confidence 0-1
                'features': latest_features.to_dict(),
                'threshold': threshold
            }
            
            
            return prediction, prediction_info
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, None
    
    def check_ml_filter(self, kline_direction: str, prediction: Optional[str], 
                        prediction_info: Optional[Dict], min_confidence: float = 0.6) -> Tuple[bool, Optional[Dict]]:
        """
        Check if ML prediction aligns with kline direction
        
        Args:
            kline_direction: 'UP' or 'DOWN'
            prediction: ML prediction ('UP', 'DOWN', or 'NEUTRAL')
            prediction_info: Prediction information dictionary
            min_confidence: Minimum confidence required
            
        Returns:
            Tuple of (is_valid, ml_info) where ml_info contains ML filter details
        """
        try:
            if prediction is None or prediction_info is None:
                logger.warning("ML prediction not available, skipping ML filter")
                return True, None
            
            confidence = prediction_info.get('confidence', 0)
            
            # Check if confidence meets minimum requirement
            if confidence < min_confidence:
                return True, None  # Don't filter, just skip
            
            # Check if prediction aligns with kline direction
            if prediction == 'NEUTRAL':
                return True, None
            
            is_aligned = prediction == kline_direction
            
            ml_info = {
                'prediction': prediction,
                'kline_direction': kline_direction,
                'is_aligned': is_aligned,
                'confidence': confidence,
                'score': prediction_info.get('score', 0),
                'ml_valid': is_aligned
            }
            
            
            return is_aligned, ml_info
            
        except Exception as e:
            logger.error(f"Error checking ML filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return True, None
    
    # Helper methods for technical indicators
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ADX"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx