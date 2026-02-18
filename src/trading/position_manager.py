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
                        
                        # Calculate stop loss price for the synced position
                        stop_loss_price = None
                        if self.data_handler and self.config:
                            try:
                                # Get current price
                                current_price = self.data_handler.get_current_price(symbol)
                                
                                # Get latest 5m K-line data
                                klines_5m = self.data_handler.get_klines(symbol, '5m', limit=1)
                                if klines_5m and len(klines_5m) > 0:
                                    latest_kline = klines_5m[-1]
                                    current_range = latest_kline['high'] - latest_kline['low']
                                    
                                    # Get stop loss parameters from config
                                    stop_loss_range_multiplier = self.config.get('strategy.stop_loss_range_multiplier', 0.6)
                                    stop_loss_min_distance_percent = self.config.get('strategy.stop_loss_min_distance_percent', 0.005)
                                    
                                    # Calculate stop loss distance
                                    stop_loss_distance = current_range * stop_loss_range_multiplier
                                    min_stop_loss_distance = current_price * stop_loss_min_distance_percent
                                    final_stop_loss_distance = max(stop_loss_distance, min_stop_loss_distance)
                                    
                                    # Calculate stop loss price based on position side
                                    if side == 'LONG':
                                        stop_loss_price = current_price - final_stop_loss_distance
                                    else:  # SHORT
                                        stop_loss_price = current_price + final_stop_loss_distance
                                    
                                    logger.info(
                                        f"Calculated stop loss for synced position {symbol}: "
                                        f"current_price={current_price:.2f}, "
                                        f"range={current_range:.2f}, "
                                        f"stop_loss_price={stop_loss_price:.2f}"
                                    )
                            except Exception as e:
                                logger.error(f"Error calculating stop loss for synced position {symbol}: {e}")
                        
                        # Reconstruct position info
                        position_info = {
                            'symbol': symbol,
                            'side': side,
                            'entry_price': entry_price,
                            'quantity': quantity,
                            'entry_time': datetime.now().timestamp(),  # Use current time as we don't have original
                            'entry_kline': None,  # We don't have the original entry kline
                            'is_open': True,
                            'synced_from_exchange': True,  # Mark as synced from exchange
                            'stop_loss_price': stop_loss_price  # Add stop loss price
                        }
                        
                        self.positions[symbol] = position_info
                        
                        logger.warning(
                            f"⚠️ Position synced from exchange: {symbol} {side} "
                            f"qty={quantity} entry_price={entry_price:.2f} "
                            f"stop_loss={stop_loss_price:.2f if stop_loss_price else 'N/A'}"
                        )
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
    
    async def update_stop_loss_prices(self) -> None:
        """
        Update stop loss prices for all open positions
        This should be called after WebSocket is connected to ensure current price is available
        """
        if not self.positions:
            logger.info("No positions to update stop loss prices")
            return
        
        if not self.data_handler or not self.config:
            logger.warning("Data handler or config not available, cannot update stop loss prices")
            return
        
        logger.info(f"Updating stop loss prices for {len(self.positions)} position(s)...")
        
        import asyncio
        
        for symbol, position in self.positions.items():
            try:
                # Get current price
                current_price = self.data_handler.get_current_price(symbol)
                if current_price is None:
                    logger.warning(f"Could not get current price for {symbol}, skipping stop loss update")
                    continue
                
                # Get latest 5m K-line data
                klines_5m = self.data_handler.get_klines(symbol, '5m', limit=1)
                if not klines_5m or len(klines_5m) == 0:
                    logger.warning(f"No 5m K-line data for {symbol}, skipping stop loss update")
                    continue
                
                latest_kline = klines_5m[-1]
                current_range = latest_kline['high'] - latest_kline['low']
                
                if current_range == 0:
                    logger.warning(f"Current K-line range is zero for {symbol}, skipping stop loss update")
                    continue
                
                # Get stop loss parameters from config
                stop_loss_range_multiplier = self.config.get('strategy.stop_loss_range_multiplier', 0.8)
                stop_loss_min_distance_percent = self.config.get('strategy.stop_loss_min_distance_percent', 0.003)
                
                # Calculate stop loss distance
                stop_loss_distance = current_range * stop_loss_range_multiplier
                min_stop_loss_distance = current_price * stop_loss_min_distance_percent
                final_stop_loss_distance = max(stop_loss_distance, min_stop_loss_distance)
                
                # Calculate stop loss price based on position side
                position_side = position.get('side', 'LONG')
                if position_side == 'LONG':
                    stop_loss_price = current_price - final_stop_loss_distance
                else:  # SHORT
                    stop_loss_price = current_price + final_stop_loss_distance
                
                # Update stop loss price in position
                position['stop_loss_price'] = stop_loss_price
                
                logger.info(
                    f"✓ Updated stop loss for {symbol}: "
                    f"side={position_side}, "
                    f"current_price={current_price:.2f}, "
                    f"range={current_range:.2f}, "
                    f"stop_loss_price={stop_loss_price:.2f}"
                )
                
            except Exception as e:
                logger.error(f"Error updating stop loss for {symbol}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        logger.info("Stop loss price update completed")
    