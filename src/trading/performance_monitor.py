"""
性能监控和分析模块
提供订单执行性能监控和交易数据分析功能
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, config):
        """
        初始化性能监控器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        
        # 订单执行记录
        self.order_executions = deque(maxlen=1000)
        
        # 交易记录
        self.trades = deque(maxlen=500)
        
        # 性能指标
        self.metrics = {
            'total_orders': 0,
            'filled_orders': 0,
            'cancelled_orders': 0,
            'failed_orders': 0,
            'partial_fills': 0,
            'avg_fill_time': 0.0,
            'avg_slippage': 0.0,
            'total_fees': 0.0,
            'total_profit': 0.0,
            'total_loss': 0.0
        }
        
        # 时间窗口统计
        self.hourly_stats = deque(maxlen=24)  # 24小时统计
        self.daily_stats = deque(maxlen=30)   # 30天统计
    
    def record_order_execution(
        self,
        order_id: int,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        price: float,
        status: str,
        fill_time: Optional[float] = None,
        slippage: Optional[float] = None,
        fee: Optional[float] = None
    ) -> None:
        """
        记录订单执行
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            order_type: 订单类型
            side: 买卖方向
            quantity: 数量
            price: 价格
            status: 订单状态
            fill_time: 成交时间（秒）
            slippage: 滑点
            fee: 手续费
        """
        try:
            execution = {
                'order_id': order_id,
                'symbol': symbol,
                'order_type': order_type,
                'side': side,
                'quantity': quantity,
                'price': price,
                'status': status,
                'fill_time': fill_time,
                'slippage': slippage,
                'fee': fee,
                'timestamp': datetime.now()
            }
            
            self.order_executions.append(execution)
            
            # 更新指标
            self.metrics['total_orders'] += 1
            
            if status == 'FILLED':
                self.metrics['filled_orders'] += 1
                if fill_time:
                    self._update_avg_fill_time(fill_time)
                if slippage:
                    self._update_avg_slippage(slippage)
                if fee:
                    self.metrics['total_fees'] += fee
            elif status == 'CANCELED':
                self.metrics['cancelled_orders'] += 1
            elif status == 'FAILED':
                self.metrics['failed_orders'] += 1
            elif status == 'PARTIALLY_FILLED':
                self.metrics['partial_fills'] += 1
            
        except Exception as e:
            logger.error(f"Error recording order execution: {e}")
    
    def record_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        profit: float,
        holding_time: float,
        entry_type: str,
        exit_type: str
    ) -> None:
        """
        记录交易
        
        Args:
            trade_id: 交易ID
            symbol: 交易对
            side: 买卖方向
            entry_price: 入场价格
            exit_price: 出场价格
            quantity: 数量
            profit: 盈亏
            holding_time: 持仓时间（秒）
            entry_type: 入场类型
            exit_type: 出场类型
        """
        try:
            trade = {
                'trade_id': trade_id,
                'symbol': symbol,
                'side': side,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'profit': profit,
                'holding_time': holding_time,
                'entry_type': entry_type,
                'exit_type': exit_type,
                'timestamp': datetime.now()
            }
            
            self.trades.append(trade)
            
            # 更新指标
            if profit > 0:
                self.metrics['total_profit'] += profit
            else:
                self.metrics['total_loss'] += abs(profit)
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    def _update_avg_fill_time(self, fill_time: float) -> None:
        """更新平均成交时间"""
        try:
            filled_count = self.metrics['filled_orders']
            current_avg = self.metrics['avg_fill_time']
            
            # 计算新的平均值
            new_avg = (current_avg * (filled_count - 1) + fill_time) / filled_count
            self.metrics['avg_fill_time'] = new_avg
            
        except Exception as e:
            logger.error(f"Error updating average fill time: {e}")
    
    def _update_avg_slippage(self, slippage: float) -> None:
        """更新平均滑点"""
        try:
            filled_count = self.metrics['filled_orders']
            current_avg = self.metrics['avg_slippage']
            
            # 计算新的平均值
            new_avg = (current_avg * (filled_count - 1) + slippage) / filled_count
            self.metrics['avg_slippage'] = new_avg
            
        except Exception as e:
            logger.error(f"Error updating average slippage: {e}")
    
    def get_order_fill_rate(self) -> float:
        """
        获取订单成交率
        
        Returns:
            成交率（0-1）
        """
        try:
            total = self.metrics['total_orders']
            if total == 0:
                return 0.0
            
            filled = self.metrics['filled_orders']
            return filled / total
            
        except Exception as e:
            logger.error(f"Error calculating order fill rate: {e}")
            return 0.0
    
    def get_win_rate(self) -> float:
        """
        获取胜率
        
        Returns:
            胜率（0-1）
        """
        try:
            if len(self.trades) == 0:
                return 0.0
            
            wins = sum(1 for t in self.trades if t.get('profit', 0) > 0)
            return wins / len(self.trades)
            
        except Exception as e:
            logger.error(f"Error calculating win rate: {e}")
            return 0.0
    
    def get_profit_factor(self) -> float:
        """
        获取盈亏比
        
        Returns:
            盈亏比
        """
        try:
            total_profit = self.metrics['total_profit']
            total_loss = self.metrics['total_loss']
            
            if total_loss == 0:
                return float('inf') if total_profit > 0 else 0.0
            
            return total_profit / total_loss
            
        except Exception as e:
            logger.error(f"Error calculating profit factor: {e}")
            return 0.0
    
    def get_avg_holding_time(self) -> float:
        """
        获取平均持仓时间
        
        Returns:
            平均持仓时间（秒）
        """
        try:
            if len(self.trades) == 0:
                return 0.0
            
            holding_times = [t.get('holding_time', 0) for t in self.trades]
            return statistics.mean(holding_times)
            
        except Exception as e:
            logger.error(f"Error calculating average holding time: {e}")
            return 0.0
    
    def get_avg_profit_per_trade(self) -> float:
        """
        获取平均每笔交易盈亏
        
        Returns:
            平均盈亏
        """
        try:
            if len(self.trades) == 0:
                return 0.0
            
            profits = [t.get('profit', 0) for t in self.trades]
            return statistics.mean(profits)
            
        except Exception as e:
            logger.error(f"Error calculating average profit per trade: {e}")
            return 0.0
    
    def get_max_drawdown(self) -> float:
        """
        获取最大回撤
        
        Returns:
            最大回撤
        """
        try:
            if len(self.trades) == 0:
                return 0.0
            
            # 计算累计盈亏
            cumulative = []
            running_total = 0.0
            for trade in self.trades:
                running_total += trade.get('profit', 0)
                cumulative.append(running_total)
            
            if len(cumulative) == 0:
                return 0.0
            
            # 计算最大回撤
            peak = max(cumulative)
            trough = min(cumulative)
            max_drawdown = peak - trough
            
            return max_drawdown
            
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0
    
    def get_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        获取夏普比率
        
        Args:
            risk_free_rate: 无风险利率（年化）
            
        Returns:
            夏普比率
        """
        try:
            if len(self.trades) < 2:
                return 0.0
            
            profits = [t.get('profit', 0) for t in self.trades]
            
            # 计算平均收益
            avg_return = statistics.mean(profits)
            
            # 计算标准差
            std_return = statistics.stdev(profits) if len(profits) > 1 else 0.0
            
            if std_return == 0:
                return 0.0
            
            # 计算夏普比率（简化版）
            sharpe = avg_return / std_return
            
            return sharpe
            
        except Exception as e:
            logger.error(f"Error calculating sharpe ratio: {e}")
            return 0.0
    
    def get_performance_report(self) -> Dict:
        """
        获取性能报告
        
        Returns:
            性能报告字典
        """
        try:
            report = {
                'order_metrics': {
                    'total_orders': self.metrics['total_orders'],
                    'filled_orders': self.metrics['filled_orders'],
                    'cancelled_orders': self.metrics['cancelled_orders'],
                    'failed_orders': self.metrics['failed_orders'],
                    'partial_fills': self.metrics['partial_fills'],
                    'fill_rate': self.get_order_fill_rate(),
                    'avg_fill_time': self.metrics['avg_fill_time'],
                    'avg_slippage': self.metrics['avg_slippage'],
                    'total_fees': self.metrics['total_fees']
                },
                'trade_metrics': {
                    'total_trades': len(self.trades),
                    'win_rate': self.get_win_rate(),
                    'profit_factor': self.get_profit_factor(),
                    'total_profit': self.metrics['total_profit'],
                    'total_loss': self.metrics['total_loss'],
                    'net_profit': self.metrics['total_profit'] - self.metrics['total_loss'],
                    'avg_profit_per_trade': self.get_avg_profit_per_trade(),
                    'avg_holding_time': self.get_avg_holding_time(),
                    'max_drawdown': self.get_max_drawdown(),
                    'sharpe_ratio': self.get_sharpe_ratio()
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {}
    
    def get_optimization_suggestions(self) -> List[str]:
        """
        获取优化建议
        
        Returns:
            优化建议列表
        """
        try:
            suggestions = []
            
            # 基于成交率的建议
            fill_rate = self.get_order_fill_rate()
            if fill_rate < 0.7:
                suggestions.append(
                    f"订单成交率较低（{fill_rate:.1%}），建议："
                    "1. 调整限价单价格偏移；2. 增加超时时间；3. 考虑使用市价单"
                )
            
            # 基于滑点的建议
            avg_slippage = self.metrics['avg_slippage']
            if avg_slippage > 0.001:  # 0.1%
                suggestions.append(
                    f"平均滑点较高（{avg_slippage:.4f}），建议："
                    "1. 减少订单数量；2. 避免在高波动时段交易；3. 使用更保守的价格偏移"
                )
            
            # 基于胜率的建议
            win_rate = self.get_win_rate()
            if win_rate < 0.4:
                suggestions.append(
                    f"胜率较低（{win_rate:.1%}），建议："
                    "1. 提高入场信号质量；2. 增加过滤条件；3. 优化止损策略"
                )
            
            # 基于盈亏比的建议
            profit_factor = self.get_profit_factor()
            if profit_factor < 1.5:
                suggestions.append(
                    f"盈亏比较低（{profit_factor:.2f}），建议："
                    "1. 优化止盈策略；2. 调整止损距离；3. 改善入场时机"
                )
            
            # 基于持仓时间的建议
            avg_holding_time = self.get_avg_holding_time()
            if avg_holding_time < 300:  # 5分钟
                suggestions.append(
                    f"平均持仓时间较短（{avg_holding_time:.0f}秒），建议："
                    "1. 检查是否过度交易；2. 优化止盈止损设置；3. 增加趋势确认"
                )
            
            # 基于最大回撤的建议
            max_drawdown = self.get_max_drawdown()
            if max_drawdown > 0.1:  # 10%
                suggestions.append(
                    f"最大回撤较高（{max_drawdown:.2%}），建议："
                    "1. 降低仓位大小；2. 优化止损策略；3. 增加风险控制"
                )
            
            if not suggestions:
                suggestions.append("当前表现良好，继续保持！")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating optimization suggestions: {e}")
            return ["无法生成优化建议"]
    
    def get_performance_summary(self) -> str:
        """
        获取性能摘要
        
        Returns:
            性能摘要字符串
        """
        try:
            report = self.get_performance_report()
            
            summary_parts = [
                f"订单总数: {report['order_metrics']['total_orders']}",
                f"成交率: {report['order_metrics']['fill_rate']:.1%}",
                f"平均成交时间: {report['order_metrics']['avg_fill_time']:.2f}s",
                f"平均滑点: {report['order_metrics']['avg_slippage']:.4f}",
                f"交易总数: {report['trade_metrics']['total_trades']}",
                f"胜率: {report['trade_metrics']['win_rate']:.1%}",
                f"盈亏比: {report['trade_metrics']['profit_factor']:.2f}",
                f"净盈亏: {report['trade_metrics']['net_profit']:.2f}",
                f"最大回撤: {report['trade_metrics']['max_drawdown']:.2f}"
            ]
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return "无法生成性能摘要"
    
    def reset_metrics(self) -> None:
        """重置所有指标"""
        self.metrics = {
            'total_orders': 0,
            'filled_orders': 0,
            'cancelled_orders': 0,
            'failed_orders': 0,
            'partial_fills': 0,
            'avg_fill_time': 0.0,
            'avg_slippage': 0.0,
            'total_fees': 0.0,
            'total_profit': 0.0,
            'total_loss': 0.0
        }
        self.order_executions.clear()
        self.trades.clear()