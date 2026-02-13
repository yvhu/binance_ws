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
    
    def on_message(self, message_type: str, callback: Callable) -> None:
        """
        Register callback for specific message type
        
        Args:
            message_type: Type of message (ticker, kline, trade, error)
            callback: Callback function to handle the message
        """
        if message_type in self.callbacks:
            self.callbacks[message_type].append(callback)
            logger.info(f"Registered callback for {message_type}")
    
    def _build_stream_url(self) -> str:
        """
        Build WebSocket stream URL for Binance Futures based on configured symbols and streams
        using combined streams format per Binance docs
        
        Returns:
            Complete WebSocket URL for futures
        """
        streams = []
        logger.info(f"Building stream URL for symbols: {self.symbols}")
        logger.info(f"Configured streams: {self.streams}")
        
        for symbol in self.symbols:
            symbol_lower = symbol.lower()
            for stream in self.streams:
                if stream == 'ticker':
                    streams.append(f"{symbol_lower}@ticker")
                    logger.debug(f"Added ticker stream for {symbol}")
                elif stream.startswith('kline_'):
                    interval = stream.split('_')[1]
                    streams.append(f"{symbol_lower}@kline_{interval}")
                    logger.debug(f"Added kline_{interval} stream for {symbol}")
                elif stream == 'trade':
                    streams.append(f"{symbol_lower}@trade")
                    logger.debug(f"Added trade stream for {symbol}")
                elif stream == 'markPrice':
                    streams.append(f"{symbol_lower}@markPrice")
                    logger.debug(f"Added markPrice stream for {symbol}")
                elif stream == 'forceOrder':
                    streams.append(f"{symbol_lower}@forceOrder")
                    logger.debug(f"Added forceOrder stream for {symbol}")
        
        if not streams:
            raise ValueError("No valid streams configured")
        
        # Use combined streams URL format: /stream?streams=stream1/stream2/stream3
        stream_path = "/".join(streams)
        url = f"{self.ws_url}/stream?streams={stream_path}"
        logger.info(f"Built combined WebSocket URL: {url}")
        return url
    
    async def connect(self) -> None:
        """Connect to Binance WebSocket"""
        url = self._build_stream_url()
        logger.info(f"Connecting to Binance Futures WebSocket: {url}")
        
        try:
            logger.info("Establishing WebSocket connection...")
            # Set timeout to avoid hanging
            self.websocket = await asyncio.wait_for(
                websockets.connect(url),
                timeout=30.0
            )
            self.is_connected = True
            logger.info("✓ Successfully connected to Binance Futures WebSocket")
        except asyncio.TimeoutError:
            logger.error("✗ WebSocket connection timeout after 30 seconds")
            self.is_connected = False
            raise
        except Exception as e:
            import traceback
            logger.error(f"✗ Failed to connect to Binance WebSocket: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.is_connected = False
            raise
        finally:
            logger.info(f"WebSocket connection status: {self.is_connected}")
    
    async def disconnect(self) -> None:
        """Disconnect from Binance WebSocket"""
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from Binance Futures WebSocket")
    
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
                    self._process_ticker(event_data)
                elif event_type == 'kline':
                    self._process_kline(event_data)
                elif event_type == 'trade':
                    self._process_trade(event_data)
                elif event_type == 'markPriceUpdate':
                    self._process_mark_price(event_data)
                elif event_type == 'forceOrder':
                    self._process_force_order(event_data)
                else:
                    logger.warning(f"Unknown event type: {event_type}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
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
        
        for callback in self.callbacks['ticker']:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(ticker_info))
                else:
                    callback(ticker_info)
            except Exception as e:
                logger.error(f"Error in ticker callback: {e}")
    
    def _process_kline(self, data: Dict) -> None:
        """
        Process kline (candlestick) data
        
        Args:
            data: Kline data from Binance
        """
        kline = data.get('k', {})
        symbol = data.get('s', 'UNKNOWN')
        interval = kline.get('i', '1m')
        
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
        
        for callback in self.callbacks['kline']:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(kline_info))
                else:
                    callback(kline_info)
            except Exception as e:
                logger.error(f"Error in kline callback: {e}")
    
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
        
        for callback in self.callbacks['trade']:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(trade_info))
                else:
                    callback(trade_info)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")
    
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
        
        for callback in self.callbacks.get('mark_price', []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(mark_price_info))
                else:
                    callback(mark_price_info)
            except Exception as e:
                logger.error(f"Error in mark price callback: {e}")
    
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
        
        for callback in self.callbacks.get('force_order', []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(force_order_info))
                else:
                    callback(force_order_info)
            except Exception as e:
                logger.error(f"Error in force order callback: {e}")
    
    async def listen(self) -> None:
        """Listen for incoming messages from WebSocket"""
        if not self.is_connected or not self.websocket:
            raise RuntimeError("WebSocket is not connected")
        
        logger.info("✓ Starting to listen for messages...")
        logger.info("Waiting for market data...")
        
        try:
            message_count = 0
            async for message in self.websocket:
                message_count += 1
                if message_count == 1:
                    logger.info("✓ First message received from Binance WebSocket")
                elif message_count % 100 == 0:
                    logger.info(f"✓ Received {message_count} messages from Binance WebSocket")
                await self._handle_message(message)
        except ConnectionClosedError as e:
            logger.error(f"✗ Binance Futures WebSocket connection closed: {e}")
            self.is_connected = False
            for callback in self.callbacks['error']:
                try:
                    callback({'type': 'connection_closed', 'error': str(e)})
                except Exception as err:
                    logger.error(f"Error in error callback: {err}")
        except Exception as e:
            logger.error(f"✗ Error while listening: {e}")
            self.is_connected = False
        finally:
            logger.info(f"WebSocket listening ended, connection status: {self.is_connected}")
    
    async def start(self) -> None:
        """Start WebSocket connection and listening"""
        attempt = 0
        
        logger.info(f"Starting WebSocket connection (max {self.reconnect_attempts} attempts)...")
        
        while attempt < self.reconnect_attempts:
            try:
                logger.info(f"Connection attempt {attempt + 1}/{self.reconnect_attempts}")
                await self.connect()
                # Start a background task to send periodic pongs to keep connection alive
                pong_task = asyncio.create_task(self._send_periodic_pong())
                await self.listen()
                pong_task.cancel()
            except Exception as e:
                attempt += 1
                logger.error(f"✗ Connection attempt {attempt} failed: {e}")
                
                if attempt < self.reconnect_attempts:
                    logger.info(f"⏳ Reconnecting in {self.reconnect_delay} seconds...")
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    logger.error("✗ Max reconnection attempts reached. Giving up.")
                    raise
    
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
    
    async def _send_periodic_pong(self) -> None:
        """
        Send periodic pong frames every 5 minutes to keep WebSocket connection alive
        """
        try:
            while self.is_connected and self.websocket:
                await asyncio.sleep(300)  # 5 minutes
                await self.websocket.pong()
                logger.debug("Sent periodic pong frame to keep connection alive")
        except asyncio.CancelledError:
            logger.info("Periodic pong task cancelled")
        except Exception as e:
            logger.error(f"Error sending periodic pong: {e}")