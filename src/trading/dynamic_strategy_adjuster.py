"""
动态策略调整模块
根据市场条件和交易表现动态调整策略参数
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class DynamicStrategyAdjuster:
    """动态策略调整器"""
    
    def __init__(self, config):
        """
        初始化动态策略调整器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        
        # 交易历史记录（用于分析表现）
        self.trade_history = deque(maxlen=100)  # 保留最近100笔交易
        
        # 性能指标
        self.win_rate = 0.0
        self.profit_factor = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        
        # 市场条件缓存
        self.market_conditions = {
            'volatility': 0.0,
            'trend_strength': 0.0,
            'volume_ratio': 0.0,
            'last_update': None
        }
        
        # 动态调整参数
        self.adjusted_params = {
            'position_size_multiplier': 1.0,
            'stop_loss_multiplier': 1.0,
            'take_profit_multiplier': 1.0,
            'entry_threshold': 0.0,
            'confidence_threshold': 0.0
        }
        
        # 配置参数
        self.min_trades_for_adjustment = config.get_config(
            "trading", "min_trades_for_adjustment", default=10
        )
        
        self.max_position_size_multiplier = config.get_config(
            "trading", "max_position_size_multiplier", default=1.5
        )
        
        self.min_position_size_multiplier = config.get_config(
            "trading", "min_position_size_multiplier", default=0.5
        )
        
        logger.info(
            f"DynamicStrategyAdjuster initialized: "
            f"min_trades={self.min_trades_for_adjustment}, "
            f"max_pos_mult={self.max_position_size_multiplier}, "
            f"min_pos_mult={self.min_position_size_multiplier}"
        )
    
    def add_trade(self, trade_info: Dict) -> None:
        """
        添加交易记录
        
        Args:
            trade_info: 交易信息字典
        """
        try:
            self.trade_history.append(trade_info)
            
            # 更新连续盈亏
            if trade_info.get('profit', 0) > 0:
                self.consecutive_wins += 1
                self.consecutive_losses = 0
            else:
                self.consecutive_losses += 1
                self.consecutive_wins = 0
            
            # 更新性能指标
            self._update_performance_metrics()
            
            # 检查是否需要调整策略
            if len(self.trade_history) >= self.min_trades_for_adjustment:
                self._adjust_strategy()
            
        except Exception as e:
            logger.error(f"Error adding trade: {e}")
    
    def update_market_conditions(
        self,
        volatility: float,
        trend_strength: float,
        volume_ratio: float
    ) -> None:
        """
        更新市场条件
        
        Args:
            volatility: 波动率
            trend_strength: 趋势强度
            volume_ratio: 成交量比率
        """
        try:
            self.market_conditions = {
                'volatility': volatility,
                'trend_strength': trend_strength,
                'volume_ratio': volume_ratio,
                'last_update': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error updating market conditions: {e}")
    
    def _update_performance_metrics(self) -> None:
        """更新性能指标"""
        try:
            if len(self.trade_history) == 0:
                return
            
            # 计算胜率
            wins = sum(1 for t in self.trade_history if t.get('profit', 0) > 0)
            self.win_rate = wins / len(self.trade_history)
            
            # 计算平均盈利和平均亏损
            profits = [t.get('profit', 0) for t in self.trade_history if t.get('profit', 0) > 0]
            losses = [abs(t.get('profit', 0)) for t in self.trade_history if t.get('profit', 0) < 0]
            
            self.avg_win = sum(profits) / len(profits) if profits else 0.0
            self.avg_loss = sum(losses) / len(losses) if losses else 0.0
            
            # 计算盈亏比
            total_profit = sum(profits)
            total_loss = sum(losses)
            self.profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def _adjust_strategy(self) -> None:
        """根据表现和市场条件调整策略"""
        try:
            # 基于交易表现的调整
            self._adjust_based_on_performance()
            
            # 基于市场条件的调整
            self._adjust_based_on_market_conditions()
            
            logger.info(
                f"Strategy adjusted: "
                f"pos_mult={self.adjusted_params['position_size_multiplier']:.2f}, "
                f"sl_mult={self.adjusted_params['stop_loss_multiplier']:.2f}, "
                f"tp_mult={self.adjusted_params['take_profit_multiplier']:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Error adjusting strategy: {e}")
    
    def _adjust_based_on_performance(self) -> None:
        """基于交易表现调整策略"""
        try:
            # 基于胜率调整仓位大小
            if self.win_rate >= 0.6:
                # 胜率高，增加仓位
                self.adjusted_params['position_size_multiplier'] = min(
                    self.adjusted_params['position_size_multiplier'] * 1.1,
                    self.max_position_size_multiplier
                )
            elif self.win_rate <= 0.4:
                # 胜率低，减少仓位
                self.adjusted_params['position_size_multiplier'] = max(
                    self.adjusted_params['position_size_multiplier'] * 0.9,
                    self.min_position_size_multiplier
                )
            
            # 基于连续亏损调整
            if self.consecutive_losses >= 3:
                # 连续亏损，大幅减少仓位
                self.adjusted_params['position_size_multiplier'] = max(
                    self.adjusted_params['position_size_multiplier'] * 0.7,
                    self.min_position_size_multiplier
                )
                logger.warning(
                    f"Consecutive losses detected ({self.consecutive_losses}), "
                    f"reducing position size"
                )
            elif self.consecutive_wins >= 3:
                # 连续盈利，适度增加仓位
                self.adjusted_params['position_size_multiplier'] = min(
                    self.adjusted_params['position_size_multiplier'] * 1.05,
                    self.max_position_size_multiplier
                )
            
            # 基于盈亏比调整止盈止损
            if self.profit_factor >= 2.0:
                # 盈亏比高，可以放宽止损
                self.adjusted_params['stop_loss_multiplier'] = min(
                    self.adjusted_params['stop_loss_multiplier'] * 1.05,
                    1.5
                )
            elif self.profit_factor <= 1.0:
                # 盈亏比低，收紧止损
                self.adjusted_params['stop_loss_multiplier'] = max(
                    self.adjusted_params['stop_loss_multiplier'] * 0.95,
                    0.7
                )
            
        except Exception as e:
            logger.error(f"Error adjusting based on performance: {e}")
    
    def _adjust_based_on_market_conditions(self) -> None:
        """基于市场条件调整策略"""
        try:
            volatility = self.market_conditions.get('volatility', 0.0)
            trend_strength = self.market_conditions.get('trend_strength', 0.0)
            volume_ratio = self.market_conditions.get('volume_ratio', 0.0)
            
            # 基于波动率调整止损
            if volatility > 0.02:  # 高波动
                self.adjusted_params['stop_loss_multiplier'] = min(
                    self.adjusted_params['stop_loss_multiplier'] * 1.1,
                    1.5
                )
            elif volatility < 0.01:  # 低波动
                self.adjusted_params['stop_loss_multiplier'] = max(
                    self.adjusted_params['stop_loss_multiplier'] * 0.9,
                    0.7
                )
            
            # 基于趋势强度调整止盈
            if trend_strength > 0.7:  # 强趋势
                self.adjusted_params['take_profit_multiplier'] = min(
                    self.adjusted_params['take_profit_multiplier'] * 1.1,
                    1.5
                )
            elif trend_strength < 0.3:  # 弱趋势
                self.adjusted_params['take_profit_multiplier'] = max(
                    self.adjusted_params['take_profit_multiplier'] * 0.9,
                    0.7
                )
            
            # 基于成交量调整入场阈值
            if volume_ratio < 0.5:  # 低成交量
                self.adjusted_params['entry_threshold'] = min(
                    self.adjusted_params['entry_threshold'] + 0.01,
                    0.1
                )
            elif volume_ratio > 1.5:  # 高成交量
                self.adjusted_params['entry_threshold'] = max(
                    self.adjusted_params['entry_threshold'] - 0.005,
                    0.0
                )
            
        except Exception as e:
            logger.error(f"Error adjusting based on market conditions: {e}")
    
    def get_adjusted_position_size(self, base_size: float) -> float:
        """
        获取调整后的仓位大小
        
        Args:
            base_size: 基础仓位大小
            
        Returns:
            调整后的仓位大小
        """
        multiplier = self.adjusted_params['position_size_multiplier']
        return base_size * multiplier
    
    def get_adjusted_stop_loss_distance(self, base_distance: float) -> float:
        """
        获取调整后的止损距离
        
        Args:
            base_distance: 基础止损距离
            
        Returns:
            调整后的止损距离
        """
        multiplier = self.adjusted_params['stop_loss_multiplier']
        return base_distance * multiplier
    
    def get_adjusted_take_profit_distance(self, base_distance: float) -> float:
        """
        获取调整后的止盈距离
        
        Args:
            base_distance: 基础止盈距离
            
        Returns:
            调整后的止盈距离
        """
        multiplier = self.adjusted_params['take_profit_multiplier']
        return base_distance * multiplier
    
    def get_adjusted_entry_threshold(self, base_threshold: float) -> float:
        """
        获取调整后的入场阈值
        
        Args:
            base_threshold: 基础入场阈值
            
        Returns:
            调整后的入场阈值
        """
        adjustment = self.adjusted_params['entry_threshold']
        return base_threshold + adjustment
    
    def get_performance_summary(self) -> str:
        """
        获取性能摘要
        
        Returns:
            性能摘要字符串
        """
        try:
            summary_parts = [
                f"Total trades: {len(self.trade_history)}",
                f"Win rate: {self.win_rate:.2%}",
                f"Profit factor: {self.profit_factor:.2f}",
                f"Avg win: {self.avg_win:.2f}",
                f"Avg loss: {self.avg_loss:.2f}",
                f"Consecutive wins: {self.consecutive_wins}",
                f"Consecutive losses: {self.consecutive_losses}"
            ]
            
            return ", ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return "Error getting performance summary"
    
    def get_adjustment_summary(self) -> str:
        """
        获取调整摘要
        
        Returns:
            调整摘要字符串
        """
        try:
            summary_parts = [
                f"Position size multiplier: {self.adjusted_params['position_size_multiplier']:.2f}",
                f"Stop loss multiplier: {self.adjusted_params['stop_loss_multiplier']:.2f}",
                f"Take profit multiplier: {self.adjusted_params['take_profit_multiplier']:.2f}",
                f"Entry threshold adjustment: {self.adjusted_params['entry_threshold']:.4f}"
            ]
            
            return ", ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error getting adjustment summary: {e}")
            return "Error getting adjustment summary"
    
    def reset_adjustments(self) -> None:
        """重置所有调整参数"""
        self.adjusted_params = {
            'position_size_multiplier': 1.0,
            'stop_loss_multiplier': 1.0,
            'take_profit_multiplier': 1.0,
            'entry_threshold': 0.0,
            'confidence_threshold': 0.0
        }