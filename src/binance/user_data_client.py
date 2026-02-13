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
        logger.info("[USER_WS] Starting connection process...")
        
        # Get listen key
        logger.info("[USER_WS] Fetching listen key from Binance API...")
        self.listen_key = await asyncio.to_thread(
            self.trading_executor.get_listen_key
        )
        
        if not self.listen_key:
            logger.error("[USER_WS] ✗ Failed to get listen key: listen_key is None or empty")
            raise RuntimeError("Failed to get listen key")
        
        logger.info(f"[USER_WS] ✓ Listen key obtained: {self.listen_key[:20]}...")
        
        # Build WebSocket URL per Binance docs: wss://fstream.binance.com/ws/<listenKey>
        url = f"wss://fstream.binance.com/ws/{self.listen_key}"
        logger.info(f"[USER_WS] Connecting to URL: wss://fstream.binance.com/ws/{self.listen_key[:20]}...")
        
        try:
            # Set timeout to avoid hanging
            logger.info("[USER_WS] Attempting WebSocket connection with 30s timeout...")
            self.websocket = await asyncio.wait_for(
                websockets.connect(url),
                timeout=30.0
            )
            self.is_connected = True
            logger.info("✓ Successfully connected to user data stream")
            logger.info(f"[USER_WS] Connection state: is_connected={self.is_connected}")
            
            # Start keep-alive task
            logger.info("[USER_WS] Starting keep-alive task...")
            self.keep_alive_task = asyncio.create_task(self._keep_alive_loop())
            logger.info("[USER_WS] ✓ Keep-alive task started")
            
            # 主动用 REST 获取一次余额（否则可能永远收不到）
            logger.info("[USER_WS] Fetching initial balance via REST API...")
            try:
                balance = await asyncio.to_thread(
                    self.trading_executor.get_account_balance
                )
                self.account_balance = balance
                logger.info(f"[USER_WS] ✓ Initial balance: {balance:.2f} USDC")
            except Exception as e:
                logger.error(f"[USER_WS] ✗ Failed to fetch initial balance: {e}")
                import traceback
                logger.error(traceback.format_exc())
        except asyncio.TimeoutError:
            logger.error("[USER_WS] ✗ User data stream connection timeout after 30 seconds")
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"[USER_WS] ✗ Failed to connect to user data stream: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.is_connected = False
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from user data stream"""
        logger.info("[USER_WS] Disconnecting from user data stream...")
        
        if self.keep_alive_task:
            logger.info("[USER_WS] Cancelling keep-alive task...")
            self.keep_alive_task.cancel()
            try:
                await self.keep_alive_task
                logger.info("[USER_WS] ✓ Keep-alive task cancelled")
            except asyncio.CancelledError:
                logger.info("[USER_WS] Keep-alive task cancelled (expected)")
        
        if self.websocket:
            logger.info("[USER_WS] Closing WebSocket connection...")
            await self.websocket.close()
            self.is_connected = False
            logger.info("Disconnected from user data stream")
        else:
            logger.warning("[USER_WS] No active WebSocket connection to disconnect")
    
    async def _keep_alive_loop(self) -> None:
        """Keep the listen key alive (every 30 minutes)"""
        logger.info("[USER_WS] Keep-alive loop started")
        while self.is_connected:
            try:
                # Wait 30 minutes
                logger.info("[USER_WS] Waiting 30 minutes before next keep-alive...")
                await asyncio.sleep(30 * 60)
                
                # Keep alive
                if self.listen_key:
                    logger.info("[USER_WS] Sending keep-alive request...")
                    success = await asyncio.to_thread(
                        self.trading_executor.keep_alive_listen_key,
                        self.listen_key
                    )
                    if success:
                        logger.info("[USER_WS] ✓ Listen key kept alive")
                    else:
                        logger.error("[USER_WS] ✗ Failed to keep listen key alive")
                        # May need to reconnect
                        break
            except asyncio.CancelledError:
                logger.info("[USER_WS] Keep-alive loop cancelled")
                break
            except Exception as e:
                logger.error(f"[USER_WS] ✗ Error in keep-alive loop: {e}")
                import traceback
                logger.error(traceback.format_exc())
        logger.info("[USER_WS] Keep-alive loop exited")
    
    async def _handle_message(self, message: str) -> None:
        """
        Handle incoming user data message
        
        Args:
            message: JSON message string
        """
        try:
            logger.debug(f"[USER_WS] Raw message received (length: {len(message)} bytes)")
            data = json.loads(message)
            
            # Determine message type
            if 'e' in data:
                event_type = data['e']
                logger.info(f"[USER_WS] ✓ Received event: {event_type}")
                
                if event_type == 'ACCOUNT_UPDATE':
                    logger.debug("[USER_WS] Processing ACCOUNT_UPDATE...")
                    self._process_account_update(data)
                    logger.debug("[USER_WS] ACCOUNT_UPDATE processed")
                elif event_type == 'ORDER_TRADE_UPDATE':
                    logger.debug("[USER_WS] Processing ORDER_TRADE_UPDATE...")
                    self._process_order_update(data)
                    logger.debug("[USER_WS] ORDER_TRADE_UPDATE processed")
                elif event_type == 'ACCOUNT_CONFIG_UPDATE':
                    logger.debug("[USER_WS] Processing ACCOUNT_CONFIG_UPDATE...")
                    self._process_account_config_update(data)
                    logger.debug("[USER_WS] ACCOUNT_CONFIG_UPDATE processed")
                else:
                    logger.warning(f"[USER_WS] Unknown user data event type: {event_type}")
            else:
                logger.warning(f"[USER_WS] Message has no event type field")
            
        except json.JSONDecodeError as e:
            logger.error(f"[USER_WS] ✗ Failed to parse user data message: {e}")
            logger.error(f"[USER_WS] Raw message: {message[:200]}...")
        except Exception as e:
            logger.error(f"[USER_WS] ✗ Error handling user data message: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _process_account_update(self, data: Dict) -> None:
        """
        Process account update
        
        Args:
            data: Account update data from Binance
        """
        try:
            logger.info("[USER_WS] Processing account update...")
            account_data = data.get('a', {})
            balances = account_data.get('B', [])
            
            logger.info(f"[USER_WS] Found {len(balances)} balance(s)")
            
            # Find USDC balance (Binance USDC-M Futures uses USDC)
            for balance in balances:
                asset = balance.get('a', '')
                
                if asset == 'USDC':
                    available_balance = float(balance.get('cw', 0))
                    self.account_balance = available_balance
                    
                    logger.info(f"[USER_WS] ✓ Account balance updated: {available_balance:.2f} USDC")

                    # Trigger callback
                    if self.callbacks['account_update']:
                        try:
                            logger.info("[USER_WS] Calling account_update callback...")
                            payload = {
                                'balance': available_balance,
                                'timestamp': data.get('E', 0)
                            }

                            if asyncio.iscoroutinefunction(self.callbacks['account_update']):
                                asyncio.create_task(
                                    self.callbacks['account_update'](payload)
                                )
                            else:
                                self.callbacks['account_update'](payload)
                            
                            logger.info("[USER_WS] ✓ Account_update callback completed")

                        except Exception as e:
                            logger.error(f"[USER_WS] ✗ Error in account update callback: {e}")
                            import traceback
                            logger.error(traceback.format_exc())

                    break

            # Update positions
            positions = account_data.get('P', [])
            logger.info(f"[USER_WS] Found {len(positions)} position(s)")
            
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
                    
                    logger.info(f"[USER_WS] Position updated: {symbol} amt={position_amt} pnl={unrealized_pnl:.2f}")
                    
                    # Trigger callback
                    if self.callbacks['position_update']:
                        try:
                            logger.info(f"[USER_WS] Calling position_update callback for {symbol}...")
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
                            logger.info(f"[USER_WS] ✓ Position_update callback completed for {symbol}")
                        except Exception as e:
                            logger.error(f"[USER_WS] ✗ Error in position update callback: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                elif symbol in self.positions:
                    # Position closed
                    del self.positions[symbol]
                    logger.info(f"[USER_WS] Position closed for {symbol}")
            
            logger.info("[USER_WS] Account update processing completed")
        
        except Exception as e:
            logger.error(f"[USER_WS] ✗ Error processing account update: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _process_order_update(self, data: Dict) -> None:
        """
        Process order update
        
        Args:
            data: Order update data from Binance
        """
        try:
            logger.info("[USER_WS] Processing order update...")
            order = data.get('o', {})
            symbol = order.get('s', '')
            order_status = order.get('X', '')
            
            logger.info(f"[USER_WS] Order update for {symbol}: {order_status}")
            
            # Trigger callback
            if self.callbacks['order_update']:
                try:
                    logger.info(f"[USER_WS] Calling order_update callback for {symbol}...")
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
                    logger.info(f"[USER_WS] ✓ Order_update callback completed for {symbol}")
                except Exception as e:
                    logger.error(f"[USER_WS] ✗ Error in order update callback: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info("[USER_WS] Order update processing completed")
        
        except Exception as e:
            logger.error(f"[USER_WS] ✗ Error processing order update: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
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
        logger.info("[USER_WS] Starting listen loop...")
        if not self.is_connected or not self.websocket:
            logger.error("[USER_WS] ✗ Cannot listen: User data stream is not connected")
            raise RuntimeError("User data stream is not connected")
        
        logger.info("[USER_WS] ✓ User data stream is connected, starting to receive messages...")
        message_count = 0
        
        try:
            async for message in self.websocket:
                message_count += 1
                if message_count % 10 == 0:
                    logger.info(f"[USER_WS] Received {message_count} messages so far...")
                await self._handle_message(message)
        except ConnectionClosedError as e:
            logger.error(f"[USER_WS] ✗ User data stream connection closed: {e}")
            logger.error(f"[USER_WS] Total messages received: {message_count}")
            self.is_connected = False
            if self.callbacks['error']:
                try:
                    self.callbacks['error']({'type': 'connection_closed', 'error': str(e)})
                except Exception as err:
                    logger.error(f"[USER_WS] Error in error callback: {err}")
        except Exception as e:
            logger.error(f"[USER_WS] ✗ Error while listening to user data: {e}")
            logger.error(f"[USER_WS] Total messages received: {message_count}")
            import traceback
            logger.error(traceback.format_exc())
            self.is_connected = False
    
    async def start(self) -> None:
        """Start user data stream connection and listening"""
        logger.info("Starting UserDataClient...")
        while True:
            try:
                logger.info("Attempting to connect to user data stream...")
                await self.connect()
                logger.info("Starting to listen for user data messages...")
                await self.listen()
                logger.warning("User data listen loop ended unexpectedly")
            except Exception as e:
                import traceback
                logger.error(f"UserDataClient.start() error: {e}")
                logger.error(traceback.format_exc())
                # Trigger error callback
                if self.callbacks['error']:
                    try:
                        error_dict = {'type': 'start_error', 'error': str(e)}
                        if asyncio.iscoroutinefunction(self.callbacks['error']):
                            await self.callbacks['error'](error_dict)
                        else:
                            self.callbacks['error'](error_dict)
                    except Exception as cb_err:
                        logger.error(f"Error callback raised exception: {cb_err}")
                logger.info("Reconnecting to user data stream in 5 seconds...")
                await asyncio.sleep(5)
        logger.error("UserDataClient.start() exited unexpectedly")
    
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