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
        self.ws_url = "wss://fstream.binance.com"
        self.symbols = config.binance_symbols
        self.streams = config.binance_streams
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        
        # Callbacks for different message types
        self.callbacks: Dict[str, List[Callable]] = {
            'kline': [],
            'error': []
        }
        
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
                if stream.startswith('kline_'):
                    interval = stream.split('_')[1]
                    streams.append(f"{symbol_lower}@kline_{interval}")
        
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
                
                if event_type == 'kline':
                    self._process_kline(event_data)
                else:
                    logger.debug(f"[WS] Unknown event type: {event_type}")
            else:
                logger.debug(f"[WS] Message has no event type field")
            
        except json.JSONDecodeError as e:
            logger.error(f"[WS] ✗ Failed to parse message: {e}")
            logger.error(f"[WS] Raw message: {message[:200]}...")
        except Exception as e:
            logger.error(f"[WS] ✗ Error handling message: {e}")
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
                if asyncio.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(kline_info))
                    self.active_tasks.append(task)
                    self.active_tasks = [t for t in self.active_tasks if not t.done()]
                else:
                    callback(kline_info)
            except Exception as e:
                logger.error(f"[WS] ✗ Error in kline callback {idx+1}: {e}")
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
                delay = min(5 * (2 ** min(attempt - 1, 4)), 60)
                
                logger.info(f"⏳ Reconnecting in {delay} seconds... (attempt {attempt})")
                await asyncio.sleep(delay)
                
                # Reset attempt counter after long delay to allow fresh start
                if attempt >= 5:
                    logger.warning(f"Reached 5 failed attempts, continuing to retry...")
                    attempt = 0
    