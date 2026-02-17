"""
Position Manager
Manages trading positions for futures trading
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PositionManager:
    """Manager for trading positions with state persistence"""
    
    def __init__(self, trading_executor=None, config=None, data_handler=None):
        """
        Initialize position manager
        
        Args:
            trading_executor: Trading executor instance for syncing positions from exchange
            config: Configuration manager instance for strategy parameters
            data_handler: Data handler instance for getting current price and K-line data
        """
        self.positions: Dict[str, Dict] = {}  # symbol -> position info
        self.trading_executor = trading_executor
        self.config = config
        self.data_handler = data_handler
    
    def has_position(self, symbol: str) -> bool:
        """
        Check if there is an open position for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if position exists
        """
        return symbol in self.positions and self.positions[symbol] is not None
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get position information for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Position dictionary or None
        """
        return self.positions.get(symbol)
    
    def open_position(self, symbol: str, side: str, entry_price: float, quantity: float, entry_kline: Optional[Dict] = None) -> Dict:
        """
        Open a new position
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            quantity: Position quantity
            entry_kline: Entry K-line data (optional)
            
        Returns:
            Position dictionary
        """
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_time': datetime.now().timestamp(),
            'entry_kline': entry_kline,
            'is_open': True
        }
        
        self.positions[symbol] = position
        
        logger.info(f"Opened {side} position for {symbol} at {entry_price}, quantity: {quantity}")
        
        return position
    
    def close_position(self, symbol: str, exit_price: float) -> Optional[Dict]:
        """
        Close an existing position
        
        Args:
            symbol: Trading pair symbol
            exit_price: Exit price
            
        Returns:
            Closed position dictionary or None
        """
        if not self.has_position(symbol):
            logger.warning(f"No position to close for {symbol}")
            return None
        
        position = self.positions[symbol]
        position['exit_price'] = exit_price
        position['exit_time'] = datetime.now().timestamp()
        position['is_open'] = False
        
        # Calculate PnL
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['quantity']
        else:  # SHORT
            pnl = (position['entry_price'] - exit_price) * position['quantity']
        
        position['pnl'] = pnl
        
        logger.info(f"Closed {position['side']} position for {symbol} at {exit_price}, PnL: {pnl}")
        
        # Remove from active positions
        del self.positions[symbol]
        
        return position
    
    def close_all_positions(self, exit_prices: Dict[str, float]) -> List[Dict]:
        """
        Close all open positions
        
        Args:
            exit_prices: Dictionary of symbol -> exit price
            
        Returns:
            List of closed position dictionaries
        """
        closed_positions = []
        
        for symbol in list(self.positions.keys()):
            if symbol in exit_prices:
                closed = self.close_position(symbol, exit_prices[symbol])
                if closed:
                    closed_positions.append(closed)
        
        return closed_positions
    
    async def sync_from_exchange(self, symbols: List[str]) -> None:
        """
        Sync positions from Binance exchange to ensure state persistence
        This should be called on startup to avoid "logic empty but real has position" risk
        
        Args:
            symbols: List of trading pair symbols to sync
        """
        if not self.trading_executor:
            logger.warning("Trading executor not provided, cannot sync positions from exchange")
            return
        
        logger.info(f"Syncing positions from exchange for {len(symbols)} symbol(s)...")
        
        import asyncio
        from binance.enums import SIDE_SELL, SIDE_BUY
        # Use string for order type to avoid enum compatibility issues
        ORDER_TYPE_STOP_MARKET = "STOP_MARKET"
        
        for symbol in symbols:
            try:
                # Get position from Binance API
                position = await asyncio.to_thread(self.trading_executor.get_position, symbol)
                
                if position:
                    position_amt = float(position.get('positionAmt', 0))
                    
                    if position_amt != 0:
                        # Determine position side
                        side = 'LONG' if position_amt > 0 else 'SHORT'
                        entry_price = float(position.get('entryPrice', 0))
                        quantity = abs(position_amt)
                        
                        # Reconstruct position info
                        position_info = {
                            'symbol': symbol,
                            'side': side,
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'entry_time': datetime.now().timestamp(),  # Use current time as we don't have original
                            'entry_kline': None,  # We don't have the original entry kline
                            'is_open': True,
                            'synced_from_exchange': True  # Mark as synced from exchange
                        }
                        
                        self.positions[symbol] = position_info
                        
                        logger.warning(
                            f"⚠️ Position synced from exchange: {symbol} {side} "
                            f"qty={quantity} entry_price={entry_price:.2f}"
                        )
                        
                        # Check if stop loss order exists
                        has_stop_loss = await asyncio.to_thread(
                            self.trading_executor.has_stop_loss_order,
                            symbol
                        )
                        
                        if not has_stop_loss:
                            logger.warning(f"⚠️ No stop loss order found for {symbol}, creating one...")
                            
                            # Calculate stop loss price based on current price and strategy config
                            if self.config and self.data_handler:
                                try:
                                    # Get strategy configuration
                                    stop_loss_range_multiplier = self.config.get_config(
                                        "strategy",
                                        "stop_loss_range_multiplier",
                                        default=0.8
                                    )
                                    stop_loss_min_distance_percent = self.config.get_config(
                                        "strategy",
                                        "stop_loss_min_distance_percent",
                                        default=0.003
                                    )
                                    
                                    # Get current price
                                    current_price = self.data_handler.get_current_price(symbol)
                                    if current_price is None:
                                        logger.error(f"Could not get current price for {symbol}")
                                        continue
                                    
                                    # Get latest 5m K-line to calculate range
                                    klines = self.data_handler.get_klines(symbol, "5m")
                                    if not klines:
                                        logger.warning(f"No K-line data for {symbol}, using minimum stop loss distance")
                                        # Use minimum stop loss distance as fallback
                                        stop_loss_distance = current_price * stop_loss_min_distance_percent
                                    else:
                                        # Get the latest closed K-line
                                        closed_klines = [k for k in klines if k.get('is_closed', False)]
                                        if closed_klines:
                                            latest_kline = closed_klines[-1]
                                            current_range = latest_kline['high'] - latest_kline['low']
                                            if current_range > 0:
                                                stop_loss_distance = current_range * stop_loss_range_multiplier
                                            else:
                                                stop_loss_distance = current_price * stop_loss_min_distance_percent
                                        else:
                                            stop_loss_distance = current_price * stop_loss_min_distance_percent
                                    
                                    # Calculate stop loss price
                                    if side == 'LONG':
                                        stop_loss_price = current_price - stop_loss_distance
                                    else:  # SHORT
                                        stop_loss_price = current_price + stop_loss_distance
                                    
                                    logger.info(
                                        f"Creating stop loss order for {symbol}: "
                                        f"side={side}, current_price={current_price:.2f}, "
                                        f"stop_loss_price={stop_loss_price:.2f}"
                                    )
                                    
                                    # Create stop loss order
                                    if side == 'LONG':
                                        order = await asyncio.to_thread(
                                            self.trading_executor.client.futures_create_order,
                                            symbol=symbol,
                                            side=SIDE_SELL,
                                            type=ORDER_TYPE_STOP_MARKET,
                                            stopPrice=stop_loss_price,
                                            quantity=quantity,
                                            reduceOnly=True
                                        )
                                    else:  # SHORT
                                        order = await asyncio.to_thread(
                                            self.trading_executor.client.futures_create_order,
                                            symbol=symbol,
                                            side=SIDE_BUY,
                                            type=ORDER_TYPE_STOP_MARKET,
                                            stopPrice=stop_loss_price,
                                            quantity=quantity,
                                            reduceOnly=True
                                        )
                                    
                                    logger.info(f"✓ Stop loss order created for {symbol}: {order}")
                                    
                                except Exception as e:
                                    logger.error(f"Failed to create stop loss order for {symbol}: {e}")
                                    import traceback
                                    logger.error(traceback.format_exc())
                            else:
                                logger.warning(
                                    f"Cannot create stop loss order for {symbol}: "
                                    f"config or data_handler not provided"
                                )
                        else:
                            logger.info(f"✓ Stop loss order already exists for {symbol}")
                    else:
                        # No position on exchange, ensure local state is also empty
                        if symbol in self.positions:
                            logger.info(f"Removing local position for {symbol} (no position on exchange)")
                            del self.positions[symbol]
                else:
                    # No position on exchange, ensure local state is also empty
                    if symbol in self.positions:
                        logger.info(f"Removing local position for {symbol} (no position on exchange)")
                        del self.positions[symbol]
                        
            except Exception as e:
                logger.error(f"Error syncing position for {symbol}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.info(f"Position sync completed. Current positions: {list(self.positions.keys())}")
    