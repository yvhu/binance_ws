"""
Binance Futures User Data Stream Client
Handles WebSocket connections for user account data (balance, positions, orders)
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from ..config.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class UserDataClient:
    """Binance user data stream client for account information"""
    
    def __init__(self, config: ConfigManager, trading_executor):
        """
        Initialize user data stream client
        
        Args:
            config: Configuration manager instance
            trading_executor: Trading executor for getting listen key
        """
        self.config = config
        self.trading_executor = trading_executor
        self.ws_url = config.binance_ws_url
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.listen_key: Optional[str] = None
        
        # Callbacks for different message types
        self.callbacks: Dict[str, Callable] = {
            'account_update': None,
            'order_update': None,
            'position_update': None,
            'error': None
        }
        
        # Account data storage
        self.account_balance: Optional[float] = None
        self.positions: Dict[str, Dict] = {}
        
        # Keep-alive task
        self.keep_alive_task: Optional[asyncio.Task] = None
    
    def on_account_update(self, callback: Callable) -> None:
        """
        Register callback for account updates
        
        Args:
            callback: Callback function to handle account updates
        """
        self.callbacks['account_update'] = callback
        logger.info("Registered callback for account updates")
    
    def on_order_update(self, callback: Callable) -> None:
        """
        Register callback for order updates
        
        Args:
            callback: Callback function to handle order updates
        """
        self.callbacks['order_update'] = callback
        logger.info("Registered callback for order updates")
    
    def on_position_update(self, callback: Callable) -> None:
        """
        Register callback for position updates
        
        Args:
            callback: Callback function to handle position updates
        """
        self.callbacks['position_update'] = callback
        logger.info("Registered callback for position updates")
    
    def on_error(self, callback: Callable) -> None:
        """
        Register callback for errors
        
        Args:
            callback: Callback function to handle errors
        """
        self.callbacks['error'] = callback
        logger.info("Registered callback for errors")
    
    async def connect(self) -> None:
        """Connect to Binance user data stream"""
        # Get listen key
        logger.info("Getting listen key for user data stream...")
        self.listen_key = self.trading_executor.get_listen_key()
        
        if not self.listen_key:
            raise RuntimeError("Failed to get listen key")
        
        # Build WebSocket URL
        url = f"{self.ws_url}/{self.listen_key}"
        logger.info(f"Connecting to user data stream: {url}")
        
        try:
            logger.info("Establishing user data stream connection...")
            # Set timeout to avoid hanging
            self.websocket = await asyncio.wait_for(
                websockets.connect(url),
                timeout=30.0
            )
            self.is_connected = True
            logger.info("✓ Successfully connected to user data stream")
            
            # Start keep-alive task
            self.keep_alive_task = asyncio.create_task(self._keep_alive_loop())
            
        except asyncio.TimeoutError:
            logger.error("✗ User data stream connection timeout after 30 seconds")
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"✗ Failed to connect to user data stream: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from user data stream"""
        if self.keep_alive_task:
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from user data stream")
    
    async def _keep_alive_loop(self) -> None:
        """Keep the listen key alive (every 30 minutes)"""
        while self.is_connected:
            try:
                # Wait 30 minutes
                await asyncio.sleep(30 * 60)
                
                # Keep alive
                if self.listen_key:
                    success = self.trading_executor.keep_alive_listen_key(self.listen_key)
                    if success:
                        logger.info("Listen key kept alive")
                    else:
                        logger.error("Failed to keep listen key alive")
                        # May need to reconnect
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in keep-alive loop: {e}")
    
    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming user data message
        
        Args:
            message: JSON message string
        """
        try:
            data = json.loads(message)
            
            # Determine message type
            if 'e' in data:
                event_type = data['e']
                
                if event_type == 'ACCOUNT_UPDATE':
                    self._process_account_update(data)
                elif event_type == 'ORDER_TRADE_UPDATE':
                    self._process_order_update(data)
                elif event_type == 'ACCOUNT_CONFIG_UPDATE':
                    self._process_account_config_update(data)
                else:
                    logger.warning(f"Unknown user data event type: {event_type}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse user data message: {e}")
        except Exception as e:
            logger.error(f"Error handling user data message: {e}")
    
    def _process_account_update(self, data: Dict) -> None:
        """
        Process account update
        
        Args:
            data: Account update data from Binance
        """
        try:
            account_data = data.get('a', {})
            balances = account_data.get('B', [])
            
            # Find USDC balance (Binance USDC-M Futures uses USDC)
            for balance in balances:
                asset = balance.get('a', '')
                if asset == 'USDC':
                    available_balance = float(balance.get('cw', 0))  # Cross wallet balance
                    self.account_balance = available_balance
                    logger.info(f"Account balance updated: {available_balance:.2f} USDC")
                    
                    # Trigger callback
                    if self.callbacks['account_update']:
                        try:
                            if asyncio.iscoroutinefunction(self.callbacks['account_update']):
                                asyncio.create_task(self.callbacks['account_update']({
                                    'balance': available_balance,
                                    'timestamp': data.get('E', 0)
                                }))
                            else:
                                self.callbacks['account_update']({
                                    'balance': available_balance,
                                    'timestamp': data.get('E', 0)
                                })
                        except Exception as e:
                            logger.error(f"Error in account update callback: {e}")
                    break
            
            # Update positions
            positions = account_data.get('P', [])
            for position in positions:
                symbol = position.get('s', '')
                position_amt = float(position.get('pa', 0))
                unrealized_pnl = float(position.get('up', 0))
                
                if position_amt != 0:
                    self.positions[symbol] = {
                        'amount': position_amt,
                        'unrealized_pnl': unrealized_pnl,
                        'entry_price': float(position.get('ep', 0)),
                        'mark_price': float(position.get('mp', 0))
                    }
                    
                    # Trigger callback
                    if self.callbacks['position_update']:
                        try:
                            if asyncio.iscoroutinefunction(self.callbacks['position_update']):
                                asyncio.create_task(self.callbacks['position_update']({
                                    'symbol': symbol,
                                    'amount': position_amt,
                                    'unrealized_pnl': unrealized_pnl,
                                    'entry_price': float(position.get('ep', 0)),
                                    'mark_price': float(position.get('mp', 0))
                                }))
                            else:
                                self.callbacks['position_update']({
                                    'symbol': symbol,
                                    'amount': position_amt,
                                    'unrealized_pnl': unrealized_pnl,
                                    'entry_price': float(position.get('ep', 0)),
                                    'mark_price': float(position.get('mp', 0))
                                })
                        except Exception as e:
                            logger.error(f"Error in position update callback: {e}")
                elif symbol in self.positions:
                    # Position closed
                    del self.positions[symbol]
                    logger.info(f"Position closed for {symbol}")
        
        except Exception as e:
            logger.error(f"Error processing account update: {e}")
    
    def _process_order_update(self, data: Dict) -> None:
        """
        Process order update
        
        Args:
            data: Order update data from Binance
        """
        try:
            order = data.get('o', {})
            symbol = order.get('s', '')
            order_status = order.get('X', '')
            
            logger.info(f"Order update for {symbol}: {order_status}")
            
            # Trigger callback
            if self.callbacks['order_update']:
                try:
                    if asyncio.iscoroutinefunction(self.callbacks['order_update']):
                        asyncio.create_task(self.callbacks['order_update']({
                            'symbol': symbol,
                            'order_id': order.get('i', 0),
                            'client_order_id': order.get('c', ''),
                            'side': order.get('S', ''),
                            'order_type': order.get('o', ''),
                            'status': order_status,
                            'price': float(order.get('p', 0)),
                            'quantity': float(order.get('q', 0)),
                            'executed_quantity': float(order.get('z', 0)),
                            'cumulative_quote_qty': float(order.get('Z', 0)),
                            'avg_price': float(order.get('ap', 0)),
                            'timestamp': data.get('E', 0)
                        }))
                    else:
                        self.callbacks['order_update']({
                            'symbol': symbol,
                            'order_id': order.get('i', 0),
                            'client_order_id': order.get('c', ''),
                            'side': order.get('S', ''),
                            'order_type': order.get('o', ''),
                            'status': order_status,
                            'price': float(order.get('p', 0)),
                            'quantity': float(order.get('q', 0)),
                            'executed_quantity': float(order.get('z', 0)),
                            'cumulative_quote_qty': float(order.get('Z', 0)),
                            'avg_price': float(order.get('ap', 0)),
                            'timestamp': data.get('E', 0)
                        })
                except Exception as e:
                    logger.error(f"Error in order update callback: {e}")
        
        except Exception as e:
            logger.error(f"Error processing order update: {e}")
    
    def _process_account_config_update(self, data: Dict) -> None:
        """
        Process account configuration update
        
        Args:
            data: Account config update data from Binance
        """
        try:
            logger.info(f"Account config update: {data}")
        except Exception as e:
            logger.error(f"Error processing account config update: {e}")
    
    async def listen(self) -> None:
        """Listen for incoming messages from user data stream"""
        if not self.is_connected or not self.websocket:
            raise RuntimeError("User data stream is not connected")
        
        logger.info("✓ Starting to listen for user data...")
        
        try:
            message_count = 0
            async for message in self.websocket:
                message_count += 1
                if message_count == 1:
                    logger.info("✓ First user data message received")
                elif message_count % 10 == 0:
                    logger.info(f"✓ Received {message_count} user data messages")
                await self._handle_message(message)
        except ConnectionClosedError as e:
            logger.error(f"✗ User data stream connection closed: {e}")
            self.is_connected = False
            if self.callbacks['error']:
                try:
                    self.callbacks['error']({'type': 'connection_closed', 'error': str(e)})
                except Exception as err:
                    logger.error(f"Error in error callback: {err}")
        except Exception as e:
            logger.error(f"✗ Error while listening to user data: {e}")
            self.is_connected = False
    
    async def start(self) -> None:
        """Start user data stream connection and listening"""
        try:
            await self.connect()
            await self.listen()
        except Exception as e:
            import traceback
            logger.error(f"✗ User data stream error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Trigger error callback
            if self.callbacks['error']:
                try:
                    error_dict = {'type': 'start_error', 'error': str(e)}
                    logger.debug(f"Calling error callback with: {error_dict}")
                    if asyncio.iscoroutinefunction(self.callbacks['error']):
                        await self.callbacks['error'](error_dict)
                    else:
                        self.callbacks['error'](error_dict)
                except Exception as err:
                    logger.error(f"Error in error callback: {err}")
                    logger.error(f"Error callback traceback: {traceback.format_exc()}")
            raise
    
    def get_account_balance(self) -> Optional[float]:
        """
        Get current account balance
        
        Returns:
            Account balance or None if not available
        """
        return self.account_balance
    
    def get_positions(self) -> Dict[str, Dict]:
        """
        Get current positions
        
        Returns:
            Dictionary of positions
        """
        return self.positions.copy()