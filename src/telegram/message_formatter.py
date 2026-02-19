"""
Telegram Message Formatter
Formats messages for Telegram notifications
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import html

logger = logging.getLogger(__name__)


class MessageFormatter:
    """Formatter for Telegram messages"""
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """
        Escape HTML special characters
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text safe for HTML parsing
        """
        return html.escape(str(text))
    
    @staticmethod
    def _format_percentage(value: float) -> str:
        """
        Format percentage value safely for HTML
        
        Args:
            value: Percentage value
            
        Returns:
            Formatted percentage string
        """
        return f"{value:.1f}%"
    
    @staticmethod
    def format_ticker_alert(ticker_data: Dict) -> str:
        """
        Format ticker data into a readable message
        
        Args:
            ticker_data: Ticker data dictionary
            
        Returns:
            Formatted message string
        """
        symbol = MessageFormatter._escape_html(ticker_data.get('symbol', 'UNKNOWN'))
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
        Format trading signal alert (deprecated - use format_indicator_analysis instead)
        
        Args:
            symbol: Trading pair symbol
            signal_type: Type of signal (BUY/SELL)
            indicators: Dictionary of indicator values
            price: Current price
            
        Returns:
            Formatted message string
        """
        emoji = "🟢" if signal_type == "BUY" else "🔴"
        symbol_escaped = MessageFormatter._escape_html(symbol)
        
        message = (
            f"{emoji} <b>{symbol_escaped} {signal_type} 信号</b>\n\n"
            f"💰 价格: ${price:,.2f}\n\n"
            f"📊 <b>指标:</b>\n"
        )
        
        # Add indicator values
        for key, value in indicators.items():
            key_escaped = MessageFormatter._escape_html(key)
            if isinstance(value, float):
                message += f"  • {key_escaped}: {value:.4f}\n"
            else:
                message += f"  • {key_escaped}: {MessageFormatter._escape_html(str(value))}\n"
        
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
        symbol = MessageFormatter._escape_html(kline_data.get('symbol', 'UNKNOWN'))
        interval = kline_data.get('interval', '5m')
        open_price = kline_data.get('open', 0)
        high = kline_data.get('high', 0)
        low = kline_data.get('low', 0)
        close = kline_data.get('close', 0)
        volume = kline_data.get('volume', 0)
        is_closed = kline_data.get('is_closed', False)
        
        status = "✅ 已收盘" if is_closed else "⏳ 进行中"
        
        # Calculate body and range
        body = abs(close - open_price)
        range_val = high - low
        body_ratio = (body / range_val * 100) if range_val > 0 else 0
        
        # Determine direction
        direction = "🟢 阳线" if close > open else "🔴 阴线"
        
        message = (
            f"🕯️ <b>{symbol} {interval} K线</b> {status} {direction}\n\n"
            f"📊 OHLCV:\n"
            f"  • 开盘: ${open_price:,.2f}\n"
            f"  • 最高: ${high:,.2f}\n"
            f"  • 最低: ${low:,.2f}\n"
            f"  • 收盘: ${close:,.2f}\n"
            f"  • 成交量: {volume:,.2f}\n"
            f"  • 振幅: ${range_val:.2f}\n"
            f"  • 实体比例: {MessageFormatter._format_percentage(body_ratio)}\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        return message
    
    @staticmethod
    def format_error_message(error: str, context: Optional[str] = None) -> str:
        """
        Format error message - Optimized for readability
        
        Args:
            error: Error message
            context: Additional context information
            
        Returns:
            Formatted error message string
        """
        message = f"⚠️ <b>错误提醒</b>\n"
        message += f"{'─' * 30}\n"
        
        if context:
            message += f"📍 上下文: {MessageFormatter._escape_html(context)}\n"
        
        message += f"❌ 错误: {MessageFormatter._escape_html(error)}\n"
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_system_status(status: str, details: Optional[Dict] = None) -> str:
        """
        Format system status message - Optimized for readability
        
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
        
        message = f"{emoji} <b>系统状态: {status}</b>\n"
        message += f"{'─' * 30}\n"
        
        if details:
            for key, value in details.items():
                key_escaped = MessageFormatter._escape_html(key)
                value_escaped = MessageFormatter._escape_html(str(value))
                message += f"  • {key_escaped}: {value_escaped}\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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
                symbol_escaped = MessageFormatter._escape_html(symbol)
                message += (
                    f"{emoji} <b>{symbol_escaped}</b>\n"
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
        Format trade notification message - Optimized for readability
        
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
        symbol_escaped = MessageFormatter._escape_html(symbol)
        
        message = f"{emoji} <b>仓位已开仓</b>\n"
        message += f"{'─' * 30}\n"
        message += f"📊 交易对: {symbol_escaped}\n"
        message += f"📈 方向: {side_cn}\n"
        message += f"💰 开仓价格: ${price:,.2f}\n"
        message += f"📦 数量: {quantity:.4f}\n"
        message += f"💵 仓位价值: ${position_value:,.2f}\n"
        message += f"⚡ 杠杆: {leverage}倍\n"
        
        # Add stop loss price if available
        if stop_loss_price is not None:
            stop_loss_distance = abs(stop_loss_price - price)
            stop_loss_percent = (stop_loss_distance / price) * 100
            message += f"🛡️ 止损价格: ${stop_loss_price:,.2f} ({stop_loss_percent:.2f}%)\n"
        
        # Add K-line time information
        if kline_time is not None:
            kline_end = datetime.fromtimestamp(kline_time / 1000)
            kline_start = kline_end.replace(minute=(kline_end.minute // 5) * 5, second=0, microsecond=0)
            kline_end_rounded = kline_start + timedelta(minutes=5)
            message += f"⏰ K线时间: {kline_start.strftime('%H:%M')}-{kline_end_rounded.strftime('%H:%M')}\n"
        
        # Add position calculation information if available
        if position_calc_info:
            balance = position_calc_info.get('balance', 0)
            required_margin = position_calc_info.get('required_margin', 0)
            opening_fee = position_calc_info.get('opening_fee', 0)
            
            message += f"\n<b>💰 资金信息</b>\n"
            message += f"  账户余额: ${balance:.2f}\n"
            message += f"  所需保证金: ${required_margin:.2f}\n"
            message += f"  开仓手续费: ${opening_fee:.4f}\n"
        
        # Add volume and range information if available
        if volume_info or range_info:
            message += f"\n<b>📊 市场数据</b>\n"
            if volume_info:
                current_volume = volume_info.get('current_volume', 0)
                ratio_5 = volume_info.get('ratio_5', 0)
                message += f"  成交量: {current_volume:,.0f} ({ratio_5:.2f}x)\n"
            if range_info:
                current_range = range_info.get('current_range', 0)
                ratio_5 = range_info.get('ratio_5', 0)
                message += f"  振幅: ${current_range:.2f} ({ratio_5:.2f}x)\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_close_notification(symbol: str, side: str, entry_price: float, exit_price: float, quantity: float, pnl: float,
                                   close_reason: str = "止损触发") -> str:
        """
        Format position close notification message - Optimized for readability
        
        Args:
            symbol: Trading pair symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            exit_price: Exit price
            quantity: Position quantity
            pnl: Profit/Loss
            close_reason: Reason for closing position (default: "止损触发")
            
        Returns:
            Formatted message string
        """
        emoji = "✅" if pnl >= 0 else "❌"
        side_cn = "做多" if side == "LONG" else "做空"
        pnl_percent = (pnl / (entry_price * quantity)) * 100
        symbol_escaped = MessageFormatter._escape_html(symbol)
        
        message = f"{emoji} <b>仓位已平仓</b>\n"
        message += f"{'─' * 30}\n"
        message += f"📊 交易对: {symbol_escaped}\n"
        message += f"📈 方向: {side_cn}\n"
        message += f"💰 开仓价格: ${entry_price:,.2f}\n"
        message += f"💰 平仓价格: ${exit_price:,.2f}\n"
        message += f"📦 数量: {quantity:.4f}\n"
        message += f"💵 盈亏: ${pnl:+,.2f} ({pnl_percent:+.2f}%)\n"
        
        # Format close reason more cleanly
        if close_reason:
            message += f"\n<b>📋 平仓原因</b>\n"
            # Split multi-line reasons
            for line in close_reason.split('\n'):
                if line.strip():
                    message += f"  {line.strip()}\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_no_trade_notification(symbol: str, reason: str, kline_time: Optional[int] = None) -> str:
        """
        Format no trade notification message - Optimized for readability
        
        Args:
            symbol: Trading pair symbol
            reason: Reason for not trading
            kline_time: K-line timestamp in milliseconds (optional)
            
        Returns:
            Formatted message string
        """
        symbol_escaped = MessageFormatter._escape_html(symbol)
        
        message = f"⏭️ <b>未交易 - {symbol_escaped}</b>\n"
        message += f"{'─' * 30}\n"
        
        # Format reason more cleanly
        if reason:
            message += f"<b>📋 原因</b>\n"
            # Split multi-line reasons
            for line in reason.split('\n'):
                if line.strip():
                    message += f"  {line.strip()}\n"
        
        # Add K-line time information
        if kline_time is not None:
            kline_end = datetime.fromtimestamp(kline_time / 1000)
            kline_start = kline_end.replace(minute=(kline_end.minute // 5) * 5, second=0, microsecond=0)
            kline_end_rounded = kline_start + timedelta(minutes=5)
            message += f"\n⏰ K线时间: {kline_start.strftime('%H:%M')}-{kline_end_rounded.strftime('%H:%M')}\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message
    
    @staticmethod
    def format_indicator_analysis(symbol: str, sar_direction: Optional[str], direction_3m: Optional[str], direction_5m: str,
                                   sar_value: Optional[float] = None, current_price: Optional[float] = None,
                                   decision: Optional[str] = None,
                                   volume_info: Optional[Dict] = None,
                                   range_info: Optional[Dict] = None,
                                   body_info: Optional[Dict] = None,
                                   trend_info: Optional[Dict] = None,
                                   rsi_info: Optional[Dict] = None,
                                   macd_info: Optional[Dict] = None,
                                   adx_info: Optional[Dict] = None,
                                   market_env_info: Optional[Dict] = None,
                                   multi_timeframe_info: Optional[Dict] = None,
                                   sentiment_info: Optional[Dict] = None,
                                   ml_info: Optional[Dict] = None,
                                   signal_strength: str = 'MEDIUM',
                                   kline_time: Optional[int] = None) -> str:
        """
        Format indicator analysis message - Optimized version with better readability
        
        Args:
            symbol: Trading pair symbol
            sar_direction: SAR direction (deprecated, always None)
            direction_3m: 3m K-line direction (deprecated, always None)
            direction_5m: 5m K-line direction ('UP' or 'DOWN')
            sar_value: SAR value (deprecated, always None)
            current_price: Current price (optional)
            decision: Trading decision (optional)
            volume_info: Volume information dictionary (optional)
            range_info: Range information dictionary (optional)
            body_info: Body ratio information dictionary (optional)
            trend_info: Trend filter information dictionary (optional)
            rsi_info: RSI filter information dictionary (optional)
            macd_info: MACD filter information dictionary (optional)
            adx_info: ADX filter information dictionary (optional)
            market_env_info: Market environment information dictionary (optional)
            multi_timeframe_info: Multi-timeframe analysis information dictionary (optional)
            sentiment_info: Sentiment filter information dictionary (optional)
            ml_info: ML filter information dictionary (optional)
            signal_strength: Signal strength (STRONG/MEDIUM/WEAK)
            kline_time: K-line timestamp in milliseconds (optional)
            
        Returns:
            Formatted message string
        """
        # Direction emojis
        direction_emoji = {
            'UP': '🟢',
            'DOWN': '🔴'
        }
        
        # Decision emoji and text
        decision_emoji = {
            'LONG': '🟢 做多',
            'SHORT': '🔴 做空',
            'NO_TRADE': '⏭️ 不交易'
        }
        
        # Signal strength emoji
        strength_emoji = {
            'STRONG': '💪',
            'MEDIUM': '👍',
            'WEAK': '👌'
        }
        
        symbol_escaped = MessageFormatter._escape_html(symbol)
        
        # Build header with decision
        header_emoji = decision_emoji.get(decision, '📊') if decision else '📊'
        message = f"{header_emoji} <b>{symbol_escaped} 5m K线分析</b>\n"
        message += f"{'─' * 30}\n"
        
        # Add K-line time and price in one line
        if kline_time is not None:
            kline_end = datetime.fromtimestamp(kline_time / 1000)
            kline_start = kline_end.replace(minute=(kline_end.minute // 5) * 5, second=0, microsecond=0)
            kline_end_rounded = kline_start + timedelta(minutes=5)
            time_str = f"{kline_start.strftime('%H:%M')}-{kline_end_rounded.strftime('%H:%M')}"
        else:
            time_str = "N/A"
        
        price_str = f"${current_price:,.2f}" if current_price else "N/A"
        direction_str = direction_emoji.get(direction_5m, direction_5m)
        message += f"⏰ {time_str} | 💰 {price_str} | {direction_str}\n\n"
        
        # Build condition summary - organized by category
        message += "<b>📊 条件检查</b>\n"
        
        # Basic conditions (Volume, Range, Body)
        basic_conditions = []
        if volume_info:
            ratio_5 = volume_info.get('ratio_5', 0)
            threshold = volume_info.get('threshold', 0)
            volume_valid = ratio_5 >= threshold
            basic_conditions.append(f"成交量 {ratio_5:.2f}x {'✅' if volume_valid else '❌'}")
        
        if range_info:
            ratio_5 = range_info.get('ratio_5', 0)
            threshold = range_info.get('threshold', 0)
            range_valid = ratio_5 >= threshold
            basic_conditions.append(f"振幅 {ratio_5:.2f}x {'✅' if range_valid else '❌'}")
        
        if body_info:
            body_ratio = body_info.get('body_ratio', 0)
            threshold = body_info.get('threshold', 0)
            upper_shadow_ratio = body_info.get('upper_shadow_ratio', 0)
            lower_shadow_ratio = body_info.get('lower_shadow_ratio', 0)
            shadow_ratio_threshold = body_info.get('shadow_ratio_threshold', 0.5)
            body_valid = body_ratio >= threshold
            shadow_valid = upper_shadow_ratio < shadow_ratio_threshold and lower_shadow_ratio < shadow_ratio_threshold
            basic_conditions.append(f"实体 {body_ratio*100:.0f}% {'✅' if (body_valid and shadow_valid) else '❌'}")
        
        if basic_conditions:
            message += "  基础: " + " | ".join(basic_conditions) + "\n"
        
        # Technical indicators (Trend, RSI, MACD, ADX)
        tech_conditions = []
        if trend_info:
            trend_aligned = trend_info.get('trend_aligned', False)
            ma_period = trend_info.get('ma_period', 20)
            tech_conditions.append(f"MA{ma_period} {'✅' if trend_aligned else '❌'}")
        
        if rsi_info:
            rsi_valid = rsi_info.get('rsi_valid', False)
            rsi_value = rsi_info.get('rsi_value', 0)
            tech_conditions.append(f"RSI {rsi_value:.0f} {'✅' if rsi_valid else '❌'}")
        
        if macd_info:
            macd_valid = macd_info.get('is_valid', False)
            macd_histogram = macd_info.get('histogram', 0)
            tech_conditions.append(f"MACD {macd_histogram:.4f} {'✅' if macd_valid else '❌'}")
        
        if adx_info:
            adx_valid = adx_info.get('adx_valid', False)
            adx_value = adx_info.get('adx_value', 0)
            tech_conditions.append(f"ADX {adx_value:.0f} {'✅' if adx_valid else '❌'}")
        
        if tech_conditions:
            message += "  技术: " + " | ".join(tech_conditions) + "\n"
        
        # Advanced conditions (Market, Multi-timeframe, Sentiment, ML)
        advanced_conditions = []
        if market_env_info:
            market_type = market_env_info.get('market_type', 'UNKNOWN')
            confidence = market_env_info.get('confidence', 0)
            env_valid = market_env_info.get('is_valid', False)
            advanced_conditions.append(f"市场 {market_type[:2]} {confidence:.0f}% {'✅' if env_valid else '❌'}")
        
        if multi_timeframe_info:
            aligned_count = multi_timeframe_info.get('aligned_count', 0)
            total_count = multi_timeframe_info.get('total_count', 0)
            mt_valid = aligned_count >= 2
            advanced_conditions.append(f"多周期 {aligned_count}/{total_count} {'✅' if mt_valid else '❌'}")
        
        if sentiment_info:
            fear_greed_value = sentiment_info.get('value', 0)
            fear_greed_classification = sentiment_info.get('classification', 'N/A')
            sentiment_valid = sentiment_info.get('is_valid', False)
            advanced_conditions.append(f"情绪 {fear_greed_value} ({fear_greed_classification[:2]}) {'✅' if sentiment_valid else '❌'}")
        
        if ml_info:
            prediction = ml_info.get('prediction', 'N/A')
            confidence = ml_info.get('confidence', 0)
            ml_valid = ml_info.get('ml_valid', False)
            advanced_conditions.append(f"ML {prediction[:2]} {confidence:.0%} {'✅' if ml_valid else '❌'}")
        
        if advanced_conditions:
            message += "  高级: " + " | ".join(advanced_conditions) + "\n"
        
        # Add signal strength and decision
        message += f"\n<b>💪 信号强度:</b> {strength_emoji.get(signal_strength, signal_strength)} {signal_strength}\n"
        
        if decision:
            message += f"<b>🎯 交易决策:</b> {decision_emoji.get(decision, decision)}\n"
        
        # Add detailed info only for trade decisions
        if decision and decision != 'NO_TRADE':
            message += f"\n{'─' * 30}\n"
            message += "<b>📋 详细信息</b>\n"
            
            # Volume details
            if volume_info:
                current_volume = volume_info.get('current_volume', 0)
                avg_volume_5 = volume_info.get('avg_volume_5', 0)
                message += f"  📦 成交量: {current_volume:,.0f} (平均: {avg_volume_5:,.0f})\n"
            
            # Range details
            if range_info:
                current_range = range_info.get('current_range', 0)
                avg_range_5 = range_info.get('avg_range_5', 0)
                message += f"  📊 振幅: ${current_range:.2f} (平均: ${avg_range_5:.2f})\n"
            
            # Body details
            if body_info:
                body = body_info.get('body', 0)
                range_val = body_info.get('range', 0)
                upper_shadow = body_info.get('upper_shadow', 0)
                lower_shadow = body_info.get('lower_shadow', 0)
                message += f"  🕯️ 实体: ${body:.2f} | 上影: ${upper_shadow:.2f} | 下影: ${lower_shadow:.2f}\n"
            
            # Trend details
            if trend_info:
                ma_value = trend_info.get('ma_value', 0)
                ma_direction = trend_info.get('ma_direction', 'UNKNOWN')
                ma_direction_emoji = '📈' if ma_direction == 'UP' else '📉'
                message += f"  📈 MA20: ${ma_value:,.2f} {ma_direction_emoji}\n"
            
            # Sentiment details
            if sentiment_info:
                fear_greed_value = sentiment_info.get('value', 0)
                fear_greed_classification = sentiment_info.get('classification', 'N/A')
                message += f"  😊 恐惧贪婪: {fear_greed_value} ({fear_greed_classification})\n"
            
            # ML details
            if ml_info:
                prediction = ml_info.get('prediction', 'N/A')
                confidence = ml_info.get('confidence', 0)
                score = ml_info.get('score', 0)
                message += f"  🤖 ML预测: {prediction} (置信度: {confidence:.0%})\n"
        
        message += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!', '%']
        
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text