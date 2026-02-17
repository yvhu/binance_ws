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
    def format_trade_notification(symbol: str, side: str, price: float, quantity: float, leverage: int,
                                   volume_info: Optional[Dict] = None,
                                   range_info: Optional[Dict] = None,
                                   stop_loss_price: Optional[float] = None,
                                   position_calc_info: Optional[Dict] = None,
                                   kline_time: Optional[int] = None) -> str:
        """
        Format trade notification message
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            price: Entry price
            quantity: Position quantity
            leverage: Leverage multiplier
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            stop_loss_price: Stop loss price (optional)
            position_calc_info: Position calculation information (optional)
            kline_time: K-line timestamp in milliseconds (optional)
            
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
        )
        
        # Add stop loss price if available
        if stop_loss_price is not None:
            stop_loss_distance = abs(stop_loss_price - price)
            stop_loss_percent = (stop_loss_distance / price) * 100
            message += f"🛡️ 止损价格: ${stop_loss_price:,.2f} (距离: {stop_loss_distance:.2f}, {stop_loss_percent:.2f}%)\n"
        
        # Add K-line time information
        if kline_time is not None:
            kline_datetime = datetime.fromtimestamp(kline_time / 1000)
            message += f"⏰ <b>5m K线时间:</b> {kline_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Add position calculation information if available
        if position_calc_info:
            balance = position_calc_info.get('balance', 0)
            max_position_value = position_calc_info.get('max_position_value', 0)
            opening_fee = position_calc_info.get('opening_fee', 0)
            safety_margin = position_calc_info.get('safety_margin', 0)
            available_position_value = position_calc_info.get('available_position_value', 0)
            required_margin = position_calc_info.get('required_margin', 0)
            
            message += (
                f"\n"
                f"💰 <b>仓位计算详情:</b>\n"
                f"  • 账户余额: ${balance:.2f}\n"
                f"  • 最大仓位价值: ${max_position_value:.2f}\n"
                f"  • 开仓手续费: ${opening_fee:.4f}\n"
                f"  • 安全边际: ${safety_margin:.4f}\n"
                f"  • 可用仓位价值: ${available_position_value:.2f}\n"
                f"  • 所需保证金: ${required_margin:.2f}\n"
            )
        
        # Add volume information if available
        if volume_info:
            current_volume = volume_info.get('current_volume', 0)
            avg_volume_5 = volume_info.get('avg_volume_5', 0)
            ratio_5 = volume_info.get('ratio_5', 0)
            
            message += (
                f"\n"
                f"📦 <b>5m K线成交量 (基于已关闭K线):</b>\n"
                f"  • 第一个5m成交量: {current_volume:,.2f}\n"
                f"  • 近5根平均: {avg_volume_5:,.2f} (比例: {ratio_5:.2f}x)\n"
            )
        
        # Add range information if available
        if range_info:
            current_range = range_info.get('current_range', 0)
            avg_range_5 = range_info.get('avg_range_5', 0)
            ratio_5 = range_info.get('ratio_5', 0)
            
            message += (
                f"\n"
                f"📊 <b>5m K线振幅 (基于已关闭K线):</b>\n"
                f"  • 第一个5m振幅: {current_range:.2f}\n"
                f"  • 近5根平均: {avg_range_5:.2f} (比例: {ratio_5:.2f}x)\n"
            )
        
        message += f"\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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
    def format_indicator_analysis(symbol: str, sar_direction: Optional[str], direction_3m: str, direction_5m: str,
                                   sar_value: Optional[float] = None, current_price: Optional[float] = None,
                                   decision: Optional[str] = None,
                                   volume_info: Optional[Dict] = None,
                                   range_info: Optional[Dict] = None,
                                   body_info: Optional[Dict] = None,
                                   kline_time: Optional[int] = None) -> str:
        """
        Format indicator analysis message
        
        Args:
            symbol: Trading pair symbol
            sar_direction: SAR direction (deprecated, always None)
            direction_3m: 3m K-line direction ('UP' or 'DOWN')
            direction_5m: 5m K-line direction ('UP' or 'DOWN')
            sar_value: SAR value (deprecated, always None)
            current_price: Current price (optional)
            decision: Trading decision (optional)
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            body_info: Body ratio information dictionary (optional)
            kline_time: K-line timestamp in milliseconds (optional)
            
        Returns:
            Formatted message string
        """
        # Direction emojis
        direction_emoji = {
            'UP': '🟢 上涨',
            'DOWN': '🔴 下跌'
        }
        
        # Decision emoji
        decision_emoji = {
            'LONG': '🟢 做多',
            'SHORT': '🔴 做空',
            'NO_TRADE': '⏭️ 不交易'
        }
        
        message = (
            f"📊 <b>{symbol} 指标分析</b>\n\n"
        )
        
        # Add K-line time information
        if kline_time is not None:
            kline_datetime = datetime.fromtimestamp(kline_time / 1000)
            message += f"⏰ <b>5m K线时间:</b> {kline_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if current_price is not None:
            message += f"💰 <b>当前价格:</b> ${current_price:,.2f}\n\n"
        
        message += (
            f"📊 <b>5m K线方向:</b>\n"
            f"  • {direction_emoji.get(direction_5m, direction_5m)}\n"
        )
        
        # Add volume information if available
        if volume_info:
            current_volume = volume_info.get('current_volume', 0)
            avg_volume_5 = volume_info.get('avg_volume_5', 0)
            ratio_5 = volume_info.get('ratio_5', 0)
            threshold = volume_info.get('threshold', 0)
            
            volume_valid = ratio_5 >= threshold
            volume_status = "✅ 通过" if volume_valid else "❌ 未通过"
            
            message += (
                f"\n"
                f"📦 <b>5m K线成交量 (基于已关闭K线):</b>\n"
                f"  • 第一个5m成交量: {current_volume:,.2f}\n"
                f"  • 近5根平均: {avg_volume_5:,.2f} (比例: {ratio_5:.2f}x)\n"
                f"  • 阈值要求: ≥{threshold:.2f}x\n"
                f"  • 成交量检查: {volume_status}\n"
            )
        
        # Add range information if available
        if range_info:
            current_range = range_info.get('current_range', 0)
            avg_range_5 = range_info.get('avg_range_5', 0)
            ratio_5 = range_info.get('ratio_5', 0)
            threshold = range_info.get('threshold', 0)
            
            range_valid = ratio_5 >= threshold
            range_status = "✅ 通过" if range_valid else "❌ 未通过"
            
            message += (
                f"\n"
                f"📊 <b>5m K线振幅 (基于已关闭K线):</b>\n"
                f"  • 第一个5m振幅: {current_range:.2f}\n"
                f"  • 近5根平均: {avg_range_5:.2f} (比例: {ratio_5:.2f}x)\n"
                f"  • 阈值要求: ≥{threshold:.2f}x\n"
                f"  • 振幅检查: {range_status}\n"
            )
        
        # Direction is determined by 5m K-line
        message += f"\n<b>交易方向:</b> {direction_emoji.get(direction_5m, direction_5m)}\n"
        
        # Add body ratio information if available
        if body_info:
            body = body_info.get('body', 0)
            range_val = body_info.get('range', 0)
            body_ratio = body_info.get('body_ratio', 0)
            upper_shadow = body_info.get('upper_shadow', 0)
            lower_shadow = body_info.get('lower_shadow', 0)
            upper_shadow_ratio = body_info.get('upper_shadow_ratio', 0)
            lower_shadow_ratio = body_info.get('lower_shadow_ratio', 0)
            threshold = body_info.get('threshold', 0)
            shadow_ratio_threshold = body_info.get('shadow_ratio_threshold', 0.5)
            
            body_valid = body_ratio >= threshold
            shadow_valid = upper_shadow_ratio < shadow_ratio_threshold and lower_shadow_ratio < shadow_ratio_threshold
            body_status = "✅ 通过" if (body_valid and shadow_valid) else "❌ 未通过"
            
            message += (
                f"\n"
                f"📊 <b>5m K线实体比例:</b>\n"
                f"  • 实体长度: {body:.2f}\n"
                f"  • 整体振幅: {range_val:.2f}\n"
                f"  • 实体比例: {body_ratio:.4f}\n"
                f"  • 上影线: {upper_shadow:.2f} ({upper_shadow_ratio:.1%})\n"
                f"  • 下影线: {lower_shadow:.2f} ({lower_shadow_ratio:.1%})\n"
                f"  • 阈值要求: 实体≥{threshold:.4f}, 单边影线<{shadow_ratio_threshold:.0%}\n"
                f"  • 实体检查: {body_status}\n"
            )
        
        if decision:
            message += f"\n<b>交易决策:</b> {decision_emoji.get(decision, decision)}\n"
        
        message += f"\n⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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