"""
Position Manager
Manages trading positions for futures trading
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class PositionManager:
    """Manager for trading positions"""
    
    def __init__(self):
        """Initialize position manager"""
        self.positions: Dict[str, Dict] = {}  # symbol -> position info
        self.current_15m_start_time: Optional[int] = None
        self.has_opened_position_this_cycle: bool = False
    
    def set_15m_cycle_start(self, start_time: int) -> None:
        """
        Set the start time of current 15m cycle
        
        Args:
            start_time: Start time of 15m K-line
        """
        self.current_15m_start_time = start_time
        self.has_opened_position_this_cycle = False
        logger.info(f"New 15m cycle started at {datetime.fromtimestamp(start_time/1000)}")
    
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
    
    def open_position(self, symbol: str, side: str, entry_price: float, quantity: float) -> Dict:
        """
        Open a new position
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            quantity: Position quantity
            
        Returns:
            Position dictionary
        """
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'entry_time': datetime.now().timestamp(),
            'is_open': True
        }
        
        self.positions[symbol] = position
        self.has_opened_position_this_cycle = True
        
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
    
    def can_open_position(self) -> bool:
        """
        Check if a new position can be opened in current cycle
        
        Returns:
            True if position can be opened
        """
        return not self.has_opened_position_this_cycle
    
    def reset_cycle(self) -> None:
        """Reset cycle state"""
        self.has_opened_position_this_cycle = False
        logger.info("Cycle reset, ready for new position")