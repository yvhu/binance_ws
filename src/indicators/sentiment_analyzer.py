"""
Sentiment Analyzer
Fetches and analyzes market sentiment indicators (Fear and Greed Index)
"""

import logging
import aiohttp
from typing import Optional, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyzer for market sentiment indicators"""
    
    def __init__(self):
        """Initialize sentiment analyzer"""
        self.fear_greed_index_url = "https://api.alternative.me/fng/"
        self.last_fear_greed_value: Optional[int] = None
        self.last_fear_greed_timestamp: Optional[int] = None
        self.last_fear_greed_classification: Optional[str] = None
    
    async def get_fear_greed_index(self) -> Optional[Dict]:
        """
        Get the current Fear and Greed Index from Alternative.me API
        
        Returns:
            Dictionary containing:
            - value: Fear and Greed Index value (0-100)
            - classification: Text classification (e.g., "Extreme Fear", "Greed")
            - timestamp: Unix timestamp
            Or None if request fails
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.fear_greed_index_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'data' in data and len(data['data']) > 0:
                            fng_data = data['data'][0]
                            value = int(fng_data.get('value', 50))
                            classification = fng_data.get('value_classification', 'Neutral')
                            timestamp = int(fng_data.get('timestamp', 0))
                            
                            # Cache the latest value
                            self.last_fear_greed_value = value
                            self.last_fear_greed_timestamp = timestamp
                            self.last_fear_greed_classification = classification
                            
                            logger.info(
                                f"[SENTIMENT] Fear and Greed Index: {value} ({classification}), "
                                f"timestamp: {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                            
                            return {
                                'value': value,
                                'classification': classification,
                                'timestamp': timestamp
                            }
                        else:
                            logger.warning("No data in Fear and Greed Index response")
                            return None
                    else:
                        logger.error(f"Failed to fetch Fear and Greed Index: HTTP {response.status}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching Fear and Greed Index: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Fear and Greed Index: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_cached_fear_greed_index(self) -> Optional[Dict]:
        """
        Get the cached Fear and Greed Index value
        
        Returns:
            Dictionary containing cached value, classification, and timestamp
            Or None if no cached value exists
        """
        if self.last_fear_greed_value is not None:
            return {
                'value': self.last_fear_greed_value,
                'classification': self.last_fear_greed_classification,
                'timestamp': self.last_fear_greed_timestamp
            }
        return None
    
    def check_sentiment_filter(self, kline_direction: str, 
                               min_fear: int = 25, max_greed: int = 75,
                               min_greed: int = 56, max_fear: int = 44) -> Tuple[bool, Optional[Dict]]:
        """
        Check if sentiment conditions are met for entry
        
        Args:
            kline_direction: 'UP' (LONG) or 'DOWN' (SHORT)
            min_fear: Minimum fear level to allow long entry (default: 25)
            max_greed: Maximum greed level to allow long entry (default: 75)
            min_greed: Minimum greed level to allow short entry (default: 56)
            max_fear: Maximum fear level to allow short entry (default: 44)
            
        Returns:
            Tuple of (is_valid, sentiment_info) where sentiment_info contains:
            - value: Fear and Greed Index value
            - classification: Text classification
            - is_valid: Whether sentiment condition is met
            - reason: Reason if not valid
        """
        try:
            # Get cached Fear and Greed Index
            fng_data = self.get_cached_fear_greed_index()
            
            if fng_data is None:
                logger.warning("No Fear and Greed Index data available, skipping sentiment filter")
                return True, None
            
            value = fng_data['value']
            classification = fng_data['classification']
            
            is_valid = True
            reason = None
            
            if kline_direction == 'UP':
                # For LONG entry: sentiment should not be too greedy
                # Allow entry when sentiment is in fear or neutral range
                if value > max_greed:
                    is_valid = False
                    reason = f"Sentiment too greedy ({value} > {max_greed}) for LONG entry"
                    logger.warning(f"[SENTIMENT] {reason}")
                else:
                    pass
            else:  # DOWN
                # For SHORT entry: sentiment should not be too fearful
                # Allow entry when sentiment is in greed or neutral range
                if value < min_greed:
                    is_valid = False
                    reason = f"Sentiment too fearful ({value} < {min_greed}) for SHORT entry"
                    logger.warning(f"[SENTIMENT] {reason}")
                else:
                    pass
            
            sentiment_info = {
                'value': value,
                'classification': classification,
                'is_valid': is_valid,
                'reason': reason
            }
            
            return is_valid, sentiment_info
            
        except Exception as e:
            logger.error(f"Error checking sentiment filter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return True, None
    
    def get_sentiment_emoji(self, value: int) -> str:
        """
        Get emoji for sentiment value
        
        Args:
            value: Fear and Greed Index value (0-100)
            
        Returns:
            Emoji representing the sentiment
        """
        if value <= 24:
            return "😱"  # Extreme Fear
        elif value <= 44:
            return "😰"  # Fear
        elif value <= 55:
            return "😐"  # Neutral
        elif value <= 75:
            return "😊"  # Greed
        else:
            return "🤑"  # Extreme Greed