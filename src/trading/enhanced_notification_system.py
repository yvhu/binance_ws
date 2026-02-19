"""
增强通知系统
提供详细和结构化的交易通知功能
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """通知类型枚举"""
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FAILED = "ORDER_FAILED"
    ORDER_MODIFIED = "ORDER_MODIFIED"
    
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    POSITION_PARTIALLY_CLOSED = "POSITION_PARTIALLY_CLOSED"
    
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"
    TAKE_PROFIT_TRIGGERED = "TAKE_PROFIT_TRIGGERED"
    
    RISK_WARNING = "RISK_WARNING"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    PERFORMANCE_REPORT = "PERFORMANCE_REPORT"
    
    MARKET_UPDATE = "MARKET_UPDATE"
    STRATEGY_ADJUSTMENT = "STRATEGY_ADJUSTMENT"


class NotificationPriority(Enum):
    """通知优先级枚举"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class EnhancedNotificationSystem:
    """增强通知系统"""
    
    def __init__(self, config, telegram_client=None):
        """
        初始化增强通知系统
        
        Args:
            config: 配置管理器实例
            telegram_client: Telegram客户端实例（可选）
        """
        self.config = config
        self.telegram_client = telegram_client
        
        # 通知历史
        self.notification_history = []
        self.max_history_size = 1000
        
        # 通知统计
        self.stats = {
            'total_notifications': 0,
            'by_type': {},
            'by_priority': {},
            'sent_count': 0,
            'failed_count': 0
        }
        
        # 通知配置
        self.enable_notifications = config.get_config(
            "telegram", "enable_notifications", default=True
        )
        
        self.notification_types_enabled = {
            NotificationType.ORDER_PLACED: True,
            NotificationType.ORDER_FILLED: True,
            NotificationType.ORDER_PARTIALLY_FILLED: False,
            NotificationType.ORDER_CANCELLED: True,
            NotificationType.ORDER_FAILED: True,
            NotificationType.ORDER_MODIFIED: False,
            
            NotificationType.POSITION_OPENED: True,
            NotificationType.POSITION_CLOSED: True,
            NotificationType.POSITION_PARTIALLY_CLOSED: True,
            
            NotificationType.STOP_LOSS_TRIGGERED: True,
            NotificationType.TAKE_PROFIT_TRIGGERED: True,
            
            NotificationType.RISK_WARNING: True,
            NotificationType.SYSTEM_ALERT: True,
            NotificationType.PERFORMANCE_REPORT: False,
            
            NotificationType.MARKET_UPDATE: False,
            NotificationType.STRATEGY_ADJUSTMENT: False
        }
        
        logger.info("EnhancedNotificationSystem initialized")
    
    def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict] = None
    ) -> bool:
        """
        发送通知
        
        Args:
            notification_type: 通知类型
            title: 通知标题
            message: 通知消息
            priority: 通知优先级
            data: 附加数据
            
        Returns:
            是否发送成功
        """
        try:
            # 检查是否启用该类型的通知
            if not self.notification_types_enabled.get(notification_type, False):
                logger.debug(f"Notification type {notification_type.value} is disabled")
                return False
            
            # 检查是否启用通知
            if not self.enable_notifications:
                logger.debug("Notifications are disabled")
                return False
            
            # 创建通知对象
            notification = {
                'type': notification_type.value,
                'title': title,
                'message': message,
                'priority': priority.name,
                'data': data or {},
                'timestamp': datetime.now().isoformat()
            }
            
            # 添加到历史
            self._add_to_history(notification)
            
            # 更新统计
            self._update_stats(notification_type, priority)
            
            # 发送通知
            if self.telegram_client:
                success = self._send_to_telegram(notification)
                if success:
                    self.stats['sent_count'] += 1
                else:
                    self.stats['failed_count'] += 1
                return success
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def _send_to_telegram(self, notification: Dict) -> bool:
        """
        发送通知到Telegram
        
        Args:
            notification: 通知对象
            
        Returns:
            是否发送成功
        """
        try:
            # 格式化消息
            formatted_message = self._format_notification(notification)
            
            # 发送消息
            if self.telegram_client:
                self.telegram_client.send_message(formatted_message)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error sending notification to Telegram: {e}")
            return False
    
    def _format_notification(self, notification: Dict) -> str:
        """
        格式化通知消息
        
        Args:
            notification: 通知对象
            
        Returns:
            格式化后的消息
        """
        try:
            # 添加优先级图标
            priority_icons = {
                'LOW': '📝',
                'NORMAL': 'ℹ️',
                'HIGH': '⚠️',
                'URGENT': '🚨'
            }
            
            icon = priority_icons.get(notification['priority'], 'ℹ️')
            
            # 构建消息
            message_parts = [
                f"{icon} *{notification['title']}*",
                "",
                notification['message']
            ]
            
            # 添加附加数据
            data = notification.get('data', {})
            if data:
                message_parts.append("")
                message_parts.append("*详细信息:*")
                for key, value in data.items():
                    message_parts.append(f"  • {key}: {value}")
            
            # 添加时间戳
            message_parts.append("")
            message_parts.append(f"🕐 {notification['timestamp']}")
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logger.error(f"Error formatting notification: {e}")
            return str(notification)
    
    def _add_to_history(self, notification: Dict) -> None:
        """添加通知到历史"""
        try:
            self.notification_history.append(notification)
            
            # 限制历史大小
            if len(self.notification_history) > self.max_history_size:
                self.notification_history = self.notification_history[-self.max_history_size:]
            
        except Exception as e:
            logger.error(f"Error adding notification to history: {e}")
    
    def _update_stats(self, notification_type: NotificationType, priority: NotificationPriority) -> None:
        """更新通知统计"""
        try:
            self.stats['total_notifications'] += 1
            
            # 按类型统计
            type_name = notification_type.value
            self.stats['by_type'][type_name] = self.stats['by_type'].get(type_name, 0) + 1
            
            # 按优先级统计
            priority_name = priority.name
            self.stats['by_priority'][priority_name] = self.stats['by_priority'].get(priority_name, 0) + 1
            
        except Exception as e:
            logger.error(f"Error updating notification stats: {e}")
    
    # ==================== 便捷通知方法 ====================
    
    def notify_order_placed(
        self,
        symbol: str,
        order_id: int,
        side: str,
        quantity: float,
        price: float,
        order_type: str
    ) -> bool:
        """通知订单已下达"""
        try:
            title = f"订单已下达 - {symbol}"
            message = (
                f"订单ID: {order_id}\n"
                f"方向: {side}\n"
                f"数量: {quantity:.6f}\n"
                f"价格: {price:.2f}\n"
                f"类型: {order_type}"
            )
            
            return self.send_notification(
                NotificationType.ORDER_PLACED,
                title,
                message,
                NotificationPriority.NORMAL,
                {
                    'symbol': symbol,
                    'order_id': order_id,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'order_type': order_type
                }
            )
            
        except Exception as e:
            logger.error(f"Error notifying order placed: {e}")
            return False
    
    def notify_order_filled(
        self,
        symbol: str,
        order_id: int,
        side: str,
        quantity: float,
        price: float,
        fee: float
    ) -> bool:
        """通知订单已成交"""
        try:
            title = f"订单已成交 - {symbol}"
            message = (
                f"订单ID: {order_id}\n"
                f"方向: {side}\n"
                f"数量: {quantity:.6f}\n"
                f"价格: {price:.2f}\n"
                f"手续费: {fee:.4f}"
            )
            
            return self.send_notification(
                NotificationType.ORDER_FILLED,
                title,
                message,
                NotificationPriority.HIGH,
                {
                    'symbol': symbol,
                    'order_id': order_id,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'fee': fee
                }
            )
            
        except Exception as e:
            logger.error(f"Error notifying order filled: {e}")
            return False
    
    def notify_position_opened(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """通知持仓已开"""
        try:
            title = f"持仓已开 - {symbol}"
            message = (
                f"方向: {side}\n"
                f"数量: {quantity:.6f}\n"
                f"入场价: {entry_price:.2f}"
            )
            
            if stop_loss:
                message += f"\n止损价: {stop_loss:.2f}"
            if take_profit:
                message += f"\n止盈价: {take_profit:.2f}"
            
            return self.send_notification(
                NotificationType.POSITION_OPENED,
                title,
                message,
                NotificationPriority.HIGH,
                {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
            )
            
        except Exception as e:
            logger.error(f"Error notifying position opened: {e}")
            return False
    
    def notify_position_closed(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        profit: float
    ) -> bool:
        """通知持仓已平"""
        try:
            profit_percent = (profit / (entry_price * quantity)) * 100
            profit_emoji = "📈" if profit > 0 else "📉"
            
            title = f"持仓已平 - {symbol}"
            message = (
                f"方向: {side}\n"
                f"数量: {quantity:.6f}\n"
                f"入场价: {entry_price:.2f}\n"
                f"出场价: {exit_price:.2f}\n"
                f"{profit_emoji} 盈亏: {profit:.2f} ({profit_percent:.2f}%)"
            )
            
            return self.send_notification(
                NotificationType.POSITION_CLOSED,
                title,
                message,
                NotificationPriority.HIGH,
                {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'profit': profit,
                    'profit_percent': profit_percent
                }
            )
            
        except Exception as e:
            logger.error(f"Error notifying position closed: {e}")
            return False
    
    def notify_stop_loss_triggered(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss_price: float,
        loss: float
    ) -> bool:
        """通知止损触发"""
        try:
            title = f"⚠️ 止损触发 - {symbol}"
            message = (
                f"方向: {side}\n"
                f"数量: {quantity:.6f}\n"
                f"入场价: {entry_price:.2f}\n"
                f"止损价: {stop_loss_price:.2f}\n"
                f"亏损: {loss:.2f}"
            )
            
            return self.send_notification(
                NotificationType.STOP_LOSS_TRIGGERED,
                title,
                message,
                NotificationPriority.URGENT,
                {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'stop_loss_price': stop_loss_price,
                    'loss': loss
                }
            )
            
        except Exception as e:
            logger.error(f"Error notifying stop loss triggered: {e}")
            return False
    
    def notify_take_profit_triggered(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        take_profit_price: float,
        profit: float
    ) -> bool:
        """通知止盈触发"""
        try:
            title = f"🎯 止盈触发 - {symbol}"
            message = (
                f"方向: {side}\n"
                f"数量: {quantity:.6f}\n"
                f"入场价: {entry_price:.2f}\n"
                f"止盈价: {take_profit_price:.2f}\n"
                f"盈利: {profit:.2f}"
            )
            
            return self.send_notification(
                NotificationType.TAKE_PROFIT_TRIGGERED,
                title,
                message,
                NotificationPriority.HIGH,
                {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'take_profit_price': take_profit_price,
                    'profit': profit
                }
            )
            
        except Exception as e:
            logger.error(f"Error notifying take profit triggered: {e}")
            return False
    
    def notify_risk_warning(
        self,
        warning_type: str,
        message: str,
        data: Optional[Dict] = None
    ) -> bool:
        """通知风险警告"""
        try:
            title = f"⚠️ 风险警告 - {warning_type}"
            
            return self.send_notification(
                NotificationType.RISK_WARNING,
                title,
                message,
                NotificationPriority.URGENT,
                data or {}
            )
            
        except Exception as e:
            logger.error(f"Error notifying risk warning: {e}")
            return False
    
    def notify_performance_report(self, report: Dict) -> bool:
        """通知性能报告"""
        try:
            title = "📊 性能报告"
            
            # 格式化报告
            order_metrics = report.get('order_metrics', {})
            trade_metrics = report.get('trade_metrics', {})
            
            message = (
                f"*订单统计*\n"
                f"总订单数: {order_metrics.get('total_orders', 0)}\n"
                f"成交率: {order_metrics.get('fill_rate', 0):.1%}\n"
                f"平均成交时间: {order_metrics.get('avg_fill_time', 0):.2f}s\n"
                f"平均滑点: {order_metrics.get('avg_slippage', 0):.4f}\n\n"
                f"*交易统计*\n"
                f"总交易数: {trade_metrics.get('total_trades', 0)}\n"
                f"胜率: {trade_metrics.get('win_rate', 0):.1%}\n"
                f"盈亏比: {trade_metrics.get('profit_factor', 0):.2f}\n"
                f"净盈亏: {trade_metrics.get('net_profit', 0):.2f}\n"
                f"最大回撤: {trade_metrics.get('max_drawdown', 0):.2%}"
            )
            
            return self.send_notification(
                NotificationType.PERFORMANCE_REPORT,
                title,
                message,
                NotificationPriority.NORMAL,
                report
            )
            
        except Exception as e:
            logger.error(f"Error notifying performance report: {e}")
            return False
    
    def get_notification_stats(self) -> Dict:
        """获取通知统计"""
        return self.stats.copy()
    
    def get_recent_notifications(self, count: int = 10) -> List[Dict]:
        """
        获取最近的通知
        
        Args:
            count: 返回数量
            
        Returns:
            通知列表
        """
        return self.notification_history[-count:]
    
    def enable_notification_type(self, notification_type: NotificationType) -> None:
        """启用指定类型的通知"""
        self.notification_types_enabled[notification_type] = True
        logger.info(f"Notification type {notification_type.value} enabled")
    
    def disable_notification_type(self, notification_type: NotificationType) -> None:
        """禁用指定类型的通知"""
        self.notification_types_enabled[notification_type] = False
        logger.info(f"Notification type {notification_type.value} disabled")