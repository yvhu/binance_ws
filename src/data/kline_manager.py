"""
K线数据管理模块
负责K线数据的存储、更新和管理
"""

from collections import deque
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class Kline:
    """K线数据类"""
    
    def __init__(self, open_time: int, open_price: float, high: float,
                 low: float, close: float, volume: float, close_time: int,
                 is_closed: bool = False):
        self.open_time = open_time
        self.open_price = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.close_time = close_time
        self.is_closed = is_closed
    
    @classmethod
    def from_binance(cls, data: List) -> 'Kline':
        """从Binance API数据创建K线对象"""
        return cls(
            open_time=int(data[0]),
            open_price=float(data[1]),
            high=float(data[2]),
            low=float(data[3]),
            close=float(data[4]),
            volume=float(data[5]),
            close_time=int(data[6]),
            is_closed=data[8]  # x字段表示K线是否关闭
        )
    
    def __repr__(self):
        return f"Kline(time={datetime.fromtimestamp(self.open_time/1000)}, close={self.close}, closed={self.is_closed})"


class KlineManager:
    """K线数据管理器"""
    
    def __init__(self, max_klines: int = 200):
        """
        初始化K线管理器
        
        Args:
            max_klines: 最大保留的K线数量
        """
        self.max_klines = max_klines
        self.klines = deque(maxlen=max_klines)
        self.current_kline: Optional[Kline] = None
    
    def add_kline(self, kline: Kline) -> None:
        """
        添加K线数据
        
        Args:
            kline: K线对象
        """
        if kline.is_closed:
            # K线已关闭，加入历史数据
            self.klines.append(kline)
            logger.info(f"添加已关闭K线: {kline}")
        else:
            # K线未关闭，更新当前K线
            self.current_kline = kline
            logger.debug(f"更新当前K线: {kline}")
    
    def update_current_kline(self, kline: Kline) -> None:
        """
        更新当前K线数据
        
        Args:
            kline: 新的K线数据
        """
        if self.current_kline is None:
            self.current_kline = kline
        else:
            # 更新当前K线的高低价和收盘价
            self.current_kline.high = max(self.current_kline.high, kline.high)
            self.current_kline.low = min(self.current_kline.low, kline.low)
            self.current_kline.close = kline.close
            self.current_kline.volume = kline.volume
            self.current_kline.close_time = kline.close_time
            self.current_kline.is_closed = kline.is_closed
            
            # 如果K线关闭，加入历史数据
            if kline.is_closed:
                self.klines.append(self.current_kline)
                self.current_kline = None
                logger.info(f"K线关闭并加入历史数据")
    
    def get_close_prices(self, count: Optional[int] = None) -> List[float]:
        """
       获取收盘价列表
        
        Args:
            count: 获取的数量，None表示全部
            
        Returns:
            收盘价列表
        """
        prices = [k.close for k in self.klines]
        if count is not None:
            return prices[-count:]
        return prices
    
    def get_latest_kline(self) -> Optional[Kline]:
        """
        获取最新的K线
        
        Returns:
            最新的K线对象
        """
        if self.current_kline is not None:
            return self.current_kline
        elif len(self.klines) > 0:
            return self.klines[-1]
        return None
    
    def get_kline_count(self) -> int:
        """
        获取K线数量
        
        Returns:
            K线数量
        """
        count = len(self.klines)
        if self.current_kline is not None:
            count += 1
        return count
    
    def is_ready(self, required_count: int) -> bool:
        """
        检查是否有足够的K线数据
        
        Args:
            required_count: 需要的K线数量
            
        Returns:
            是否有足够的数据
        """
        return self.get_kline_count() >= required_count
    
    def __repr__(self):
        return f"KlineManager(klines={len(self.klines)}, current={'yes' if self.current_kline else 'no'})"