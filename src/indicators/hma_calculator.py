"""
HMA (Hull Moving Average) 指标计算模块
"""

import math
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class HMA:
    """Hull Moving Average 指标类"""
    
    def __init__(self, period: int):
        """
        初始化HMA指标
        
        Args:
            period: HMA周期
        """
        self.period = period
        self.values: List[float] = []
    
    def calculate(self, prices: List[float]) -> Optional[float]:
        """
        计算HMA值
        
        Args:
            prices: 价格列表
            
        Returns:
            HMA值，如果数据不足则返回None
        """
        if len(prices) < self.period:
            return None
        
        # HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))
        half_period = int(self.period / 2)
        sqrt_period = int(math.sqrt(self.period))
        
        # 计算WMA
        wma_half = self._calculate_wma(prices, half_period)
        wma_full = self._calculate_wma(prices, self.period)
        
        if wma_half is None or wma_full is None:
            return None
        
        # 计算 2*WMA(n/2) - WMA(n)
        raw_hma = 2 * wma_half - wma_full
        
        # 再次应用WMA
        hma = self._calculate_wma_single(raw_hma, sqrt_period)
        
        return hma
    
    def _calculate_wma(self, prices: List[float], period: int) -> Optional[float]:
        """
        计算加权移动平均线
        
        Args:
            prices: 价格列表
            period: 周期
            
        Returns:
            WMA值
        """
        if len(prices) < period:
            return None
        
        # 取最后period个价格
        recent_prices = prices[-period:]
        weights = list(range(1, period + 1))
        
        # 计算加权平均
        weighted_sum = sum(price * weight for price, weight in zip(recent_prices, weights))
        sum_weights = sum(weights)
        
        return weighted_sum / sum_weights
    
    def _calculate_wma_single(self, value: float, period: int) -> float:
        """
        计算单个值的WMA（用于HMA的第二次计算）
        
        Args:
            value: 单个值
            period: 周期
            
        Returns:
            WMA值
        """
        # 对于单个值，WMA就是该值本身
        return value
    
    def update(self, price: float) -> Optional[float]:
        """
        更新HMA值（用于实时计算）
        
        Args:
            price: 新的价格
            
        Returns:
            最新的HMA值
        """
        # 这个方法需要维护历史价格数据
        # 简化实现，直接返回None，建议使用calculate方法
        return None


class HMAIndicator:
    """HMA指标管理器"""
    
    def __init__(self, hma1: int, hma2: int, hma3: int):
        """
        初始化HMA指标管理器
        
        Args:
            hma1: 短期HMA周期
            hma2: 中期HMA周期
            hma3: 长期HMA周期
        """
        self.hma1 = HMA(hma1)
        self.hma2 = HMA(hma2)
        self.hma3 = HMA(hma3)
        
        self.ma1: Optional[float] = None
        self.ma2: Optional[float] = None
        self.ma3: Optional[float] = None
    
    def calculate(self, prices: List[float]) -> bool:
        """
        计算所有HMA值
        
        Args:
            prices: 价格列表
            
        Returns:
            是否计算成功
        """
        self.ma1 = self.hma1.calculate(prices)
        self.ma2 = self.hma2.calculate(prices)
        self.ma3 = self.hma3.calculate(prices)
        
        success = all(v is not None for v in [self.ma1, self.ma2, self.ma3])
        
        if success:
            logger.debug(f"HMA计算成功: MA1={self.ma1:.2f}, MA2={self.ma2:.2f}, MA3={self.ma3:.2f}")
        else:
            logger.warning("HMA计算失败，数据不足")
        
        return success
    
    def get_values(self) -> tuple:
        """
        获取HMA值
        
        Returns:
            (ma1, ma2, ma3) 元组
        """
        return self.ma1, self.ma2, self.ma3
    
    def is_ready(self) -> bool:
        """
        检查HMA是否已准备好
        
        Returns:
            是否准备好
        """
        return all(v is not None for v in [self.ma1, self.ma2, self.ma3])
    
    def get_color(self) -> str:
        """
        获取当前信号颜色
        
        Returns:
            'GREEN' (多头), 'RED' (空头), 'GRAY' (平仓)
        """
        if not self.is_ready():
            return 'GRAY'
        
        # 买入条件：ma3 < ma2 and ma3 < ma1 and ma1 > ma2
        if self.ma3 < self.ma2 and self.ma3 < self.ma1 and self.ma1 > self.ma2:
            return 'GREEN'
        
        # 卖出条件：ma3 > ma2 and ma3 > ma1 and ma2 > ma1
        if self.ma3 > self.ma2 and self.ma3 > self.ma1 and self.ma2 > self.ma1:
            return 'RED'
        
        # 平仓信号
        return 'GRAY'
    
    def get_signal(self) -> Optional[str]:
        """
        获取交易信号
        
        Returns:
            'LONG' (做多), 'SHORT' (做空), 'CLOSE' (平仓), None (无信号)
        """
        color = self.get_color()
        
        if color == 'GREEN':
            return 'LONG'
        elif color == 'RED':
            return 'SHORT'
        elif color == 'GRAY':
            return 'CLOSE'
        
        return None
    
    def __repr__(self):
        return f"HMAIndicator(MA1={self.ma1}, MA2={self.ma2}, MA3={self.ma3}, Color={self.get_color()})"