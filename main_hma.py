"""
HMA Breakout 策略主程序
"""

import asyncio
import signal
import logging
import os
from typing import Optional
from datetime import datetime

from src.config.config_manager import ConfigManager
from src.data import KlineManager, Kline
from src.indicators import HMAIndicator
from src.strategy import HMABreakoutStrategy
from src.trading import PositionManager, PositionType, TradingExecutor
from src.telegram.telegram_client import TelegramClient
from src.binance.ws_client import BinanceWSClient
from src.binance.user_data_client import UserDataClient
from binance.client import Client


class HMABreakoutBot:
    """HMA Breakout 策略机器人"""
    
    def __init__(self):
        """初始化机器人"""
        # 加载配置
        self.config = ConfigManager()
        
        # 设置日志
        self._setup_logging()
        
        # 初始化组件
        self.kline_manager = KlineManager(
            max_klines=self.config.data_config['max_klines']
        )
        
        # 初始化策略
        hma_params = self.config.hma_strategy_config
        
        self.strategy = HMABreakoutStrategy(
            hma1=hma_params['hma1'],
            hma2=hma_params['hma2'],
            hma3=hma_params['hma3']
        )
        
        # 初始化仓位管理器
        self.position_manager = PositionManager(
            stop_loss_roi=self.config.trading_config['stop_loss_roi']
        )
        
        # 初始化交易执行器
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        self.trading_executor = TradingExecutor(
            api_key=api_key,
            api_secret=api_secret,
            leverage=self.config.trading_config['leverage']
        )
        
        # 初始化 Telegram 客户端
        self.telegram_client = TelegramClient(self.config)
        
        # 初始化 Binance WebSocket 客户端
        self.binance_client = BinanceWSClient(self.config)
        
        # 初始化用户数据流客户端（监听订单更新）
        self.user_data_client = UserDataClient(self.config, api_key, api_secret)
        
        # 机器人状态
        self.is_running = False
        self.symbol = self.config.binance_symbols[0]
        self.interval = self.config.hma_strategy_config['kline_interval']
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.logging_config
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['format'],
            handlers=[
                logging.FileHandler(log_config['file']),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('hma_breakout_bot')
    
    def _signal_handler(self, signum, frame):
        """处理关闭信号"""
        self.logger.info(f"收到信号 {signum}，正在关闭...")
        self.is_running = False
    
    async def initialize(self) -> None:
        """初始化所有组件"""
        try:
            self.logger.info("正在初始化 HMA Breakout 机器人...")
            
            # 初始化 Telegram
            await self.telegram_client.initialize()
            
            # 设置杠杆和保证金模式
            self.trading_executor.set_leverage(
                self.symbol,
                self.config.trading_config['leverage']
            )
            self.trading_executor.set_margin_type(
                self.symbol,
                self.config.trading_config['margin_type']
            )
            
            # 获取账户信息
            account_info = self.trading_executor.get_account_info()
            if account_info:
                self.logger.info(f"账户余额: {account_info['total_wallet_balance']:.2f} USDT")
            
            # 检查当前持仓
            position_info = self.trading_executor.get_position_info(self.symbol)
            if position_info:
                self.logger.warning(f"检测到现有持仓: {position_info}")
                # 同步持仓到本地
                await self._sync_position(position_info)
            
            # 加载历史 K 线数据
            await self._load_historical_data()
            
            # 注册 WebSocket 回调
            self._register_callbacks()
            
            # 注册用户数据流回调
            self._register_user_data_callbacks()
            
            # 发送启动通知
            await self._send_startup_notification()
            
            self.logger.info("初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            raise
    
    async def _sync_position(self, position_info: dict) -> None:
        """同步持仓信息"""
        try:
            position_amount = position_info['position_amount']
            entry_price = position_info['entry_price']
            leverage = position_info['leverage']
            
            if position_amount > 0:
                # 多头持仓
                self.position_manager.open_position(
                    position_type=PositionType.LONG,
                    entry_price=entry_price,
                    quantity=position_amount,
                    leverage=leverage
                )
            elif position_amount < 0:
                # 空头持仓
                self.position_manager.open_position(
                    position_type=PositionType.SHORT,
                    entry_price=entry_price,
                    quantity=abs(position_amount),
                    leverage=leverage
                )
            
            self.logger.info(f"持仓已同步: {self.position_manager.get_current_position()}")
            
        except Exception as e:
            self.logger.error(f"同步持仓失败: {e}")
    
    async def _load_historical_data(self) -> None:
        """加载历史 K 线数据"""
        try:
            self.logger.info(f"正在加载历史 K 线数据: {self.symbol} {self.interval}")
            
            # 从 REST API 获取历史数据（使用TradingExecutor的客户端）
            klines = self.trading_executor.client.futures_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=self.config.data_config['init_klines']
            )
            
            # 添加到 K 线管理器
            for kline in klines:
                kline_obj = Kline.from_binance(kline)
                kline_obj.is_closed = True  # 历史数据都是已关闭的
                self.kline_manager.add_kline(kline_obj)
            
            self.logger.info(f"已加载 {len(klines)} 根历史 K 线")
            
        except Exception as e:
            self.logger.error(f"加载历史数据失败: {e}")
            raise
    
    def _register_callbacks(self) -> None:
        """注册 WebSocket 回调"""
        self.binance_client.on_message('kline', self._on_kline)
        self.binance_client.on_message('error', self._on_error)
    
    def _register_user_data_callbacks(self) -> None:
        """注册用户数据流回调"""
        self.user_data_client.on_message('order_update', self._on_order_update)
        self.user_data_client.on_message('error', self._on_user_data_error)
    
    async def _on_kline(self, kline_info: dict) -> None:
        """处理 K 线更新"""
        try:
            symbol = kline_info['symbol']
            interval = kline_info['interval']
            is_closed = kline_info.get('is_closed', False)
            
            # 只处理配置的交易对和周期
            if symbol != self.symbol or interval != self.interval:
                return
            
            # 创建 K 线对象
            kline_data = [
                kline_info['open_time'],
                kline_info['open'],
                kline_info['high'],
                kline_info['low'],
                kline_info['close'],
                kline_info['volume'],
                kline_info['close_time'],
                0,  # quote_asset_volume
                1 if is_closed else 0,  # number_of_trades
                0,  # taker_buy_base_asset_volume
                0,  # taker_buy_quote_asset_volume
                0   # ignore
            ]
            
            kline_obj = Kline.from_binance(kline_data)
            
            # 更新 K 线管理器
            self.kline_manager.update_current_kline(kline_obj)
            
            # 如果 K 线关闭，处理策略
            if is_closed:
                await self._process_strategy()
            
        except Exception as e:
            self.logger.error(f"处理 K 线失败: {e}")
    
    async def _process_strategy(self) -> None:
        """处理策略逻辑"""
        try:
            # 计算策略信号
            signal = self.strategy.on_kline_close(self.kline_manager)
            
            if signal is None:
                return
            
            signal_type = signal['signal_type']
            current_price = self.kline_manager.get_latest_kline().close
            
            self.logger.info(f"收到信号: {signal_type}, 价格: {current_price:.2f}")
            
            # 检查当前持仓
            has_position = self.position_manager.has_position()
            current_position_type = self.position_manager.get_position_type()
            
            # 处理信号
            if signal_type == 'LONG':
                await self._handle_long_signal(current_price, has_position, current_position_type)
            elif signal_type == 'SHORT':
                await self._handle_short_signal(current_price, has_position, current_position_type)
            elif signal_type == 'CLOSE':
                await self._handle_close_signal(current_price, has_position)
            
        except Exception as e:
            self.logger.error(f"处理策略失败: {e}")
    
    async def _handle_long_signal(self, current_price: float, 
                                  has_position: bool, 
                                  current_position_type: Optional[PositionType]) -> None:
        """处理多头信号"""
        try:
            if has_position:
                if current_position_type == PositionType.SHORT:
                    # 有空仓，先平空仓
                    self.logger.info("收到多头信号，先平空仓")
                    await self._close_position(current_price, "信号反转")
                
                # 有多仓，保持仓位
                self.logger.info("已有多仓，保持仓位")
                return
            
            # 无持仓，开多仓
            self.logger.info("开多仓")
            await self._open_long_position(current_price)
            
        except Exception as e:
            self.logger.error(f"处理多头信号失败: {e}")
    
    async def _handle_short_signal(self, current_price: float, 
                                   has_position: bool, 
                                   current_position_type: Optional[PositionType]) -> None:
        """处理空头信号"""
        try:
            if has_position:
                if current_position_type == PositionType.LONG:
                    # 有多仓，先平多仓
                    self.logger.info("收到空头信号，先平多仓")
                    await self._close_position(current_price, "信号反转")
                
                # 有空仓，保持仓位
                self.logger.info("已有空仓，保持仓位")
                return
            
            # 无持仓，开空仓
            self.logger.info("开空仓")
            await self._open_short_position(current_price)
            
        except Exception as e:
            self.logger.error(f"处理空头信号失败: {e}")
    
    async def _handle_close_signal(self, current_price: float, has_position: bool) -> None:
        """处理平仓信号"""
        try:
            if has_position:
                # 有持仓，平仓
                self.logger.info("收到平仓信号")
                await self._close_position(current_price, "平仓信号")
            else:
                # 无持仓，保持空仓
                self.logger.info("无持仓，保持空仓")
            
        except Exception as e:
            self.logger.error(f"处理平仓信号失败: {e}")
    
    async def _open_long_position(self, current_price: float) -> None:
        """开多仓"""
        try:
            # 获取账户余额
            balance = self.trading_executor.get_account_balance()
            if balance is None:
                self.logger.error("无法获取账户余额")
                return
            
            # 计算仓位大小（全仓）
            quantity = self.trading_executor.calculate_position_size(balance, current_price)
            
            # 开多仓并设置止损单
            order = self.trading_executor.open_long_position(
                self.symbol,
                quantity,
                stop_loss_roi=self.config.trading_config['stop_loss_roi']
            )
            
            if order:
                # 更新仓位管理器
                self.position_manager.open_position(
                    position_type=PositionType.LONG,
                    entry_price=current_price,
                    quantity=quantity,
                    leverage=self.config.trading_config['leverage']
                )
                
                # 发送通知
                await self._send_open_position_notification('LONG', current_price, quantity)
            
        except Exception as e:
            self.logger.error(f"开多仓失败: {e}")
    
    async def _open_short_position(self, current_price: float) -> None:
        """开空仓"""
        try:
            # 获取账户余额
            balance = self.trading_executor.get_account_balance()
            if balance is None:
                self.logger.error("无法获取账户余额")
                return
            
            # 计算仓位大小（全仓）
            quantity = self.trading_executor.calculate_position_size(balance, current_price)
            
            # 开空仓并设置止损单
            order = self.trading_executor.open_short_position(
                self.symbol,
                quantity,
                stop_loss_roi=self.config.trading_config['stop_loss_roi']
            )
            
            if order:
                # 更新仓位管理器
                self.position_manager.open_position(
                    position_type=PositionType.SHORT,
                    entry_price=current_price,
                    quantity=quantity,
                    leverage=self.config.trading_config['leverage']
                )
                
                # 发送通知
                await self._send_open_position_notification('SHORT', current_price, quantity)
            
        except Exception as e:
            self.logger.error(f"开空仓失败: {e}")
    
    async def _close_position(self, current_price: float, reason: str) -> None:
        """平仓"""
        try:
            position = self.position_manager.get_current_position()
            if position is None:
                return
            
            # 取消所有挂单（包括止损单）
            self.trading_executor.cancel_all_orders(self.symbol)
            
            # 平仓
            order = self.trading_executor.close_position(
                self.symbol,
                position.position_type,
                position.quantity
            )
            
            if order:
                # 计算盈亏
                close_info = self.position_manager.close_position(current_price)
                
                # 发送通知
                await self._send_close_position_notification(close_info, reason)
            
        except Exception as e:
            self.logger.error(f"平仓失败: {e}")
    
    async def _send_startup_notification(self) -> None:
        """发送启动通知"""
        try:
            account_info = self.trading_executor.get_account_info()
            balance = account_info['total_wallet_balance'] if account_info else 0
            
            details = {
                "交易对": self.symbol,
                "K线周期": self.interval,
                "杠杆": f"{self.config.trading_config['leverage']}倍",
                "策略": "HMA Breakout",
                "账户余额": f"{balance:.2f} USDT",
                "止损": f"{self.config.trading_config['stop_loss_roi']:.0%}"
            }
            
            message = "🚀 HMA Breakout 机器人已启动\n\n"
            for key, value in details.items():
                message += f"{key}: {value}\n"
            
            await self.telegram_client.send_message(message)
            
        except Exception as e:
            self.logger.error(f"发送启动通知失败: {e}")
    
    async def _send_open_position_notification(self, position_type: str,
                                               price: float, quantity: float) -> None:
        """发送开仓通知"""
        try:
            position = self.position_manager.get_current_position()
            
            emoji = "🟢" if position_type == "LONG" else "🔴"
            direction = "做多" if position_type == "LONG" else "做空"
            
            # 止损信息
            stop_loss_info = ""
            if position and position.stop_loss_price is not None:
                stop_loss_info = f"止损价格: {position.stop_loss_price:.2f} ({position.stop_loss_roi:.0%})\n"
            
            message = f"""
{emoji} 开仓通知

交易对: {self.symbol}
方向: {direction}
入场价格: {price:.2f}
数量: {quantity:.4f}
杠杆: {self.config.trading_config['leverage']}x
{stop_loss_info}"""
            
            await self.telegram_client.send_message(message)
            
        except Exception as e:
            self.logger.error(f"发送开仓通知失败: {e}")
    
    async def _send_close_position_notification(self, close_info: dict, reason: str) -> None:
        """发送平仓通知"""
        try:
            emoji = "🟢" if close_info['roi'] > 0 else "🔴"
            
            message = f"""
{emoji} 平仓通知

交易对: {self.symbol}
方向: {close_info['position_type']}
入场价格: {close_info['entry_price']:.2f}
平仓价格: {close_info['close_price']:.2f}
盈亏: {close_info['roi']:.2%}
盈亏金额: {close_info['pnl']:.2f} USDT
原因: {reason}
"""
            
            await self.telegram_client.send_message(message)
            
        except Exception as e:
            self.logger.error(f"发送平仓通知失败: {e}")
    
    async def _on_order_update(self, order_info: dict) -> None:
        """处理订单更新"""
        try:
            symbol = order_info['symbol']
            status = order_info['status']
            order_type = order_info['order_type']
            is_reduce_only = order_info['is_reduce_only']
            is_close_position = order_info['is_close_position']
            
            # 只处理当前交易对的订单
            if symbol != self.symbol:
                return
            
            # 只处理止损单成交（reduce_only 且已完全成交）
            if is_reduce_only and status == 'FILLED' and order_type == 'STOP_MARKET':
                self.logger.info(f"检测到止损单成交: {order_info}")
                
                # 获取当前持仓
                position = self.position_manager.get_current_position()
                if position:
                    # 计算平仓信息
                    close_price = order_info['avg_price']
                    close_info = self.position_manager.close_position(close_price)
                    
                    # 发送止损平仓通知
                    await self._send_close_position_notification(close_info, "止损触发")
                    
        except Exception as e:
            self.logger.error(f"处理订单更新失败: {e}")
    
    async def _on_user_data_error(self, error_info: dict) -> None:
        """处理用户数据流错误"""
        try:
            error_message = error_info.get('error', 'Unknown error')
            self.logger.error(f"用户数据流错误: {error_message}")
            
            await self.telegram_client.send_message(f"❌ 用户数据流错误: {error_message}")
            
        except Exception as e:
            self.logger.error(f"处理用户数据流错误失败: {e}")
    
    async def _on_error(self, error_info: dict) -> None:
        """处理错误"""
        try:
            error_message = error_info.get('error', 'Unknown error')
            self.logger.error(f"WebSocket 错误: {error_message}")
            
            await self.telegram_client.send_message(f"❌ 错误: {error_message}")
            
        except Exception as e:
            self.logger.error(f"处理错误失败: {e}")
    
    async def run(self) -> None:
        """运行机器人"""
        self.is_running = True
        
        try:
            # 初始化
            await self.initialize()
            
            # 启动 WebSocket
            ws_task = asyncio.create_task(self.binance_client.start())
            
            # 启动用户数据流
            user_data_task = asyncio.create_task(self.user_data_client.start())
            
            # 主循环 - 保持运行
            while self.is_running:
                await asyncio.sleep(1)
            
            # 停止 WebSocket
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass
            
            # 停止用户数据流
            user_data_task.cancel()
            try:
                await user_data_task
            except asyncio.CancelledError:
                pass
            
        except asyncio.CancelledError:
            self.logger.info("机器人被取消")
        except Exception as e:
            self.logger.error(f"机器人运行错误: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """关闭机器人"""
        self.logger.info("正在关闭机器人...")
        
        try:
            # 断开 WebSocket
            await self.binance_client.disconnect()
            
            # 断开用户数据流
            await self.user_data_client.disconnect()
            
            # 停止 Telegram
            await self.telegram_client.shutdown()
            
            self.logger.info("机器人已关闭")
            
        except Exception as e:
            self.logger.error(f"关闭失败: {e}")


async def main():
    """主入口"""
    bot = HMABreakoutBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n机器人已停止")
    except Exception as e:
        print(f"致命错误: {e}")