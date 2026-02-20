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
from ..utils.retry_decorator import sync_retry, log_retry_attempt

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
        
        # 缓存交易对精度信息
        self.symbol_precision_cache: Dict[str, Dict] = {}
    
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
    
    @sync_retry(max_retries=3, base_delay=1.0, on_retry_callback=log_retry_attempt)
    def get_account_balance(self, symbol: str = None) -> Optional[float]:
        """
        获取账户可用余额（用于开仓）
        
        Args:
            symbol: 交易对（可选），用于确定查询哪种资产余额
        
        Returns:
            可用资产余额，失败返回None
        """
        try:
            # 使用 futures_account 获取完整账户信息（包含可用余额）
            account = self.client.futures_account()
            
            # 打印完整账户信息用于调试
            # logger.debug(f"完整账户信息: {account}")
            
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
            
            # 检查所有资产余额
            balance = 0.0
            if 'assets' in account:
                for asset in account['assets']:
                    asset_name_check = asset.get('asset', 'N/A')
                    available_balance = float(asset.get('availableBalance', 0))
                    
                    logger.debug(f"检查资产: {asset_name_check} = {available_balance:.8f} (可用)")
                    
                    # 优先使用 USDC，如果没有则使用 USDT
                    if asset_name_check == 'USDC' and available_balance > 0:
                        balance = available_balance
                        logger.info(f"使用 USDC 可用余额: {balance:.8f}")
                    elif asset_name_check == 'USDT' and available_balance > 0 and balance == 0:
                        balance = available_balance
                        logger.info(f"使用 USDT 可用余额: {balance:.8f}")
            
            if balance > 0:
                logger.info(f"账户可用余额: {balance:.8f} {asset_name}")
                return balance
            
            logger.warning(f"账户无可用余额")
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
    
    def get_symbol_precision(self, symbol: str) -> Optional[Dict]:
        """
        获取交易对精度信息
        
        Args:
            symbol: 交易对
            
        Returns:
            精度信息字典，包含 quantity_precision 和 price_precision
        """
        # 检查缓存
        if symbol in self.symbol_precision_cache:
            return self.symbol_precision_cache[symbol]
        
        try:
            exchange_info = self.client.futures_exchange_info()
            
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    # 获取数量精度
                    quantity_precision = 0
                    for filter_info in s['filters']:
                        if filter_info['filterType'] == 'LOT_SIZE':
                            step_size = float(filter_info['stepSize'])
                            # 计算小数位数
                            if step_size < 1:
                                quantity_precision = len(str(step_size).split('.')[1].rstrip('0'))
                            break
                    
                    # 获取价格精度
                    price_precision = 0
                    for filter_info in s['filters']:
                        if filter_info['filterType'] == 'PRICE_FILTER':
                            tick_size = float(filter_info['tickSize'])
                            # 计算小数位数
                            if tick_size < 1:
                                price_precision = len(str(tick_size).split('.')[1].rstrip('0'))
                            break
                    
                    precision_info = {
                        'quantity_precision': quantity_precision,
                        'price_precision': price_precision,
                        'step_size': step_size,
                        'tick_size': tick_size
                    }
                    
                    # 缓存结果
                    self.symbol_precision_cache[symbol] = precision_info
                    
                    logger.info(f"交易对 {symbol} 精度: 数量={quantity_precision}, 价格={price_precision}")
                    return precision_info
            
            logger.error(f"未找到交易对 {symbol} 的精度信息")
            return None
            
        except BinanceAPIException as e:
            logger.error(f"获取交易对精度失败: {e}")
            return None
    
    def round_quantity(self, symbol: str, quantity: float) -> float:
        """
        根据交易对精度对数量进行四舍五入
        
        Args:
            symbol: 交易对
            quantity: 原始数量
            
        Returns:
            四舍五入后的数量
        """
        precision_info = self.get_symbol_precision(symbol)
        if precision_info:
            step_size = precision_info['step_size']
            # 向下取整到最近的 step_size 倍数
            rounded_quantity = int(quantity / step_size) * step_size
            logger.debug(f"数量四舍五入: {quantity:.8f} -> {rounded_quantity:.8f} (step_size={step_size})")
            return rounded_quantity
        else:
            # 如果无法获取精度，默认保留3位小数
            logger.warning(f"无法获取 {symbol} 精度，使用默认精度3位小数")
            return round(quantity, 3)
    
    def calculate_position_size(self, balance: float, current_price: float, symbol: str = None) -> float:
        """
        计算仓位大小（全仓交易）
        
        Args:
            balance: 账户余额
            current_price: 当前价格
            symbol: 交易对（可选，用于精度处理）
            
        Returns:
            仓位数量
        """
        # 全仓交易：使用全部余额
        # 考虑杠杆倍数
        position_value = balance * self.leverage
        quantity = position_value / current_price
        
        logger.info(f"计算仓位大小: 余额={balance:.2f}, 价格={current_price:.2f}, "
                   f"杠杆={self.leverage}x, 数量={quantity:.4f}")
        
        # 如果提供了交易对，根据精度进行四舍五入
        if symbol:
            quantity = self.round_quantity(symbol, quantity)
            logger.info(f"精度调整后数量: {quantity:.8f}")
        
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
            # 根据交易对精度对数量进行四舍五入
            rounded_quantity = self.round_quantity(symbol, quantity)
            logger.info(f"开多仓数量调整: {quantity:.8f} -> {rounded_quantity:.8f}")
            
            # 使用市价单开多仓
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=rounded_quantity
            )
            
            logger.info(f"开多仓成功: {symbol} 数量={rounded_quantity:.8f}")
            logger.info(f"订单响应: {order}")
            
            # 获取成交价格
            # 市价单可能没有 avgPrice，尝试从多个字段获取
            entry_price = None
            if 'avgPrice' in order and order['avgPrice']:
                entry_price = float(order['avgPrice'])
            elif 'cummulativeQuoteQty' in order and 'executedQty' in order:
                # 计算平均价格 = 总成交金额 / 总成交数量
                cum_quote = float(order['cummulativeQuoteQty'])
                exec_qty = float(order['executedQty'])
                if exec_qty > 0:
                    entry_price = cum_quote / exec_qty
            
            logger.info(f"获取到的入场价格: {entry_price}")
            
            if entry_price:
                # 设置止损单（使用调整后的数量）
                self._set_stop_loss_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    quantity=rounded_quantity,
                    entry_price=entry_price,
                    stop_loss_roi=stop_loss_roi
                )
            else:
                logger.error("无法获取入场价格，无法设置止损单")
            
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
            # 根据交易对精度对数量进行四舍五入
            rounded_quantity = self.round_quantity(symbol, quantity)
            logger.info(f"开空仓数量调整: {quantity:.8f} -> {rounded_quantity:.8f}")
            
            # 使用市价单开空仓
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=rounded_quantity
            )
            
            logger.info(f"开空仓成功: {symbol} 数量={rounded_quantity:.8f}")
            logger.info(f"订单响应: {order}")
            
            # 获取成交价格
            # 市价单可能没有 avgPrice，尝试从多个字段获取
            entry_price = None
            if 'avgPrice' in order and order['avgPrice']:
                entry_price = float(order['avgPrice'])
            elif 'cummulativeQuoteQty' in order and 'executedQty' in order:
                # 计算平均价格 = 总成交金额 / 总成交数量
                cum_quote = float(order['cummulativeQuoteQty'])
                exec_qty = float(order['executedQty'])
                if exec_qty > 0:
                    entry_price = cum_quote / exec_qty
            
            logger.info(f"获取到的入场价格: {entry_price}")
            
            if entry_price:
                # 设置止损单（使用调整后的数量）
                self._set_stop_loss_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    quantity=rounded_quantity,
                    entry_price=entry_price,
                    stop_loss_roi=stop_loss_roi
                )
            else:
                logger.error("无法获取入场价格，无法设置止损单")
            
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
            # 根据交易对精度对数量进行四舍五入
            rounded_quantity = self.round_quantity(symbol, quantity)
            logger.info(f"平仓数量调整: {quantity:.8f} -> {rounded_quantity:.8f}")
            
            # 根据持仓类型决定平仓方向
            if position_type == PositionType.LONG:
                # 平多仓：卖出
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_MARKET,
                    quantity=rounded_quantity
                )
            else:
                # 平空仓：买入
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_MARKET,
                    quantity=rounded_quantity
                )
            
            logger.info(f"平仓成功: {symbol} 数量={rounded_quantity:.8f}")
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
            # 获取交易对价格精度
            precision_info = self.get_symbol_precision(symbol)
            if not precision_info:
                logger.error(f"无法获取 {symbol} 的价格精度，无法设置止损单")
                return False
            
            price_precision = precision_info['price_precision']
            tick_size = precision_info['tick_size']
            
            # 计算止损价格
            # ROI = (价格变化 / 入场价格) * 杠杆
            # 价格变化 = ROI * 入场价格 / 杠杆
            price_change = abs(stop_loss_roi) * entry_price / self.leverage
            
            logger.info(f"止损价格计算: 入场价={entry_price:.8f}, ROI={stop_loss_roi:.2%}, "
                       f"杠杆={self.leverage}x, 价格变化={price_change:.8f}")
            
            if side == SIDE_SELL:
                # 多头止损：价格下跌
                stop_price = entry_price - price_change
            else:
                # 空头止损：价格上涨
                stop_price = entry_price + price_change
            
            # 确保止损价格不为负数
            if stop_price <= 0:
                logger.error(f"止损价格计算错误: {stop_price:.8f} <= 0")
                return False
            
            # 根据价格精度调整止损价格
            # 向下取整到最近的 tick_size 倍数
            rounded_stop_price = int(stop_price / tick_size) * tick_size
            
            logger.info(f"止损价格调整: 原始={stop_price:.8f}, 调整后={rounded_stop_price:.8f}, "
                       f"tick_size={tick_size}")
            
            # 创建止损单
            # 注意：closePosition=True 时不能使用 reduceOnly 参数
            logger.info(f"正在创建止损单: symbol={symbol}, side={side}, "
                       f"stopPrice={rounded_stop_price:.8f}, closePosition=True")
            
            stop_order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                stopPrice=rounded_stop_price,
                closePosition=True
            )
            
            logger.info(f"设置止损单成功: {symbol} 止损价={rounded_stop_price:.8f} ROI={stop_loss_roi:.2%} "
                       f"订单ID={stop_order.get('orderId', 'N/A')}")
            return True
            
        except BinanceAPIException as e:
            logger.error(f"设置止损单失败: {e}")
            logger.error(f"错误代码: {e.code}, 错误消息: {e.message}")
            return False
        except Exception as e:
            logger.error(f"设置止损单异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
            # logger.info(f"完整账户信息: {account}")
            
            # 从 assets 数组中查找 USDC 或 USDT 的可用余额
            available_balance = 0.0
            total_wallet_balance = 0.0
            asset_name = 'USDT'  # 默认资产名称
            
            if 'assets' in account:
                for asset in account['assets']:
                    asset_name_check = asset.get('asset', 'N/A')
                    asset_available = float(asset.get('availableBalance', 0))
                    asset_wallet_balance = float(asset.get('walletBalance', 0))
                    
                    logger.debug(f"检查资产: {asset_name_check} = 可用:{asset_available:.8f}, 钱包:{asset_wallet_balance:.8f}")
                    
                    # 优先使用 USDC，如果没有则使用 USDT
                    if asset_name_check == 'USDC' and asset_available > 0:
                        available_balance = asset_available
                        total_wallet_balance = asset_wallet_balance
                        asset_name = 'USDC'
                        logger.info(f"使用 USDC 余额: 可用={available_balance:.8f}, 钱包={total_wallet_balance:.8f}")
                    elif asset_name_check == 'USDT' and asset_available > 0 and available_balance == 0:
                        available_balance = asset_available
                        total_wallet_balance = asset_wallet_balance
                        asset_name = 'USDT'
                        logger.info(f"使用 USDT 余额: 可用={available_balance:.8f}, 钱包={total_wallet_balance:.8f}")
            
            # 如果没有找到可用余额，尝试使用 totalWalletBalance 和 availableBalance 字段
            if available_balance == 0 and 'totalWalletBalance' in account:
                total_wallet_balance = float(account['totalWalletBalance'])
                available_balance = float(account['availableBalance'])
                logger.info(f"使用 API 返回的总余额字段: 总={total_wallet_balance:.8f}, 可用={available_balance:.8f}")
            
            account_info = {
                'total_wallet_balance': total_wallet_balance,
                'available_balance': available_balance,
                'total_position_initial_margin': float(account.get('totalPositionInitialMargin', 0)),
                'total_unrealized_profit': float(account.get('totalUnrealizedProfit', 0)),
                'total_margin_balance': float(account.get('totalMarginBalance', 0)),
                'asset_name': asset_name
            }
            
            logger.info(f"账户总余额: {account_info['total_wallet_balance']:.8f} {asset_name}")
            logger.info(f"可用余额: {account_info['available_balance']:.8f} {asset_name}")
            
            return account_info
        except BinanceAPIException as e:
            logger.error(f"获取账户信息失败: {e}")
            return None