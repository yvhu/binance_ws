"""
Telegram Message Formatter
Formats messages for Telegram notifications
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageFormatter:
    """Formatter for Telegram messages"""
    
    @staticmethod
    def format_ticker_alert(ticker_data: Dict) -> str:
        """
        Format ticker data into a readable message
        
        Args:
            ticker_data: Ticker data dictionary
            
        Returns:
            Formatted message string
        """
        symbol = ticker_data.get('symbol', 'UNKNOWN')
        price = ticker_data.get('current_price', 0)
        change = ticker_data.get('price_change', 0)
        change_percent = ticker_data.get('price_change_percent', 0)
        high = ticker_data.get('high_price', 0)
        low = ticker_data.get('low_price', 0)
        volume = ticker_data.get('volume', 0)
        
        # Determine emoji based on price change
        emoji = "📈" if change_percent >= 0 else "📉"
        
        message = (
            f"{emoji} <b>{symbol} 价格提醒</b>\n\n"
            f"💰 当前价格: ${price:,.2f}\n"
            f"📊 24小时变化: {change:+.2f} ({change_percent:+.2f}%)\n"
            f"🔺 24小时最高: ${high:,.2f}\n"
            f"🔻 24小时最低: ${low:,.2f}\n"
            f"📦 24小时成交量: {volume:,.2f}\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    @staticmethod
    def format_signal_alert(symbol: str, signal_type: str, indicators: Dict, price: float) -> str:
        """
        Format trading signal alert
        
        Args:
            symbol: Trading pair symbol
            signal_type: Type of signal (BUY/SELL)
            indicators: Dictionary of indicator values
            price: Current price
            
        Returns:
            Formatted message string
        """
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        
        message = (
            f"{emoji} <b>{symbol} {signal_type} 信号</b>\n\n"
            f"💰 价格: ${price:,.2f}\n\n"
            f"📊 <b>指标:</b>\n"
        )
        
        # Add indicator values
        for key, value in indicators.items():
            if isinstance(value, float):
                message += f"  • {key}: {value:.4f}\n"
            else:
                message += f"  • {key}: {value}\n"
        
        message += f"\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_kline_update(kline_data: Dict) -> str:
        """
        Format kline (candlestick) update
        
        Args:
            kline_data: Kline data dictionary
            
        Returns:
            Formatted message string
        """
        symbol = kline_data.get('symbol', 'UNKNOWN')
        interval = kline_data.get('interval', '1m')
        open_price = kline_data.get('open', 0)
        high = kline_data.get('high', 0)
        low = kline_data.get('low', 0)
        close = kline_data.get('close', 0)
        volume = kline_data.get('volume', 0)
        is_closed = kline_data.get('is_closed', False)
        
        status = "✅ 已收盘" if is_closed else "⏳ 进行中"
        
        message = (
            f"🕯️ <b>{symbol} {interval} K线</b> {status}\n\n"
            f"📊 OHLCV:\n"
            f"  • 开盘: ${open_price:,.2f}\n"
            f"  • 最高: ${high:,.2f}\n"
            f"  • 最低: ${low:,.2f}\n"
            f"  • 收盘: ${close:,.2f}\n"
            f"  • 成交量: {volume:,.2f}\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    @staticmethod
    def format_error_message(error: str, context: Optional[str] = None) -> str:
        """
        Format error message
        
        Args:
            error: Error message
            context: Additional context information
            
        Returns:
            Formatted error message string
        """
        message = f"⚠️ <b>错误提醒</b>\n\n"
        
        if context:
            message += f"📍 上下文: {context}\n"
        
        message += f"❌ 错误: {error}\n"
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_system_status(status: str, details: Optional[Dict] = None) -> str:
        """
        Format system status message
        
        Args:
            status: System status (STARTED, STOPPED, ERROR, etc.)
            details: Additional status details
            
        Returns:
            Formatted status message string
        """
        emoji_map = {
            'STARTED': '🚀',
            'STOPPED': '🛑',
            'ERROR': '❌',
            'RECONNECTING': '🔄',
            'CONNECTED': '✅',
            'DISCONNECTED': '❌'
        }
        
        emoji = emoji_map.get(status, 'ℹ️')
        
        message = f"{emoji} <b>系统状态: {status}</b>\n\n"
        
        if details:
            for key, value in details.items():
                message += f"  • {key}: {value}\n"
        
        message += f"\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_summary_report(symbols: List[str], data: Dict) -> str:
        """
        Format summary report for multiple symbols
        
        Args:
            symbols: List of trading symbols
            data: Dictionary containing data for each symbol
            
        Returns:
            Formatted summary report string
        """
        message = "📊 <b>市场汇总报告</b>\n\n"
        
        for symbol in symbols:
            if symbol in data:
                symbol_data = data[symbol]
                price = symbol_data.get('current_price', 0)
                change = symbol_data.get('price_change_percent', 0)
                volume = symbol_data.get('volume', 0)
                
                emoji = "📈" if change >= 0 else "📉"
                message += (
                    f"{emoji} <b>{symbol}</b>\n"
                    f"  价格: ${price:,.2f}\n"
                    f"  24小时变化: {change:+.2f}%\n"
                    f"  成交量: {volume:,.2f}\n\n"
                )
        
        message += f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_trade_notification(symbol: str, side: str, price: float, quantity: float, leverage: int) -> str:
        """
        Format trade notification message
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            price: Entry price
            quantity: Position quantity
            leverage: Leverage multiplier
            
        Returns:
            Formatted message string
        """
        emoji = "🟢" if side == "LONG" else "🔴"
        side_cn = "做多" if side == "LONG" else "做空"
        position_value = price * quantity
        
        message = (
            f"{emoji} <b>仓位已开仓</b>\n\n"
            f"📊 交易对: {symbol}\n"
            f"📈 方向: {side_cn}\n"
            f"💰 开仓价格: ${price:,.2f}\n"
            f"📦 数量: {quantity:.4f}\n"
            f"💵 仓位价值: ${position_value:,.2f}\n"
            f"⚡ 杠杆: {leverage}倍\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    @staticmethod
    def format_close_notification(symbol: str, side: str, entry_price: float, exit_price: float, quantity: float, pnl: float) -> str:
        """
        Format position close notification message
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position quantity
            pnl: Profit/Loss
            
        Returns:
            Formatted message string
        """
        emoji = "✅" if pnl >= 0 else "❌"
        side_cn = "做多" if side == "LONG" else "做空"
        pnl_percent = (pnl / (entry_price * quantity)) * 100
        
        message = (
            f"{emoji} <b>仓位已平仓</b>\n\n"
            f"📊 交易对: {symbol}\n"
            f"📈 方向: {side_cn}\n"
            f"💰 开仓价格: ${entry_price:,.2f}\n"
            f"💰 平仓价格: ${exit_price:,.2f}\n"
            f"📦 数量: {quantity:.4f}\n"
            f"💵 盈亏: ${pnl:+,.2f} ({pnl_percent:+.2f}%)\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    @staticmethod
    def format_no_trade_notification(symbol: str, reason: str) -> str:
        """
        Format no trade notification message
        
        Args:
            symbol: Trading pair symbol
            reason: Reason for not trading
            
        Returns:
            Formatted message string
        """
        message = (
            f"⏭️ <b>未交易 - {symbol}</b>\n\n"
            f"📋 原因: {reason}\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        Escape special characters for MarkdownV2
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text