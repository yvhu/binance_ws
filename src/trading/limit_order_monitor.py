"""
Limit Order Monitor
Monitors limit orders and converts to market orders when necessary
"""

import asyncio
import logging
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OrderInfo:
    """订单信息"""
    order_id: int
    symbol: str
    side: str  # 'BUY' or 'SELL'
    order_type: str  # 'ENTRY' or 'TAKE_PROFIT'
    limit_price: float
    quantity: float
    created_at: datetime
    price_history: list  # 价格历史记录
    original_quantity: float  # 原始数量（用于重新下单）


class LimitOrderMonitor:
    """限价单监控器"""
    
    def __init__(self, trading_executor, config):
        """
        初始化限价单监控器
        
        Args:
            trading_executor: TradingExecutor实例
            config: ConfigManager实例
        """
        self.trading_executor = trading_executor
        self.config = config
        
        # 活跃订单
        self.active_orders: Dict[int, OrderInfo] = {}
        
        # 监控任务
        self.monitor_tasks: Dict[int, asyncio.Task] = {}
        
        # 价格回调函数（用于获取实时价格）
        self.get_current_price_callback: Optional[Callable[[str], float]] = None
        
        # 配置参数
        self._load_config()
        
        logger.info("Limit order monitor initialized")
    
    def _load_config(self):
        """加载配置参数"""
        # 开仓限价单配置
        self.entry_limit_order_enabled = self.config.get_config(
            "trading.limit_order", "entry_limit_order_enabled", default=True
        )
        self.entry_price_away_threshold = self.config.get_config(
            "trading.limit_order", "entry_price_away_threshold", default=0.005
        )
        self.entry_limit_order_timeout = self.config.get_config(
            "trading.limit_order", "entry_limit_order_timeout", default=30
        )
        self.entry_rapid_price_change_threshold = self.config.get_config(
            "trading.limit_order", "entry_rapid_price_change_threshold", default=0.003
        )
        self.entry_rapid_price_change_window = self.config.get_config(
            "trading.limit_order", "entry_rapid_price_change_window", default=5
        )
        
        # 止盈限价单配置
        self.take_profit_limit_order_enabled = self.config.get_config(
            "trading.limit_order", "take_profit_limit_order_enabled", default=True
        )
        self.take_profit_price_away_threshold = self.config.get_config(
            "trading.limit_order", "take_profit_price_away_threshold", default=0.005
        )
        self.take_profit_limit_order_timeout = self.config.get_config(
            "trading.limit_order", "take_profit_limit_order_timeout", default=60
        )
        
        # 监控配置
        self.monitor_check_interval = self.config.get_config(
            "trading.limit_order", "monitor_check_interval", default=1
        )
        self.emergency_check_interval = self.config.get_config(
            "trading.limit_order", "emergency_check_interval", default=0.5
        )
        
        # 止损配置
        self.stop_loss_use_market_order = self.config.get_config(
            "trading.limit_order", "stop_loss_use_market_order", default=True
        )
        self.emergency_close_threshold = self.config.get_config(
            "trading.limit_order", "emergency_close_threshold", default=0.002
        )
        
        logger.info(
            f"Limit order monitor config loaded:\n"
            f"  Entry limit order enabled: {self.entry_limit_order_enabled}\n"
            f"  Entry price away threshold: {self.entry_price_away_threshold*100:.2f}%\n"
            f"  Entry timeout: {self.entry_limit_order_timeout}s\n"
            f"  Take profit limit order enabled: {self.take_profit_limit_order_enabled}\n"
            f"  Take profit price away threshold: {self.take_profit_price_away_threshold*100:.2f}%\n"
            f"  Take profit timeout: {self.take_profit_limit_order_timeout}s\n"
            f"  Monitor check interval: {self.monitor_check_interval}s\n"
            f"  Emergency check interval: {self.emergency_check_interval}s"
        )
    
    def set_price_callback(self, callback: Callable[[str], float]):
        """
        设置价格回调函数
        
        Args:
            callback: 获取当前价格的回调函数，参数为symbol，返回价格
        """
        self.get_current_price_callback = callback
    
    async def start_monitor(self, order_id: int, order_info: Dict):
        """
        启动监控任务
        
        Args:
            order_id: 订单ID
            order_info: 订单信息字典
        """
        if order_id in self.active_orders:
            logger.warning(f"Order {order_id} is already being monitored")
            return
        
        # 创建订单信息对象
        order = OrderInfo(
            order_id=order_id,
            symbol=order_info['symbol'],
            side=order_info['side'],
            order_type=order_info['order_type'],
            limit_price=order_info['limit_price'],
            quantity=order_info['quantity'],
            created_at=datetime.now(),
            price_history=[],
            original_quantity=order_info.get('original_quantity', order_info['quantity'])
        )
        
        self.active_orders[order_id] = order
        
        # 启动监控任务
        task = asyncio.create_task(self._monitor_order(order))
        self.monitor_tasks[order_id] = task
    
    async def _monitor_order(self, order: OrderInfo):
        """
        监控订单
        
        Args:
            order: 订单信息对象
        """
        try:
            # 根据订单类型选择配置
            if order.order_type == 'ENTRY':
                price_away_threshold = self.entry_price_away_threshold
                timeout = self.entry_limit_order_timeout
                rapid_change_threshold = self.entry_rapid_price_change_threshold
                rapid_change_window = self.entry_rapid_price_change_window
            else:  # TAKE_PROFIT
                price_away_threshold = self.take_profit_price_away_threshold
                timeout = self.take_profit_limit_order_timeout
                rapid_change_threshold = 0.01  # 止盈时快速变化阈值更大
                rapid_change_window = 10
            
            while True:
                # 检查订单状态
                order_status = self.trading_executor.get_order_status(order.symbol, order.order_id)
                
                if not order_status:
                    logger.error(f"Failed to get order status for {order.order_id}")
                    await asyncio.sleep(self.monitor_check_interval)
                    continue
                
                status = order_status.get('status', '')
                
                # 订单已成交
                if status == 'FILLED':
                    self.stop_monitor(order.order_id)
                    break
                
                # 订单已取消或已过期
                if status in ['CANCELED', 'EXPIRED', 'REJECTED']:
                    logger.warning(
                        f"Order {order.order_id} status changed to {status}, stopping monitor"
                    )
                    self.stop_monitor(order.order_id)
                    break
                
                # 获取当前价格
                current_price = await self._get_current_price(order.symbol)
                if current_price is None:
                    logger.warning(f"Failed to get current price for {order.symbol}")
                    await asyncio.sleep(self.monitor_check_interval)
                    continue
                
                # 记录价格历史
                order.price_history.append({
                    'price': current_price,
                    'time': datetime.now()
                })
                
                # 只保留最近的价格历史
                if len(order.price_history) > rapid_change_window * 2:
                    order.price_history = order.price_history[-rapid_change_window * 2:]
                
                # 检查监控条件
                should_cancel = False
                cancel_reason = ""
                
                # 1. 检查价格是否远离
                if self._is_price_away(order, current_price, price_away_threshold):
                    should_cancel = True
                    cancel_reason = f"price away (current={current_price:.2f}, limit={order.limit_price:.2f})"
                
                # 2. 检查是否超时
                elif self._is_timeout(order, timeout):
                    should_cancel = True
                    cancel_reason = f"timeout ({timeout}s)"
                
                # 3. 检查价格是否快速变化
                elif self._is_rapid_price_change(order, rapid_change_threshold, rapid_change_window):
                    should_cancel = True
                    cancel_reason = f"rapid price change (threshold={rapid_change_threshold*100:.2f}%)"
                
                # 如果需要取消订单
                if should_cancel:
                    logger.warning(
                        f"⚠️ Order {order.order_id} should be cancelled: {cancel_reason}"
                    )
                    
                    # 取消订单
                    cancel_success = self.trading_executor.cancel_order(order.symbol, order.order_id)
                    
                    if cancel_success:
                        # 转为市价单
                        await self._convert_to_market_order(order)
                        
                        self.stop_monitor(order.order_id)
                        break
                    else:
                        logger.error(f"Failed to cancel order {order.order_id}")
                
                # 等待下一次检查
                await asyncio.sleep(self.monitor_check_interval)
        
        except asyncio.CancelledError:
            self.stop_monitor(order.order_id)
        except Exception as e:
            logger.error(f"Error monitoring order {order.order_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.stop_monitor(order.order_id)
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取当前价格
        
        Args:
            symbol: 交易对
            
        Returns:
            当前价格或None
        """
        if self.get_current_price_callback:
            try:
                price = self.get_current_price_callback(symbol)
                return price
            except Exception as e:
                logger.error(f"Error getting current price for {symbol}: {e}")
                return None
        else:
            logger.warning("Price callback not set, using REST API")
            try:
                ticker = self.trading_executor.client.futures_symbol_ticker(symbol=symbol)
                return float(ticker['price'])
            except Exception as e:
                logger.error(f"Failed to get current price via REST API for {symbol}: {e}")
                return None
    
    def _is_price_away(self, order: OrderInfo, current_price: float, threshold: float) -> bool:
        """
        检查价格是否远离限价单价格
        
        Args:
            order: 订单信息
            current_price: 当前价格
            threshold: 阈值
            
        Returns:
            True如果价格远离
        """
        if order.side == 'BUY':
            # 做多：当前价格 > 限价单价格 * (1 + threshold)
            return current_price > order.limit_price * (1 + threshold)
        else:  # SELL
            # 做空：当前价格 < 限价单价格 * (1 - threshold)
            return current_price < order.limit_price * (1 - threshold)
    
    def _is_timeout(self, order: OrderInfo, timeout: int) -> bool:
        """
        检查订单是否超时
        
        Args:
            order: 订单信息
            timeout: 超时时间（秒）
            
        Returns:
            True如果超时
        """
        elapsed = (datetime.now() - order.created_at).total_seconds()
        return elapsed > timeout
    
    def _is_rapid_price_change(self, order: OrderInfo, threshold: float, window: int) -> bool:
        """
        检查价格是否快速变化
        
        Args:
            order: 订单信息
            threshold: 变化阈值
            window: 时间窗口（秒）
            
        Returns:
            True如果价格快速变化
        """
        if len(order.price_history) < 2:
            return False
        
        # 获取窗口内的价格
        now = datetime.now()
        window_start = now - timedelta(seconds=window)
        
        window_prices = [
            p['price'] for p in order.price_history
            if p['time'] >= window_start
        ]
        
        if len(window_prices) < 2:
            return False
        
        # 计算价格变化
        price_change = abs(window_prices[-1] - window_prices[0]) / window_prices[0]
        
        return price_change > threshold
    
    async def _convert_to_market_order(self, order: OrderInfo):
        """
        转为市价单
        
        Args:
            order: 订单信息
        """
        try:
            if order.order_type == 'ENTRY':
                # 开仓转为市价单
                if order.side == 'BUY':
                    result = self.trading_executor.open_long_position(
                        order.symbol, order.original_quantity
                    )
                else:  # SELL
                    result = self.trading_executor.open_short_position(
                        order.symbol, order.original_quantity
                    )
                
                if not result:
                    logger.error(f"Failed to place market order for {order.order_id}")
            
            elif order.order_type == 'TAKE_PROFIT':
                # 止盈转为市价单
                if order.side == 'BUY':
                    result = self.trading_executor.close_short_position(order.symbol)
                else:  # SELL
                    result = self.trading_executor.close_long_position(order.symbol)
                
                if not result:
                    logger.error(f"Failed to place market close order for {order.order_id}")
        
        except Exception as e:
            logger.error(f"Error converting order {order.order_id} to market order: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def stop_monitor(self, order_id: int):
        """
        停止监控订单
        
        Args:
            order_id: 订单ID
        """
        if order_id in self.monitor_tasks:
            task = self.monitor_tasks[order_id]
            if not task.done():
                task.cancel()
            del self.monitor_tasks[order_id]
        
        if order_id in self.active_orders:
            del self.active_orders[order_id]
    
    def get_active_orders(self) -> Dict[int, OrderInfo]:
        """
        获取所有活跃订单
        
        Returns:
            活跃订单字典
        """
        return self.active_orders.copy()
    
    def is_monitoring(self, order_id: int) -> bool:
        """
        检查是否正在监控某个订单
        
        Args:
            order_id: 订单ID
            
        Returns:
            True如果正在监控
        """
        return order_id in self.active_orders
    
    async def shutdown(self):
        """关闭监控器，停止所有监控任务"""
        # 取消所有监控任务
        for order_id in list(self.monitor_tasks.keys()):
            self.stop_monitor(order_id)