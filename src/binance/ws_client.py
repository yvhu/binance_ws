"""
Binance Futures WebSocket Client
Handles WebSocket connections to Binance Futures for real-time market data
"""

import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from ..config.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class BinanceWSClient:
    """Binance WebSocket client for real-time market data"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize Binance Futures WebSocket client
        
        Args:
            config: Configuration manager instance
        """
        self.config = config
        self.ws_url = config.binance_ws_url
        self.symbols = config.binance_symbols
        self.streams = config.binance_streams
        self.futures_type = config.get_config("binance", "futures_type", default="perpetual")
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.reconnect_attempts = config.get_config("binance", "reconnect_attempts", default=5)
        self.reconnect_delay = config.get_config("binance", "reconnect_delay", default=5)
        
        # Callbacks for different message types
        self.callbacks: Dict[str, List[Callable]] = {
            'ticker': [],
            'kline': [],
            'trade': [],
            'error': []
        }
        
        # Data storage
        self.latest_data: Dict[str, Dict] = {}
        
        # Track active callback tasks to prevent garbage collection
        self.active_tasks: List[asyncio.Task] = []
    
    def on_message(self, message_type: str, callback: Callable) -> None:
        """
        Register callback for specific message type
        
        Args:
            message_type: Type of message (ticker, kline, trade, error)
            callback: Callback function to handle the message
        """
        if message_type in self.callbacks:
            self.callbacks[message_type].append(callback)
    
    def _build_stream_url(self) -> str:
        """
        Build WebSocket stream URL for Binance Futures based on configured symbols and streams
        using combined streams format per Binance docs
        
        Returns:
            Complete WebSocket URL for futures
        """
        streams = []
        
        for symbol in self.symbols:
            symbol_lower = symbol.lower()
            for stream in self.streams:
                if stream == 'ticker':
                    streams.append(f"{symbol_lower}@ticker")
                elif stream.startswith('kline_'):
                    interval = stream.split('_')[1]
                    streams.append(f"{symbol_lower}@kline_{interval}")
                elif stream == 'trade':
                    streams.append(f"{symbol_lower}@trade")
                elif stream == 'markPrice':
                    streams.append(f"{symbol_lower}@markPrice")
                elif stream == 'forceOrder':
                    streams.append(f"{symbol_lower}@forceOrder")
        
        if not streams:
            raise ValueError("No valid streams configured")
        
        # Use combined streams URL format: /stream?streams=stream1/stream2/stream3
        stream_path = "/".join(streams)
        url = f"{self.ws_url}/stream?streams={stream_path}"
        return url
    
    async def connect(self) -> None:
        """Connect to Binance WebSocket"""
        url = self._build_stream_url()
        
        try:
            # Set timeout to avoid hanging
            self.websocket = await asyncio.wait_for(
                websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=1000
                ),
                timeout=30.0
            )
            self.is_connected = True
        except asyncio.TimeoutError:
            logger.error("✗ WebSocket connection timeout after 30 seconds")
            self.is_connected = False
            raise
        except Exception as e:
            import traceback
            logger.error(f"✗ Failed to connect to Binance WebSocket: {e}")
            logger.error(traceback.format_exc())
            self.is_connected = False
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Binance WebSocket"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
    
    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming WebSocket message for combined streams format
        
        Args:
            message: JSON message string
        """
        try:
            data = json.loads(message)
            
            # For combined streams, message has 'stream' and 'data' fields
            if 'stream' in data and 'data' in data:
                event_data = data['data']
            else:
                event_data = data
            
            if 'e' in event_data:
                event_type = event_data['e']
                
                if event_type == '24hrTicker':
                    # logger.debug(f"[WS] Processing ticker event...")
                    self._process_ticker(event_data)
                    # logger.debug(f"[WS] Ticker event processed")
                elif event_type == 'kline':
                    # logger.debug(f"[WS] Processing kline event...")
                    self._process_kline(event_data)
                    # logger.debug(f"[WS] Kline event processed")
                elif event_type == 'trade':
                    # logger.debug(f"[WS] Processing trade event...")
                    self._process_trade(event_data)
                    # logger.debug(f"[WS] Trade event processed")
                elif event_type == 'markPriceUpdate':
                    # logger.debug(f"[WS] Processing mark price event...")
                    self._process_mark_price(event_data)
                    # logger.debug(f"[WS] Mark price event processed")
                elif event_type == 'forceOrder':
                    # logger.debug(f"[WS] Processing force order event...")
                    self._process_force_order(event_data)
                    # logger.debug(f"[WS] Force order event processed")
                else:
                    logger.warning(f"[WS] Unknown event type: {event_type}")
            else:
                logger.debug(f"[WS] Message has no event type field")
            
        except json.JSONDecodeError as e:
            logger.error(f"[WS] ✗ Failed to parse message: {e}")
            logger.error(f"[WS] Raw message: {message[:200]}...")
        except Exception as e:
            logger.error(f"[WS] ✗ Error handling message: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _process_ticker(self, data: Dict) -> None:
        """
        Process ticker data
        
        Args:
            data: Ticker data from Binance
        """
        symbol = data.get('s', 'UNKNOWN')
        self.latest_data[f"{symbol}_ticker"] = data
        
        ticker_info = {
            'symbol': symbol,
            'price_change': float(data.get('p', 0)),
            'price_change_percent': float(data.get('P', 0)),
            'current_price': float(data.get('c', 0)),
            'high_price': float(data.get('h', 0)),
            'low_price': float(data.get('l', 0)),
            'volume': float(data.get('v', 0)),
            'timestamp': data.get('E', 0)
        }
        
        for idx, callback in enumerate(self.callbacks['ticker']):
            try:
                # logger.debug(f"[WS] Calling ticker callback {idx+1}/{callback_count}...")
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(ticker_info))
                    self.active_tasks.append(task)
                    # Clean up completed tasks
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(ticker_info)
                # logger.debug(f"[WS] Ticker callback {idx+1}/{callback_count} completed")
            except Exception as e:
                logger.error(f"[WS] ✗ Error in ticker callback {idx+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    def _process_kline(self, data: Dict) -> None:
        """
        Process kline (candlestick) data
        
        Args:
            data: Kline data from Binance
        """
        kline = data.get('k', {})
        symbol = data.get('s', 'UNKNOWN')
        interval = kline.get('i', '1m')
        is_closed = kline.get('x', False)
        
        self.latest_data[f"{symbol}_kline_{interval}"] = data
        
        kline_info = {
            'symbol': symbol,
            'interval': interval,
            'open_time': kline.get('t', 0),
            'close_time': kline.get('T', 0),
            'open': float(kline.get('o', 0)),
            'high': float(kline.get('h', 0)),
            'low': float(kline.get('l', 0)),
            'close': float(kline.get('c', 0)),
            'volume': float(kline.get('v', 0)),
            'is_closed': kline.get('x', False),
            'number_of_trades': kline.get('n', 0)
        }
        
        for idx, callback in enumerate(self.callbacks['kline']):
            try:
                # logger.debug(f"[WS] Calling kline callback {idx+1}/{callback_count}...")
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(kline_info))
                    self.active_tasks.append(task)
                    # Clean up completed tasks
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(kline_info)
                # logger.debug(f"[WS] Kline callback {idx+1}/{callback_count} completed")
            except Exception as e:
                logger.error(f"[WS] ✗ Error in kline callback {idx+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    def _process_trade(self, data: Dict) -> None:
        """
        Process trade data
        
        Args:
            data: Trade data from Binance
        """
        symbol = data.get('s', 'UNKNOWN')
        
        trade_info = {
            'symbol': symbol,
            'trade_id': data.get('t', 0),
            'price': float(data.get('p', 0)),
            'quantity': float(data.get('q', 0)),
            'time': data.get('T', 0),
            'is_buyer_maker': data.get('m', False)
        }
        
        for idx, callback in enumerate(self.callbacks['trade']):
            try:
                # logger.debug(f"[WS] Calling trade callback {idx+1}/{callback_count}...")
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(trade_info))
                    self.active_tasks.append(task)
                    # Clean up completed tasks
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(trade_info)
                # logger.debug(f"[WS] Trade callback {idx+1}/{callback_count} completed")
            except Exception as e:
                logger.error(f"[WS] ✗ Error in trade callback {idx+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    def _process_mark_price(self, data: Dict) -> None:
        """
        Process mark price data (Futures specific)
        
        Args:
            data: Mark price data from Binance Futures
        """
        symbol = data.get('s', 'UNKNOWN')
        
        mark_price_info = {
            'symbol': symbol,
            'mark_price': float(data.get('p', 0)),
            'index_price': float(data.get('i', 0)),
            'estimated_settle_price': float(data.get('P', 0)),
            'funding_rate': float(data.get('r', 0)),
            'next_funding_time': data.get('T', 0),
            'timestamp': data.get('E', 0)
        }
        
        for idx, callback in enumerate(self.callbacks.get('mark_price', [])):
            try:
                # logger.debug(f"[WS] Calling mark price callback {idx+1}/{callback_count}...")
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(mark_price_info))
                    self.active_tasks.append(task)
                    # Clean up completed tasks
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(mark_price_info)
                # logger.debug(f"[WS] Mark price callback {idx+1}/{callback_count} completed")
            except Exception as e:
                logger.error(f"[WS] ✗ Error in mark price callback {idx+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    def _process_force_order(self, data: Dict) -> None:
        """
        Process force order/liquidation data (Futures specific)
        
        Args:
            data: Force order data from Binance Futures
        """
        order = data.get('o', {})
        symbol = data.get('s', 'UNKNOWN')
        
        force_order_info = {
            'symbol': symbol,
            'side': order.get('S', 'UNKNOWN'),
            'order_type': order.get('o', 'UNKNOWN'),
            'time_in_force': order.get('f', 'UNKNOWN'),
            'original_quantity': float(order.get('q', 0)),
            'price': float(order.get('p', 0)),
            'average_price': float(order.get('ap', 0)),
            'order_status': order.get('X', 'UNKNOWN'),
            'last_filled_quantity': float(order.get('z', 0)),
            'total_filled_quantity': float(order.get('Z', 0)),
            'timestamp': data.get('E', 0)
        }
        
        for idx, callback in enumerate(self.callbacks.get('force_order', [])):
            try:
                # logger.debug(f"[WS] Calling force order callback {idx+1}/{callback_count}...")
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(force_order_info))
                    self.active_tasks.append(task)
                    # Clean up completed tasks
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(force_order_info)
                # logger.debug(f"[WS] Force order callback {idx+1}/{callback_count} completed")
            except Exception as e:
                logger.error(f"[WS] ✗ Error in force order callback {idx+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    async def listen(self) -> None:
        """Listen for incoming messages from WebSocket"""
        if not self.is_connected or not self.websocket:
            logger.error("[WS] ✗ Cannot listen: WebSocket is not connected")
            raise RuntimeError("WebSocket is not connected")
        
        message_count = 0
        
        try:
            async for message in self.websocket:
                message_count += 1
                await self._handle_message(message)
        except ConnectionClosedError as e:
            logger.error(f"[WS] ✗ Binance Futures WebSocket connection closed: {e}")
            logger.error(f"[WS] Total messages received: {message_count}")
            self.is_connected = False
            for callback in self.callbacks['error']:
                try:
                    callback({'type': 'connection_closed', 'error': str(e)})
                except Exception as err:
                    logger.error(f"[WS] Error in error callback: {err}")
        except Exception as e:
            logger.error(f"[WS] ✗ Error while listening: {e}")
            logger.error(f"[WS] Total messages received: {message_count}")
            import traceback
            logger.error(traceback.format_exc())
            self.is_connected = False
    
    async def start(self) -> None:
        """Start WebSocket connection and listening with continuous reconnection"""
        attempt = 0
        
        while True:  # Continuous reconnection loop
            try:
                await self.connect()
                await self.listen()
                logger.warning("Listen loop ended unexpectedly")
                
                # Reset attempt counter on successful connection
                attempt = 0
                
            except Exception as e:
                import traceback
                attempt += 1
                logger.error(f"✗ Connection attempt {attempt} failed: {e}")
                logger.error(traceback.format_exc())
                
                # Calculate delay with exponential backoff (max 60 seconds)
                delay = min(self.reconnect_delay * (2 ** min(attempt - 1, 4)), 60)
                
                logger.info(f"⏳ Reconnecting in {delay} seconds... (attempt {attempt})")
                await asyncio.sleep(delay)
                
                # Reset attempt counter after long delay to allow fresh start
                if attempt >= self.reconnect_attempts:
                    logger.warning(f"Reached {self.reconnect_attempts} failed attempts, continuing to retry...")
                    attempt = 0
    
    def get_latest_data(self, symbol: str, data_type: str = 'ticker') -> Optional[Dict]:
        """
        Get latest data for a symbol
        
        Args:
            symbol: Trading pair symbol
            data_type: Type of data (ticker, kline, trade)
            
        Returns:
            Latest data dictionary or None
        """
        key = f"{symbol}_{data_type}"
        return self.latest_data.get(key)
    
# 这里假设ws_client.py是WebSocket客户端管理文件，添加调用杠杆初始化的钩子

from src.trading.trading_executor import TradingExecutor

# 假设已有TradingExecutor实例 te
# 在WebSocket连接成功的回调中调用
# 这里假设TradingExecutor实例te是在main.py中创建的，示例代码如下：
# 请根据实际情况调整

from src.trading.trading_executor import TradingExecutor
from src.config.config_manager import ConfigManager

config = ConfigManager()
te = TradingExecutor(config)

def on_ws_connected():
    te.initialize_leverage_after_ws()

def on_ws_connected():
    # 连接成功后调用杠杆初始化
    te.initialize_leverage_after_ws()

# 具体实现请根据ws_client.py的结构调整