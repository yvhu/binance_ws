"""
仓位管理模块
负责跟踪和管理交易仓位
"""

from typing import Optional, Dict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PositionType(Enum):
    """仓位类型"""
    NONE = "NONE"  # 无持仓
    LONG = "LONG"  # 多头
    SHORT = "SHORT"  # 空头


class Position:
    """仓位类"""
    
    def __init__(self, position_type: PositionType, entry_price: float,
                 quantity: float, leverage: int, entry_time: datetime):
        """
        初始化仓位
        
        Args:
            position_type: 仓位类型
            entry_price: 入场价格
            quantity: 数量
            leverage: 杠杆倍数
            entry_time: 入场时间
        """
        self.position_type = position_type
        self.entry_price = entry_price
        self.quantity = quantity
        self.leverage = leverage
        self.entry_time = entry_time
        
        # 止损
        self.stop_loss_price: Optional[float] = None
        self.stop_loss_roi: Optional[float] = None
    
    def calculate_pnl(self, current_price: float) -> Dict:
        """
        计算当前盈亏
        
        Args:
            current_price: 当前价格
            
        Returns:
            盈亏信息字典
        """
        if self.position_type == PositionType.LONG:
            # 多头盈亏
            price_diff = current_price - self.entry_price
            pnl = price_diff * self.quantity
            roi = (price_diff / self.entry_price) * self.leverage
        elif self.position_type == PositionType.SHORT:
            # 空头盈亏
            price_diff = self.entry_price - current_price
            pnl = price_diff * self.quantity
            roi = (price_diff / self.entry_price) * self.leverage
        else:
            pnl = 0
            roi = 0
        
        return {
            'pnl': pnl,
            'roi': roi,
            'current_price': current_price,
            'entry_price': self.entry_price
        }
    
    def should_stop_loss(self, current_price: float) -> bool:
        """
        检查是否应该止损
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否应该止损
        """
        if self.stop_loss_price is None:
            return False
        
        if self.position_type == PositionType.LONG:
            return current_price <= self.stop_loss_price
        elif self.position_type == PositionType.SHORT:
            return current_price >= self.stop_loss_price
        
        return False
    
    def set_stop_loss_by_roi(self, roi: float, current_price: float) -> None:
        """
        根据ROI设置止损价格
        
        Args:
            roi: 止损ROI（负数表示亏损）
            current_price: 当前价格
        """
        self.stop_loss_roi = roi
        
        # 计算止损价格
        price_change = (roi / self.leverage) * self.entry_price
        
        if self.position_type == PositionType.LONG:
            self.stop_loss_price = self.entry_price + price_change
        elif self.position_type == PositionType.SHORT:
            self.stop_loss_price = self.entry_price - price_change
        
        logger.info(f"设置止损: ROI={roi:.2%}, 价格={self.stop_loss_price:.2f}")
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'position_type': self.position_type.value,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'entry_time': self.entry_time.isoformat(),
            'stop_loss_price': self.stop_loss_price,
            'stop_loss_roi': self.stop_loss_roi
        }
    
    def __repr__(self):
        return (f"Position(type={self.position_type.value}, "
                f"entry={self.entry_price:.2f}, "
                f"qty={self.quantity}, "
                f"leverage={self.leverage}x)")


class PositionManager:
    """仓位管理器"""
    
    def __init__(self, stop_loss_roi: float = -0.40):
        """
        初始化仓位管理器
        
        Args:
            stop_loss_roi: 止损ROI（默认-40%）
        """
        self.stop_loss_roi = stop_loss_roi
        self.current_position: Optional[Position] = None
    
    def open_position(self, position_type: PositionType, entry_price: float,
                      quantity: float, leverage: int) -> Position:
        """
        开仓
        
        Args:
            position_type: 仓位类型
            entry_price: 入场价格
            quantity: 数量
            leverage: 杠杆倍数
            
        Returns:
            仓位对象
        """
        # 如果有持仓，先平仓
        if self.current_position is not None:
            logger.warning("已有持仓，先平仓")
            self.close_position(entry_price)
        
        # 创建新仓位
        self.current_position = Position(
            position_type=position_type,
            entry_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            entry_time=datetime.now()
        )
        
        # 设置止损
        self.current_position.set_stop_loss_by_roi(self.stop_loss_roi, entry_price)
        
        logger.info(f"开仓成功: {self.current_position}")
        
        return self.current_position
    
    def close_position(self, current_price: float) -> Optional[Dict]:
        """
        平仓
        
        Args:
            current_price: 当前价格
            
        Returns:
            平仓信息字典
        """
        if self.current_position is None:
            logger.warning("无持仓，无法平仓")
            return None
        
        # 计算盈亏
        pnl_info = self.current_position.calculate_pnl(current_price)
        
        # 记录平仓信息
        close_info = {
            'position_type': self.current_position.position_type.value,
            'entry_price': self.current_position.entry_price,
            'close_price': current_price,
            'pnl': pnl_info['pnl'],
            'roi': pnl_info['roi'],
            'leverage': self.current_position.leverage,
            'entry_time': self.current_position.entry_time.isoformat(),
            'close_time': datetime.now().isoformat()
        }
        
        logger.info(f"平仓成功: ROI={pnl_info['roi']:.2%}, PnL={pnl_info['pnl']:.2f}")
        
        # 清除持仓
        self.current_position = None
        
        return close_info
    
    def get_current_position(self) -> Optional[Position]:
        """
        获取当前持仓
        
        Returns:
            当前持仓对象
        """
        return self.current_position
    
    def has_position(self) -> bool:
        """
        检查是否有持仓
        
        Returns:
            是否有持仓
        """
        return self.current_position is not None
    
    def get_position_type(self) -> Optional[PositionType]:
        """
        获取持仓类型
        
        Returns:
            持仓类型
        """
        if self.current_position is None:
            return None
        return self.current_position.position_type
    
    def check_stop_loss(self, current_price: float) -> bool:
        """
        检查止损
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否应该止损
        """
        if self.current_position is None:
            return False
        
        return self.current_position.should_stop_loss(current_price)
    
    def get_pnl_info(self, current_price: float) -> Optional[Dict]:
        """
        获取当前盈亏信息
        
        Args:
            current_price: 当前价格
            
        Returns:
            盈亏信息字典
        """
        if self.current_position is None:
            return None
        
        return self.current_position.calculate_pnl(current_price)
    
    def __repr__(self):
        return f"PositionManager(has_position={self.has_position()})"