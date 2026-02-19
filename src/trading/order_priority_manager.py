"""
订单优先级管理模块
提供订单优先级分配和管理功能
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum
import heapq

logger = logging.getLogger(__name__)


class OrderPriority(Enum):
    """订单优先级枚举"""
    EMERGENCY = 0  # 紧急（止损、紧急平仓）
    HIGH = 1       # 高（止盈、重要信号）
    NORMAL = 2     # 普通（常规开仓）
    LOW = 3        # 低（次要信号）


class OrderType(Enum):
    """订单类型枚举"""
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    ENTRY_LONG = "ENTRY_LONG"
    ENTRY_SHORT = "ENTRY_SHORT"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    EMERGENCY_CLOSE = "EMERGENCY_CLOSE"


class OrderPriorityManager:
    """订单优先级管理器"""
    
    def __init__(self, config):
        """
        初始化订单优先级管理器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        
        # 优先级队列（使用堆结构）
        self.priority_queue = []
        self.order_counter = 0  # 用于保持相同优先级订单的FIFO顺序
        
        # 订单映射（order_id -> order_info）
        self.orders = {}
        
        # 最大挂单数量
        self.max_pending_orders = config.get_config(
            "trading.limit_order", "max_pending_orders", default=1
        )
        
        logger.info(
            f"OrderPriorityManager initialized: "
            f"max_pending_orders={self.max_pending_orders}"
        )
    
    def get_order_priority(
        self,
        order_type: OrderType,
        signal_strength: Optional[float] = None,
        is_urgent: bool = False
    ) -> OrderPriority:
        """
        获取订单优先级
        
        Args:
            order_type: 订单类型
            signal_strength: 信号强度（0-1）
            is_urgent: 是否紧急
            
        Returns:
            订单优先级
        """
        # 紧急订单最高优先级
        if is_urgent or order_type == OrderType.EMERGENCY_CLOSE:
            return OrderPriority.EMERGENCY
        
        # 止损订单高优先级
        if order_type == OrderType.STOP_LOSS:
            return OrderPriority.HIGH
        
        # 止盈订单高优先级
        if order_type == OrderType.TAKE_PROFIT:
            return OrderPriority.HIGH
        
        # 根据信号强度确定优先级
        if signal_strength is not None:
            if signal_strength >= 0.8:
                return OrderPriority.HIGH
            elif signal_strength >= 0.5:
                return OrderPriority.NORMAL
            else:
                return OrderPriority.LOW
        
        # 默认普通优先级
        return OrderPriority.NORMAL
    
    def add_order(
        self,
        order_id: int,
        symbol: str,
        order_type: OrderType,
        priority: OrderPriority,
        order_info: Optional[Dict] = None
    ) -> bool:
        """
        添加订单到优先级队列
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            order_type: 订单类型
            priority: 订单优先级
            order_info: 订单信息
            
        Returns:
            是否添加成功
        """
        try:
            # 检查是否已存在
            if order_id in self.orders:
                logger.warning(f"Order {order_id} already exists in priority queue")
                return False
            
            # 检查挂单数量限制
            if len(self.orders) >= self.max_pending_orders:
                logger.warning(
                    f"Cannot add order {order_id}: "
                    f"max pending orders ({self.max_pending_orders}) reached"
                )
                return False
            
            # 创建订单信息
            order_data = {
                'order_id': order_id,
                'symbol': symbol,
                'order_type': order_type,
                'priority': priority,
                'order_info': order_info or {},
                'created_at': datetime.now(),
                'counter': self.order_counter
            }
            
            # 添加到优先级队列（使用堆结构）
            # 堆元素：(priority, counter, order_id)
            heapq.heappush(
                self.priority_queue,
                (priority.value, self.order_counter, order_id)
            )
            
            # 添加到订单映射
            self.orders[order_id] = order_data
            
            # 增加计数器
            self.order_counter += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding order {order_id} to priority queue: {e}")
            return False
    
    def remove_order(self, order_id: int) -> bool:
        """
        从优先级队列中移除订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            是否移除成功
        """
        try:
            if order_id not in self.orders:
                logger.warning(f"Order {order_id} not found in priority queue")
                return False
            
            # 从订单映射中移除
            order_data = self.orders.pop(order_id)
            
            # 从优先级队列中移除（标记为已删除）
            # 注意：由于堆结构不支持直接删除，我们使用惰性删除
            # 在弹出时检查订单是否仍在映射中
            order_data['deleted'] = True
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing order {order_id} from priority queue: {e}")
            return False
    
    def get_next_order(self) -> Optional[Dict]:
        """
        获取下一个最高优先级的订单
        
        Returns:
            订单信息或None
        """
        try:
            # 清理已删除的订单
            while self.priority_queue:
                priority, counter, order_id = self.priority_queue[0]
                
                # 检查订单是否仍在映射中且未被删除
                if order_id in self.orders and not self.orders[order_id].get('deleted', False):
                    # 找到有效订单
                    heapq.heappop(self.priority_queue)
                    return self.orders[order_id]
                else:
                    # 无效订单，弹出并继续
                    heapq.heappop(self.priority_queue)
            
            # 队列为空
            return None
            
        except Exception as e:
            logger.error(f"Error getting next order from priority queue: {e}")
            return None
    
    def peek_next_order(self) -> Optional[Dict]:
        """
        查看下一个最高优先级的订单（不移除）
        
        Returns:
            订单信息或None
        """
        try:
            # 清理已删除的订单
            while self.priority_queue:
                priority, counter, order_id = self.priority_queue[0]
                
                # 检查订单是否仍在映射中且未被删除
                if order_id in self.orders and not self.orders[order_id].get('deleted', False):
                    # 找到有效订单
                    return self.orders[order_id]
                else:
                    # 无效订单，弹出并继续
                    heapq.heappop(self.priority_queue)
            
            # 队列为空
            return None
            
        except Exception as e:
            logger.error(f"Error peeking next order from priority queue: {e}")
            return None
    
    def get_order_info(self, order_id: int) -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单信息或None
        """
        return self.orders.get(order_id)
    
    def get_all_orders(self) -> List[Dict]:
        """
        获取所有订单（按优先级排序）
        
        Returns:
            订单列表
        """
        try:
            # 创建临时堆来获取排序后的订单
            temp_heap = []
            for priority, counter, order_id in self.priority_queue:
                if order_id in self.orders and not self.orders[order_id].get('deleted', False):
                    temp_heap.append((priority, counter, order_id))
            
            # 排序
            temp_heap.sort()
            
            # 返回订单列表
            return [self.orders[order_id] for _, _, order_id in temp_heap]
            
        except Exception as e:
            logger.error(f"Error getting all orders from priority queue: {e}")
            return []
    
    def get_orders_by_symbol(self, symbol: str) -> List[Dict]:
        """
        获取指定交易对的所有订单
        
        Args:
            symbol: 交易对
            
        Returns:
            订单列表
        """
        try:
            orders = []
            for order_id, order_data in self.orders.items():
                if (order_data['symbol'] == symbol and 
                    not order_data.get('deleted', False)):
                    orders.append(order_data)
            
            # 按优先级排序
            orders.sort(key=lambda x: (x['priority'].value, x['counter']))
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders by symbol {symbol}: {e}")
            return []
    
    def get_orders_by_type(self, order_type: OrderType) -> List[Dict]:
        """
        获取指定类型的所有订单
        
        Args:
            order_type: 订单类型
            
        Returns:
            订单列表
        """
        try:
            orders = []
            for order_id, order_data in self.orders.items():
                if (order_data['order_type'] == order_type and 
                    not order_data.get('deleted', False)):
                    orders.append(order_data)
            
            # 按优先级排序
            orders.sort(key=lambda x: (x['priority'].value, x['counter']))
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders by type {order_type}: {e}")
            return []
    
    def get_queue_size(self) -> int:
        """
        获取队列大小（有效订单数）
        
        Returns:
            队列大小
        """
        return sum(
            1 for order_data in self.orders.values() 
            if not order_data.get('deleted', False)
        )
    
    def is_queue_full(self) -> bool:
        """
        检查队列是否已满
        
        Returns:
            是否已满
        """
        return self.get_queue_size() >= self.max_pending_orders
    
    def clear_queue(self) -> None:
        """清空队列"""
        self.priority_queue.clear()
        self.orders.clear()
    
    def get_queue_summary(self) -> str:
        """
        获取队列摘要
        
        Returns:
            队列摘要字符串
        """
        try:
            total_orders = self.get_queue_size()
            
            if total_orders == 0:
                return "Priority queue is empty"
            
            # 按优先级统计
            priority_counts = {}
            for order_data in self.orders.values():
                if not order_data.get('deleted', False):
                    priority = order_data['priority'].name
                    priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # 按类型统计
            type_counts = {}
            for order_data in self.orders.values():
                if not order_data.get('deleted', False):
                    order_type = order_data['order_type'].value
                    type_counts[order_type] = type_counts.get(order_type, 0) + 1
            
            summary_parts = [
                f"Total orders: {total_orders}/{self.max_pending_orders}",
                f"By priority: {priority_counts}",
                f"By type: {type_counts}"
            ]
            
            return ", ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error getting queue summary: {e}")
            return "Error getting queue summary"