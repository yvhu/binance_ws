"""
订单管理API
提供统一的订单管理接口
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

from .order_persistence import OrderPersistence
from .order_priority_manager import OrderPriorityManager, OrderPriority, OrderType
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class OrderManagerAPI:
    """订单管理API"""
    
    def __init__(self, config, trading_executor):
        """
        初始化订单管理API
        
        Args:
            config: 配置管理器实例
            trading_executor: 交易执行器实例
        """
        self.config = config
        self.executor = trading_executor
        
        # 初始化子模块
        self.persistence = OrderPersistence()
        self.priority_manager = OrderPriorityManager(config)
        self.performance_monitor = PerformanceMonitor(config)
    
    # ==================== 订单查询接口 ====================
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单信息或None
        """
        try:
            # 从持久化存储获取
            order_info = self.persistence.get_order(order_id)
            
            if order_info:
                # 从交易所获取最新状态
                symbol = order_info.get('symbol', '')
                if symbol:
                    exchange_order = self.executor.get_order_status(symbol, order_id)
                    if exchange_order:
                        # 更新订单状态
                        order_info['exchange_status'] = exchange_order.get('status')
                        order_info['executed_qty'] = float(exchange_order.get('executedQty', 0))
                        order_info['cummulative_quote_qty'] = float(exchange_order.get('cummulativeQuoteQty', 0))
                        order_info['avg_price'] = float(exchange_order.get('avgPrice', 0))
                        order_info['update_time'] = datetime.now().isoformat()
                        
                        # 保存更新后的状态
                        self.persistence.update_order_status(
                            order_id,
                            exchange_order.get('status'),
                            exchange_order
                        )
            
            return order_info
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    def get_orders_by_symbol(self, symbol: str) -> List[Dict]:
        """
        获取指定交易对的所有订单
        
        Args:
            symbol: 交易对
            
        Returns:
            订单列表
        """
        try:
            orders = self.persistence.get_orders_by_symbol(symbol)
            
            # 获取交易所最新状态
            for order in orders:
                order_id = order.get('order_id')
                if order_id:
                    exchange_order = self.executor.get_order_status(symbol, order_id)
                    if exchange_order:
                        order['exchange_status'] = exchange_order.get('status')
                        order['executed_qty'] = float(exchange_order.get('executedQty', 0))
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders for {symbol}: {e}")
            return []
    
    def get_pending_orders(self) -> List[Dict]:
        """
        获取所有待处理订单
        
        Returns:
            待处理订单列表
        """
        try:
            orders = self.persistence.load_pending_orders()
            
            # 过滤出真正待处理的订单
            pending = []
            for order in orders:
                order_id = order.get('order_id')
                symbol = order.get('symbol', '')
                
                if order_id and symbol:
                    exchange_order = self.executor.get_order_status(symbol, order_id)
                    if exchange_order and exchange_order.get('status') in ['NEW', 'PARTIALLY_FILLED']:
                        order['exchange_status'] = exchange_order.get('status')
                        order['executed_qty'] = float(exchange_order.get('executedQty', 0))
                        pending.append(order)
            
            return pending
            
        except Exception as e:
            logger.error(f"Error getting pending orders: {e}")
            return []
    
    def get_order_statistics(self) -> Dict:
        """
        获取订单统计信息
        
        Returns:
            统计信息字典
        """
        try:
            # 从持久化存储获取统计
            stats = self.persistence.get_statistics()
            
            # 从性能监控器获取统计
            perf_report = self.performance_monitor.get_performance_report()
            
            # 合并统计信息
            combined_stats = {
                'persistence_stats': stats,
                'performance_metrics': perf_report,
                'priority_queue_size': self.priority_manager.get_queue_size(),
                'is_queue_full': self.priority_manager.is_queue_full(),
                'timestamp': datetime.now().isoformat()
            }
            
            return combined_stats
            
        except Exception as e:
            logger.error(f"Error getting order statistics: {e}")
            return {}
    
    # ==================== 订单操作接口 ====================
    
    def cancel_order(self, order_id: int, symbol: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            
        Returns:
            是否成功
        """
        try:
            # 从交易所取消订单
            success = self.executor.cancel_order(symbol, order_id)
            
            if success:
                # 从优先级队列移除
                self.priority_manager.remove_order(order_id)
                
                # 更新持久化状态
                self.persistence.update_order_status(order_id, 'CANCELED', {})
                
                # 记录到性能监控
                self.performance_monitor.record_order_execution(
                    order_id=order_id,
                    symbol=symbol,
                    order_type='LIMIT',
                    side='UNKNOWN',
                    quantity=0,
                    price=0,
                    status='CANCELED'
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """
        取消指定交易对的所有订单
        
        Args:
            symbol: 交易对
            
        Returns:
            是否成功
        """
        try:
            # 获取所有待处理订单
            pending_orders = self.get_orders_by_symbol(symbol)
            
            cancelled_count = 0
            for order in pending_orders:
                order_id = order.get('order_id')
                if order_id:
                    if self.cancel_order(order_id, symbol):
                        cancelled_count += 1
            
            return cancelled_count > 0
            
        except Exception as e:
            logger.error(f"Error cancelling all orders for {symbol}: {e}")
            return False
    
    def modify_order_price(self, order_id: int, symbol: str, new_price: float) -> bool:
        """
        修改订单价格
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            new_price: 新价格
            
        Returns:
            是否成功
        """
        try:
            # 修改订单
            modified_order = self.executor.modify_limit_order_price(symbol, order_id, new_price)
            
            if modified_order:
                # 更新持久化存储
                old_order = self.persistence.get_order(order_id)
                if old_order:
                    old_order['order_price'] = new_price
                    old_order['update_time'] = datetime.now().isoformat()
                    self.persistence.update_order_status(order_id, 'MODIFIED', modified_order)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error modifying order {order_id} price: {e}")
            return False
    
    def modify_order_quantity(self, order_id: int, symbol: str, new_quantity: float) -> bool:
        """
        修改订单数量
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            new_quantity: 新数量
            
        Returns:
            是否成功
        """
        try:
            # 修改订单
            modified_order = self.executor.modify_limit_order_quantity(symbol, order_id, new_quantity)
            
            if modified_order:
                # 更新持久化存储
                old_order = self.persistence.get_order(order_id)
                if old_order:
                    old_order['original_quantity'] = new_quantity
                    old_order['update_time'] = datetime.now().isoformat()
                    self.persistence.update_order_status(order_id, 'MODIFIED', modified_order)
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error modifying order {order_id} quantity: {e}")
            return False
    
    # ==================== 优先级管理接口 ====================
    
    def add_order_to_priority_queue(
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
            是否成功
        """
        try:
            success = self.priority_manager.add_order(
                order_id, symbol, order_type, priority, order_info
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error adding order {order_id} to priority queue: {e}")
            return False
    
    def get_next_priority_order(self) -> Optional[Dict]:
        """
        获取下一个最高优先级的订单
        
        Returns:
            订单信息或None
        """
        try:
            return self.priority_manager.get_next_order()
            
        except Exception as e:
            logger.error(f"Error getting next priority order: {e}")
            return None
    
    def get_priority_queue_summary(self) -> str:
        """
        获取优先级队列摘要
        
        Returns:
            队列摘要字符串
        """
        try:
            return self.priority_manager.get_queue_summary()
            
        except Exception as e:
            logger.error(f"Error getting priority queue summary: {e}")
            return "Error getting queue summary"
    
    # ==================== 性能监控接口 ====================
    
    def get_performance_report(self) -> Dict:
        """
        获取性能报告
        
        Returns:
            性能报告字典
        """
        try:
            return self.performance_monitor.get_performance_report()
            
        except Exception as e:
            logger.error(f"Error getting performance report: {e}")
            return {}
    
    def get_optimization_suggestions(self) -> List[str]:
        """
        获取优化建议
        
        Returns:
            优化建议列表
        """
        try:
            return self.performance_monitor.get_optimization_suggestions()
            
        except Exception as e:
            logger.error(f"Error getting optimization suggestions: {e}")
            return []
    
    def get_performance_summary(self) -> str:
        """
        获取性能摘要
        
        Returns:
            性能摘要字符串
        """
        try:
            return self.performance_monitor.get_performance_summary()
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return "Error getting performance summary"
    
    # ==================== 系统管理接口 ====================
    
    def cleanup_old_orders(self, days: int = 7) -> int:
        """
        清理旧订单
        
        Args:
            days: 保留天数
            
        Returns:
            清理的订单数量
        """
        try:
            count = self.persistence.cleanup_old_orders(days)
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up old orders: {e}")
            return 0
    
    def reset_performance_metrics(self) -> None:
        """重置性能指标"""
        try:
            self.performance_monitor.reset_metrics()
            
        except Exception as e:
            logger.error(f"Error resetting performance metrics: {e}")
    
    def get_system_status(self) -> Dict:
        """
        获取系统状态
        
        Returns:
            系统状态字典
        """
        try:
            status = {
                'persistence': {
                    'total_orders': self.persistence.get_statistics().get('total_orders', 0),
                    'pending_orders': len(self.persistence.load_pending_orders())
                },
                'priority_queue': {
                    'size': self.priority_manager.get_queue_size(),
                    'is_full': self.priority_manager.is_queue_full(),
                    'summary': self.priority_manager.get_queue_summary()
                },
                'performance': {
                    'summary': self.performance_monitor.get_performance_summary()
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {}