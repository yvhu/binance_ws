"""
订单风险控制模块
提供订单风险检查和市场条件评估功能
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OrderRiskControl:
    """订单风险控制类"""
    
    def __init__(self, config):
        """
        初始化订单风险控制
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        
        # 风险控制参数
        self.max_price_deviation_percent = config.get_config(
            "trading.limit_order", "max_price_deviation_percent", default=0.005
        )  # 最大价格偏差 0.5%
        
        self.max_stop_loss_distance_percent = config.get_config(
            "trading.limit_order", "max_stop_loss_distance_percent", default=0.02
        )  # 最大止损距离 2%
        
        self.min_stop_loss_distance_percent = config.get_config(
            "trading.limit_order", "min_stop_loss_distance_percent", default=0.005
        )  # 最小止损距离 0.5%
        
        self.volatility_threshold = config.get_config(
            "trading.limit_order", "volatility_threshold", default=0.02
        )  # 波动率阈值 2%
        
        self.volume_threshold_multiplier = config.get_config(
            "trading.limit_order", "volume_threshold_multiplier", default=0.5
        )  # 成交量阈值倍数
        
        # 市场条件缓存
        self.market_conditions_cache = {}
        self.cache_expiry = timedelta(minutes=5)  # 缓存5分钟
        
        logger.info(
            f"OrderRiskControl initialized: "
            f"max_price_deviation={self.max_price_deviation_percent*100:.2f}%, "
            f"max_stop_loss_distance={self.max_stop_loss_distance_percent*100:.2f}%, "
            f"min_stop_loss_distance={self.min_stop_loss_distance_percent*100:.2f}%, "
            f"volatility_threshold={self.volatility_threshold*100:.2f}%"
        )
    
    def check_order_risk(
        self,
        symbol: str,
        side: str,
        order_price: float,
        current_price: float,
        stop_loss_price: Optional[float] = None,
        klines: Optional[list] = None
    ) -> Tuple[bool, str, Dict]:
        """
        检查订单风险
        
        Args:
            symbol: 交易对
            side: 'LONG' or 'SHORT'
            order_price: 订单价格
            current_price: 当前价格
            stop_loss_price: 止损价格（可选）
            klines: K线数据（可选）
            
        Returns:
            Tuple of (is_safe, reason, risk_info)
            - is_safe: True if order is safe to place
            - reason: Risk check result description
            - risk_info: Dictionary with detailed risk information
        """
        risk_info = {
            'price_deviation': 0.0,
            'stop_loss_distance': 0.0,
            'volatility': 0.0,
            'volume_ratio': 0.0,
            'market_condition': 'UNKNOWN'
        }
        
        # 1. 检查价格偏差
        is_price_safe, price_deviation = self._check_price_deviation(
            order_price, current_price, side
        )
        risk_info['price_deviation'] = price_deviation
        
        if not is_price_safe:
            reason = (
                f"Price deviation too large: {price_deviation*100:.2f}% "
                f"(max: {self.max_price_deviation_percent*100:.2f}%)"
            )
            logger.warning(f"Order risk check failed for {symbol}: {reason}")
            return False, reason, risk_info
        
        # 2. 检查止损距离
        if stop_loss_price is not None:
            is_stop_loss_safe, stop_loss_distance = self._check_stop_loss_distance(
                order_price, stop_loss_price, side
            )
            risk_info['stop_loss_distance'] = stop_loss_distance
            
            if not is_stop_loss_safe:
                reason = (
                    f"Stop loss distance invalid: {stop_loss_distance*100:.2f}% "
                    f"(min: {self.min_stop_loss_distance_percent*100:.2f}%, "
                    f"max: {self.max_stop_loss_distance_percent*100:.2f}%)"
                )
                logger.warning(f"Order risk check failed for {symbol}: {reason}")
                return False, reason, risk_info
        
        # 3. 检查市场条件（如果有K线数据）
        if klines and len(klines) > 0:
            is_market_safe, market_condition, volatility, volume_ratio = self._check_market_condition(
                klines
            )
            risk_info['volatility'] = volatility
            risk_info['volume_ratio'] = volume_ratio
            risk_info['market_condition'] = market_condition
            
            if not is_market_safe:
                reason = (
                    f"Market condition unfavorable: {market_condition}, "
                    f"volatility={volatility*100:.2f}%, volume_ratio={volume_ratio:.2f}"
                )
                logger.warning(f"Order risk check failed for {symbol}: {reason}")
                return False, reason, risk_info
        
        # 所有检查通过
        reason = "Order risk check passed"
        return True, reason, risk_info
    
    def _check_price_deviation(
        self,
        order_price: float,
        current_price: float,
        side: str
    ) -> Tuple[bool, float]:
        """
        检查价格偏差
        
        Args:
            order_price: 订单价格
            current_price: 当前价格
            side: 'LONG' or 'SHORT'
            
        Returns:
            Tuple of (is_safe, deviation_percent)
        """
        # 计算价格偏差
        deviation = abs(order_price - current_price) / current_price
        
        # 对于限价单，价格偏差应该合理
        # 做多：订单价格应该低于当前价格
        # 做空：订单价格应该高于当前价格
        if side == 'LONG':
            if order_price > current_price:
                # 做多订单价格高于当前价格，偏差过大
                return False, deviation
        else:  # SHORT
            if order_price < current_price:
                # 做空订单价格低于当前价格，偏差过大
                return False, deviation
        
        # 检查偏差是否在允许范围内
        is_safe = deviation <= self.max_price_deviation_percent
        
        return is_safe, deviation
    
    def _check_stop_loss_distance(
        self,
        order_price: float,
        stop_loss_price: float,
        side: str
    ) -> Tuple[bool, float]:
        """
        检查止损距离
        
        Args:
            order_price: 订单价格
            stop_loss_price: 止损价格
            side: 'LONG' or 'SHORT'
            
        Returns:
            Tuple of (is_safe, distance_percent)
        """
        # 计算止损距离
        if side == 'LONG':
            # 做多：止损价格应该低于订单价格
            if stop_loss_price >= order_price:
                return False, 0.0
            distance = (order_price - stop_loss_price) / order_price
        else:  # SHORT
            # 做空：止损价格应该高于订单价格
            if stop_loss_price <= order_price:
                return False, 0.0
            distance = (stop_loss_price - order_price) / order_price
        
        # 检查止损距离是否在合理范围内
        is_safe = (
            self.min_stop_loss_distance_percent <= distance <= self.max_stop_loss_distance_percent
        )
        
        return is_safe, distance
    
    def _check_market_condition(
        self,
        klines: list
    ) -> Tuple[bool, str, float, float]:
        """
        检查市场条件
        
        Args:
            klines: K线数据
            
        Returns:
            Tuple of (is_safe, condition, volatility, volume_ratio)
        """
        if len(klines) < 20:
            # 数据不足，无法评估
            return True, 'INSUFFICIENT_DATA', 0.0, 0.0
        
        # 计算波动率
        volatility = self._calculate_volatility(klines)
        
        # 计算成交量比率
        volume_ratio = self._calculate_volume_ratio(klines)
        
        # 评估市场条件
        if volatility > self.volatility_threshold:
            # 波动率过高，市场不稳定
            condition = 'HIGH_VOLATILITY'
            is_safe = False
        elif volume_ratio < self.volume_threshold_multiplier:
            # 成交量过低，流动性不足
            condition = 'LOW_VOLUME'
            is_safe = False
        else:
            # 市场条件良好
            condition = 'NORMAL'
            is_safe = True
        
        return is_safe, condition, volatility, volume_ratio
    
    def _calculate_volatility(self, klines: list) -> float:
        """
        计算波动率
        
        Args:
            klines: K线数据
            
        Returns:
            波动率（百分比）
        """
        try:
            # 获取最近20根K线的收盘价
            recent_klines = klines[-20:]
            closes = [float(k['close']) for k in recent_klines]
            
            # 计算收益率
            returns = []
            for i in range(1, len(closes)):
                ret = (closes[i] - closes[i-1]) / closes[i-1]
                returns.append(ret)
            
            if len(returns) == 0:
                return 0.0
            
            # 计算标准差作为波动率
            import statistics
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
            
            return abs(volatility)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.0
    
    def _calculate_volume_ratio(self, klines: list) -> float:
        """
        计算成交量比率（当前成交量与平均成交量的比率）
        
        Args:
            klines: K线数据
            
        Returns:
            成交量比率
        """
        try:
            # 获取最近20根K线的成交量
            recent_klines = klines[-20:]
            volumes = [float(k['volume']) for k in recent_klines]
            
            if len(volumes) == 0:
                return 0.0
            
            # 计算平均成交量
            import statistics
            avg_volume = statistics.mean(volumes)
            
            if avg_volume == 0:
                return 0.0
            
            # 当前成交量与平均成交量的比率
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume
            
            return volume_ratio
            
        except Exception as e:
            logger.error(f"Error calculating volume ratio: {e}")
            return 0.0
    
    def get_risk_summary(self, risk_info: Dict) -> str:
        """
        获取风险摘要
        
        Args:
            risk_info: 风险信息字典
            
        Returns:
            风险摘要字符串
        """
        summary = []
        
        if 'price_deviation' in risk_info:
            summary.append(f"Price deviation: {risk_info['price_deviation']*100:.2f}%")
        
        if 'stop_loss_distance' in risk_info and risk_info['stop_loss_distance'] > 0:
            summary.append(f"Stop loss distance: {risk_info['stop_loss_distance']*100:.2f}%")
        
        if 'volatility' in risk_info and risk_info['volatility'] > 0:
            summary.append(f"Volatility: {risk_info['volatility']*100:.2f}%")
        
        if 'volume_ratio' in risk_info and risk_info['volume_ratio'] > 0:
            summary.append(f"Volume ratio: {risk_info['volume_ratio']:.2f}x")
        
        if 'market_condition' in risk_info:
            summary.append(f"Market condition: {risk_info['market_condition']}")
        
        return ", ".join(summary) if summary else "No risk information available"