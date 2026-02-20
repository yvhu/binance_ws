"""
交易执行模块
负责与Binance API交互执行交易
"""

from typing import Optional, Dict
import logging
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

from .position_manager import Position, PositionType

logger = logging.getLogger(__name__)


class TradingExecutor:
    """交易执行器"""
    
    def __init__(self, api_key: str, api_secret: str, leverage: int = 10):
        """
        初始化交易执行器
        
        Args:
            api_key: Binance API密钥
            api_secret: Binance API密钥
            leverage: 杠杆倍数
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.leverage = leverage
        
        # 初始化Binance客户端
        self.client = Client(api_key, api_secret)
    
    def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        设置杠杆倍数
        
        Args:
            symbol: 交易对
            leverage: 杠杆倍数
            
        Returns:
            是否成功
        """
        try:
            self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            logger.info(f"设置杠杆: {symbol} {leverage}x")
            return True
        except BinanceAPIException as e:
            logger.error(f"设置杠杆失败: {e}")
            return False
    
    def set_margin_type(self, symbol: str, margin_type: str = 'cross') -> bool:
        """
        设置保证金模式
        
        Args:
            symbol: 交易对
            margin_type: 保证金模式（cross或isolated）
            
        Returns:
            是否成功
        """
        try:
            # 转换为币安API要求的格式
            api_margin_type = 'CROSSED' if margin_type.lower() == 'cross' else 'ISOLATED'
            
            self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=api_margin_type
            )
            logger.info(f"设置保证金模式: {symbol} {margin_type}")
            return True
        except BinanceAPIException as e:
            # 如果已经是正确的保证金模式，忽略错误
            if e.code == -4046:
                logger.info(f"保证金模式已经是 {margin_type}，无需修改")
                return True
            logger.error(f"设置保证金模式失败: {e}")
            return False
    
    def get_account_balance(self, symbol: str = None) -> Optional[float]:
        """
        获取账户余额
        
        Args:
            symbol: 交易对（可选），用于确定查询哪种资产余额
        
        Returns:
            资产余额
        """
        try:
            account = self.client.futures_account_balance()
            
            # 打印所有资产用于调试
            logger.debug(f"账户所有资产: {account}")
            
            # 确定保证金资产（根据交易对后缀）
            asset_name = 'USDT'  # 默认查询USDT
            if symbol:
                if symbol.endswith('USDC'):
                    asset_name = 'USDC'
                elif symbol.endswith('BUSD'):
                    asset_name = 'BUSD'
                elif symbol.endswith('USDT'):
                    asset_name = 'USDT'
            
            logger.debug(f"查询资产: {asset_name}")
            
            # 查找指定资产余额
            for asset in account:
                logger.debug(f"检查资产: {asset['asset']} = {asset['balance']}")
                if asset['asset'] == asset_name:
                    balance = float(asset['balance'])
                    logger.info(f"账户余额: {balance:.8f} {asset_name}")
                    return balance
            
            # 如果没找到指定资产，尝试返回总余额
            logger.warning(f"未找到 {asset_name} 余额，尝试返回总余额")
            total_balance = 0.0
            for asset in account:
                total_balance += float(asset['balance'])
            
            if total_balance > 0:
                logger.info(f"账户总余额: {total_balance:.8f}")
                return total_balance
            
            logger.warning(f"账户无余额")
            return 0.0
        except BinanceAPIException as e:
            logger.error(f"获取账户余额失败: {e}")
            return None
    
    def get_position_info(self, symbol: str) -> Optional[Dict]:
        """
        获取持仓信息
        
        Args:
            symbol: 交易对
            
        Returns:
            持仓信息字典
        """
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            for pos in positions:
                if pos['symbol'] == symbol and float(pos['positionAmt']) != 0:
                    return {
                        'symbol': pos['symbol'],
                        'position_side': pos['positionSide'],
                        'position_amount': float(pos['positionAmt']),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                        'leverage': int(pos['leverage'])
                    }
            return None
        except BinanceAPIException as e:
            logger.error(f"获取持仓信息失败: {e}")
            return None
    
    def calculate_position_size(self, balance: float, current_price: float) -> float:
        """
        计算仓位大小（全仓交易）
        
        Args:
            balance: 账户余额
            current_price: 当前价格
            
        Returns:
            仓位数量
        """
        # 全仓交易：使用全部余额
        # 考虑杠杆倍数
        position_value = balance * self.leverage
        quantity = position_value / current_price
        
        logger.info(f"计算仓位大小: 余额={balance:.2f}, 价格={current_price:.2f}, "
                   f"杠杆={self.leverage}x, 数量={quantity:.4f}")
        
        return quantity
    
    def open_long_position(self, symbol: str, quantity: float,
                          stop_loss_roi: float = -0.40) -> Optional[Dict]:
        """
        开多仓并设置止损单
        
        Args:
            symbol: 交易对
            quantity: 数量
            stop_loss_roi: 止损ROI（默认-40%）
            
        Returns:
            订单信息
        """
        try:
            # 使用市价单开多仓
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"开多仓成功: {symbol} 数量={quantity:.4f}")
            
            # 获取成交价格
            entry_price = float(order['avgPrice']) if 'avgPrice' in order else None
            if entry_price:
                # 设置止损单
                self._set_stop_loss_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss_roi=stop_loss_roi
                )
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"开多仓失败: {e}")
            return None
    
    def open_short_position(self, symbol: str, quantity: float,
                           stop_loss_roi: float = -0.40) -> Optional[Dict]:
        """
        开空仓并设置止损单
        
        Args:
            symbol: 交易对
            quantity: 数量
            stop_loss_roi: 止损ROI（默认-40%）
            
        Returns:
            订单信息
        """
        try:
            # 使用市价单开空仓
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            logger.info(f"开空仓成功: {symbol} 数量={quantity:.4f}")
            
            # 获取成交价格
            entry_price = float(order['avgPrice']) if 'avgPrice' in order else None
            if entry_price:
                # 设置止损单
                self._set_stop_loss_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    quantity=quantity,
                    entry_price=entry_price,
                    stop_loss_roi=stop_loss_roi
                )
            
            return order
            
        except BinanceAPIException as e:
            logger.error(f"开空仓失败: {e}")
            return None
    
    def close_position(self, symbol: str, position_type: PositionType, 
                       quantity: float) -> Optional[Dict]:
        """
        平仓
        
        Args:
            symbol: 交易对
            position_type: 持仓类型
            quantity: 数量
            
        Returns:
            订单信息
        """
        try:
            # 根据持仓类型决定平仓方向
            if position_type == PositionType.LONG:
                # 平多仓：卖出
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_MARKET,
                    quantity=quantity
                )
            else:
                # 平空仓：买入
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_MARKET,
                    quantity=quantity
                )
            
            logger.info(f"平仓成功: {symbol} 数量={quantity:.4f}")
            return order
            
        except BinanceAPIException as e:
            logger.error(f"平仓失败: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        获取当前价格
        
        Args:
            symbol: 交易对
            
        Returns:
            当前价格
        """
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = float(ticker['price'])
            return price
        except BinanceAPIException as e:
            logger.error(f"获取当前价格失败: {e}")
            return None
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """
        取消所有挂单
        
        Args:
            symbol: 交易对
            
        Returns:
            是否成功
        """
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"取消所有挂单: {symbol}")
            return True
        except BinanceAPIException as e:
            logger.error(f"取消挂单失败: {e}")
            return False
    
    def _set_stop_loss_order(self, symbol: str, side: str, quantity: float,
                            entry_price: float, stop_loss_roi: float) -> bool:
        """
        设置止损单
        
        Args:
            symbol: 交易对
            side: 止损单方向（BUY或SELL）
            quantity: 数量
            entry_price: 入场价格
            stop_loss_roi: 止损ROI
            
        Returns:
            是否成功
        """
        try:
            # 计算止损价格
            # ROI = (价格变化 / 入场价格) * 杠杆
            # 价格变化 = ROI * 入场价格 / 杠杆
            price_change = abs(stop_loss_roi) * entry_price / self.leverage
            
            if side == SIDE_SELL:
                # 多头止损：价格下跌
                stop_price = entry_price - price_change
            else:
                # 空头止损：价格上涨
                stop_price = entry_price + price_change
            
            # 创建止损单
            stop_order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                stopPrice=round(stop_price, 2),
                closePosition=True,
                reduceOnly=True
            )
            
            logger.info(f"设置止损单成功: {symbol} 止损价={stop_price:.2f} ROI={stop_loss_roi:.2%}")
            return True
            
        except BinanceAPIException as e:
            logger.error(f"设置止损单失败: {e}")
            return False
    
    def get_account_info(self) -> Optional[Dict]:
        """
        获取账户信息
        
        Returns:
            账户信息字典
        """
        try:
            account = self.client.futures_account()
            
            # 打印完整的账户信息用于调试
            logger.debug(f"完整账户信息: {account}")
            
            account_info = {
                'total_wallet_balance': float(account['totalWalletBalance']),
                'available_balance': float(account['availableBalance']),
                'total_position_initial_margin': float(account['totalPositionInitialMargin']),
                'total_unrealized_profit': float(account['totalUnrealizedProfit']),
                'total_margin_balance': float(account['totalMarginBalance'])
            }
            
            logger.info(f"账户总余额: {account_info['total_wallet_balance']:.2f}")
            logger.info(f"可用余额: {account_info['available_balance']:.2f}")
            
            return account_info
        except BinanceAPIException as e:
            logger.error(f"获取账户信息失败: {e}")
            return None