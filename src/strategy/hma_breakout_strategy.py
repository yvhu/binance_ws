"""
HMA Breakout 策略模块
"""

from typing import Optional, Dict
from datetime import datetime
import logging

from ..data import KlineManager
from ..indicators import HMAIndicator

logger = logging.getLogger(__name__)


class HMABreakoutStrategy:
    """HMA Breakout 策略类"""
    
    def __init__(self, hma1: int, hma2: int, hma3: int):
        """
        初始化HMA Breakout策略
        
        Args:
            hma1: 短期HMA周期
            hma2: 中期HMA周期
            hma3: 长期HMA周期
        """
        self.hma_indicator = HMAIndicator(hma1, hma2, hma3)
        
        # 当前颜色
        self.current_color: Optional[str] = None
        
        # 统计信息
        self.long_signals = 0
        self.short_signals = 0
        self.close_signals = 0
        self.last_signal: Optional[str] = None
    
    def on_kline_close(self, kline_manager: KlineManager) -> Optional[Dict]:
        """
        K线关闭时调用，计算交易信号
        
        Args:
            kline_manager: K线管理器
            
        Returns:
            信号字典，包含信号类型和相关信息
        """
        # 检查是否有足够的数据
        if not kline_manager.is_ready(self.hma_indicator.hma3.period):
            logger.debug("K线数据不足，跳过信号计算")
            return None
        
        # 获取收盘价
        prices = kline_manager.get_close_prices()
        
        # 计算HMA指标
        if not self.hma_indicator.calculate(prices):
            logger.warning("HMA计算失败")
            return None
        
        # 获取当前颜色
        current_color = self.hma_indicator.get_color()
        
        # 检查颜色是否变化
        if current_color != self.current_color:
            self.current_color = current_color
            return self._generate_signal(current_color)
        
        return None
    
    def _generate_signal(self, color: str) -> Optional[Dict]:
        """
        生成交易信号
        
        Args:
            color: 颜色
            
        Returns:
            信号字典
        """
        ma1, ma2, ma3 = self.hma_indicator.get_values()
        
        signal = {
            'timestamp': datetime.now().isoformat(),
            'color': color,
            'ma1': ma1,
            'ma2': ma2,
            'ma3': ma3,
            'signal_type': None
        }
        
        if color == 'GREEN':
            signal['signal_type'] = 'LONG'
            self.long_signals += 1
            self.last_signal = 'LONG'
            logger.info(f"生成多头信号: MA1={ma1:.2f}, MA2={ma2:.2f}, MA3={ma3:.2f}")
        elif color == 'RED':
            signal['signal_type'] = 'SHORT'
            self.short_signals += 1
            self.last_signal = 'SHORT'
            logger.info(f"生成空头信号: MA1={ma1:.2f}, MA2={ma2:.2f}, MA3={ma3:.2f}")
        elif color == 'GRAY':
            signal['signal_type'] = 'CLOSE'
            self.close_signals += 1
            self.last_signal = 'CLOSE'
            logger.info(f"生成平仓信号: MA1={ma1:.2f}, MA2={ma2:.2f}, MA3={ma3:.2f}")
        
        return signal
    
    def get_current_color(self) -> Optional[str]:
        """
        获取当前颜色
        
        Returns:
            当前颜色
        """
        return self.current_color
    
    def __repr__(self):
        return f"HMABreakoutStrategy(current_color={self.current_color})"