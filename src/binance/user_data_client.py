"""
Binance User Data Stream Client
Handles WebSocket connections for user data (orders, positions, account)
"""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError
import hmac
import hashlib
import time

from ..config.config_manager import ConfigManager
from binance.client import Client

logger = logging.getLogger(__name__)


class UserDataClient:
    """Binance user data stream client"""
    
    def __init__(self, config: ConfigManager, api_key: str, api_secret: str):
        """
        Initialize user data stream client
        
        Args:
            config: Configuration manager instance
            api_key: Binance API key
            api_secret: Binance API secret
        """
        self.config = config
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = Client(api_key, api_secret)
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.listen_key: Optional[str] = None
        self.keep_alive_task: Optional[asyncio.Task] = None
        
        # Callbacks for different event types
        self.callbacks: Dict[str, List[Callable]] = {
            'order_update': [],
            'error': []
        }
        
        # Track active callback tasks
        self.active_tasks: List[asyncio.Task] = []
    
    def on_message(self, message_type: str, callback: Callable) -> None:
        """
        Register callback for specific message type
        
        Args:
            message_type: Type of message (order_update, account_update, position_update, error)
            callback: Callback function to handle the message
        """
        if message_type in self.callbacks:
            self.callbacks[message_type].append(callback)
    
    async def _get_listen_key(self) -> str:
        """
        Get listen key for user data stream
        
        Returns:
            Listen key string
        """
        try:
            response = self.client.futures_stream_get_listen_key()
            logger.info("获取用户数据流 listen key 成功")
            return response
        except Exception as e:
            logger.error(f"获取 listen key 失败: {e}")
            raise
    
    async def _keep_alive_listen_key(self) -> None:
        """
        Keep the listen key alive by sending keep-alive request every 30 minutes
        """
        while self.is_connected:
            try:
                await asyncio.sleep(30 * 60)  # 30 minutes
                if self.listen_key:
                    self.client.futures_stream_keepalive(self.listen_key)
                    logger.info("Keep-alive 请求发送成功")
            except Exception as e:
                logger.error(f"Keep-alive 请求失败: {e}")
    
    async def connect(self) -> None:
        """Connect to Binance user data stream"""
        try:
            # Get listen key
            self.listen_key = await self._get_listen_key()
            
            # Build WebSocket URL
            ws_url = f"wss://fstream.binance.com/ws/{self.listen_key}"
            
            # Connect
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=1000
                ),
                timeout=30.0
            )
            
            self.is_connected = True
            logger.info("用户数据流连接成功")
            
            # Start keep-alive task
            self.keep_alive_task = asyncio.create_task(self._keep_alive_listen_key())
            
        except asyncio.TimeoutError:
            logger.error("用户数据流连接超时")
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"用户数据流连接失败: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from user data stream"""
        try:
            # Cancel keep-alive task
            if self.keep_alive_task:
                self.keep_alive_task.cancel()
                try:
                    await self.keep_alive_task
                except asyncio.CancelledError:
                    pass
            
            # Close WebSocket
            if self.websocket:
                await self.websocket.close()
            
            # Close listen key
            if self.listen_key:
                try:
                    self.client.futures_stream_close(self.listen_key)
                    logger.info("Listen key 已关闭")
                except Exception as e:
                    logger.error(f"关闭 listen key 失败: {e}")
            
            self.is_connected = False
            logger.info("用户数据流已断开")
            
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
    
    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming user data message
        
        Args:
            message: JSON message string
        """
        try:
            data = json.loads(message)
            event_type = data.get('e', '')
            
            if event_type == 'ORDER_TRADE_UPDATE':
                self._process_order_update(data)
            else:
                logger.debug(f"未知事件类型: {event_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"解析消息失败: {e}")
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _process_order_update(self, data: Dict) -> None:
        """
        Process order update event
        
        Args:
            data: Order update data from Binance
        """
        order = data.get('o', {})
        symbol = order.get('s', 'UNKNOWN')
        
        order_info = {
            'symbol': symbol,
            'order_id': order.get('i', 0),
            'client_order_id': order.get('c', ''),
            'side': order.get('S', 'UNKNOWN'),
            'order_type': order.get('o', 'UNKNOWN'),
            'time_in_force': order.get('f', 'UNKNOWN'),
            'original_quantity': float(order.get('q', 0)),
            'executed_quantity': float(order.get('z', 0)),
            'cumulative_quote_qty': float(order.get('Z', 0)),
            'status': order.get('X', 'UNKNOWN'),
            'stop_price': float(order.get('p', 0)),
            'avg_price': float(order.get('ap', 0)),
            'commission': float(order.get('n', 0)),
            'commission_asset': order.get('N', ''),
            'is_maker': order.get('m', False),
            'is_reduce_only': order.get('R', False),
            'is_close_position': order.get('cp', False),
            'execution_type': order.get('x', 'UNKNOWN'),
            'order_time': order.get('T', 0),
            'event_time': data.get('E', 0)
        }
        
        for idx, callback in enumerate(self.callbacks['order_update']):
            try:
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(order_info))
                    self.active_tasks.append(task)
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(order_info)
            except Exception as e:
                logger.error(f"订单更新回调错误: {e}")
    
    
    async def listen(self) -> None:
        """Listen for incoming messages from user data stream"""
        if not self.is_connected or not self.websocket:
            logger.error("无法监听: WebSocket 未连接")
            raise RuntimeError("WebSocket 未连接")
        
        try:
            async for message in self.websocket:
                await self._handle_message(message)
        except ConnectionClosedError as e:
            logger.error(f"用户数据流连接关闭: {e}")
            self.is_connected = False
            for callback in self.callbacks['error']:
                try:
                    callback({'type': 'connection_closed', 'error': str(e)})
                except Exception as err:
                    logger.error(f"错误回调异常: {err}")
        except Exception as e:
            logger.error(f"监听错误: {e}")
            self.is_connected = False
    
    async def start(self) -> None:
        """Start user data stream with continuous reconnection"""
        while True:
            try:
                await self.connect()
                await self.listen()
                logger.warning("监听循环意外结束")
                
            except Exception as e:
                import traceback
                logger.error(f"连接失败: {e}")
                logger.error(traceback.format_exc())
                
                logger.info("5秒后重连...")
                await asyncio.sleep(5)