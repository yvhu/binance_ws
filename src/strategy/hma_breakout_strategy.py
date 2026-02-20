"""
HMA Breakout 策略模块
"""

from typing import Optional, Dict, List
from datetime import datetime
import logging
import time

from ..data import KlineManager
from ..indicators import HMAIndicator

logger = logging.getLogger(__name__)


class SignalConfirmation:
    """信号确认类"""
    
    def __init__(self, signal_type: str, color: str, timestamp: float):
        """
        初始化信号确认
        
        Args:
            signal_type: 信号类型 (LONG/SHORT/CLOSE)
            color: 颜色
            timestamp: 时间戳
        """
        self.signal_type = signal_type
        self.color = color
        self.timestamp = timestamp
        self.confirmations: List[float] = []  # 确认时间点列表
        self.is_confirmed = False
    
    def add_confirmation(self, timestamp: float) -> None:
        """添加确认"""
        self.confirmations.append(timestamp)
        logger.info(f"信号确认: {self.signal_type} 确认次数={len(self.confirmations)}")
    
    def get_confirmation_count(self) -> int:
        """获取确认次数"""
        return len(self.confirmations)


class HMABreakoutStrategy:
    """HMA Breakout 策略类"""
    
    def __init__(self, hma1: int, hma2: int, hma3: int,
                 confirmation_enabled: bool = True,
                 confirmation_times: List[int] = [30, 60],
                 required_confirmations: int = 2):
        """
        初始化HMA Breakout策略
        
        Args:
            hma1: 短期HMA周期
            hma2: 中期HMA周期
            hma3: 长期HMA周期
            confirmation_enabled: 是否启用信号确认
            confirmation_times: 确认时间点（秒）
            required_confirmations: 需要的确认次数
        """
        self.hma_indicator = HMAIndicator(hma1, hma2, hma3)
        
        # 当前颜色
        self.current_color: Optional[str] = None
        
        # 统计信息
        self.long_signals = 0
        self.short_signals = 0
        self.close_signals = 0
        self.last_signal: Optional[str] = None
        
        # 信号确认配置
        self.confirmation_enabled = confirmation_enabled
        self.confirmation_times = confirmation_times
        self.required_confirmations = required_confirmations
        
        # 待确认的信号
        self.pending_confirmation: Optional[SignalConfirmation] = None
    
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
            # 颜色反转
            self.current_color = current_color
            
            # 如果启用了信号确认，创建待确认信号
            if self.confirmation_enabled:
                signal = self._generate_signal(current_color, is_color_changed=True)
                if signal and signal['signal_type'] in ['LONG', 'SHORT']:
                    # 创建待确认信号
                    self.pending_confirmation = SignalConfirmation(
                        signal_type=signal['signal_type'],
                        color=current_color,
                        timestamp=time.time()
                    )
                    logger.info(f"信号反转，等待确认: {signal['signal_type']}")
                    return None  # 不立即返回信号，等待确认
                else:
                    # CLOSE信号不需要确认
                    return signal
            else:
                # 未启用确认，直接返回信号
                return self._generate_signal(current_color, is_color_changed=True)
        else:
            # 颜色未变，只检查是否需要平仓
            if current_color == 'GRAY':
                return self._generate_signal(current_color, is_color_changed=False)
        
        return None
    
    def check_signal_confirmation(self, kline_manager: KlineManager) -> Optional[Dict]:
        """
        检查信号确认
        
        Args:
            kline_manager: K线管理器
            
        Returns:
            确认后的信号字典，如果未确认则返回None
        """
        if not self.confirmation_enabled or self.pending_confirmation is None:
            return None
        
        current_time = time.time()
        elapsed_time = current_time - self.pending_confirmation.timestamp
        
        # 检查是否到达确认时间点
        for confirmation_time in self.confirmation_times:
            # 检查是否在确认时间点的容差范围内（±5秒）
            if abs(elapsed_time - confirmation_time) <= 5:
                # 重新计算当前颜色
                prices = kline_manager.get_close_prices()
                if not self.hma_indicator.calculate(prices):
                    logger.warning("HMA计算失败，无法确认信号")
                    return None
                
                current_color = self.hma_indicator.get_color()
                
                # 检查颜色是否仍然一致
                if current_color == self.pending_confirmation.color:
                    # 颜色一致，添加确认
                    self.pending_confirmation.add_confirmation(current_time)
                    
                    # 检查是否达到确认次数要求
                    if self.pending_confirmation.get_confirmation_count() >= self.required_confirmations:
                        logger.info(f"信号已确认: {self.pending_confirmation.signal_type}")
                        
                        # 生成最终信号
                        signal = self._generate_signal(
                            self.pending_confirmation.color,
                            is_color_changed=True
                        )
                        
                        # 清除待确认信号
                        self.pending_confirmation = None
                        
                        return signal
                else:
                    # 颜色不一致，取消信号
                    logger.info(f"信号取消: 颜色从 {self.pending_confirmation.color} 变为 {current_color}")
                    self.pending_confirmation = None
                    return None
        
        return None
    
    def _generate_signal(self, color: str, is_color_changed: bool) -> Optional[Dict]:
        """
        生成交易信号
        
        Args:
            color: 颜色
            is_color_changed: 颜色是否发生变化
            
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
            'signal_type': None,
            'is_color_changed': is_color_changed
        }
        
        if color == 'GREEN':
            if is_color_changed:
                # 颜色反转，可以开多仓
                signal['signal_type'] = 'LONG'
                self.long_signals += 1
                self.last_signal = 'LONG'
                logger.info(f"生成多头信号（颜色反转）: MA1={ma1:.2f}, MA2={ma2:.2f}, MA3={ma3:.2f}")
            else:
                # 颜色未变，不生成信号
                logger.debug(f"颜色未变（GREEN），不生成信号")
                return None
        elif color == 'RED':
            if is_color_changed:
                # 颜色反转，可以开空仓
                signal['signal_type'] = 'SHORT'
                self.short_signals += 1
                self.last_signal = 'SHORT'
                logger.info(f"生成空头信号（颜色反转）: MA1={ma1:.2f}, MA2={ma2:.2f}, MA3={ma3:.2f}")
            else:
                # 颜色未变，不生成信号
                logger.debug(f"颜色未变（RED），不生成信号")
                return None
        elif color == 'GRAY':
            # 灰色信号，总是平仓
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