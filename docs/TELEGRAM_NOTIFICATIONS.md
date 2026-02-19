# Telegram Notifications Documentation

## Overview

All Telegram notifications include timestamps for reference. Trading-related notifications also display the K-line time to help track which specific K-line triggered the action.

## System Status Notifications

### Startup Notification
Sent when the project starts, including:
- Trading pairs
- Leverage
- Strategy
- Position size
- Data streams

Example:
```
🚀 System Status: STARTED

  Trading Pairs: BTCUSDC
  Leverage: 10x
  Strategy: 5m K-line Strategy
  Position Size: 100% (Full Position)
  Streams: kline_5m

⏰ Time: 2024-01-01 12:00:00
```

### Shutdown Notification
Sent when the project stops

## Indicator Analysis Notification

**Only sent when there is a trading signal** (LONG or SHORT), including:
- Trading pair
- 5m K-line time (the specific K-line being analyzed)
- Current price
- 5m K-line direction
- Condition checks organized by category (Basic, Technical, Advanced)
- Signal strength
- Trading decision
- Detailed information

**Important Notes:**
- No notification is sent when there is no trading signal (reduces noise)
- Only sent when entry conditions are met
- Volume calculations are based on **closed K-lines only** to match Binance's display
- MA5 and MA10 include the current K-line (just closed) to match Binance's update timing
- The K-line time shown is the close time of the 5m K-line being analyzed

Example (Trade Decision):
```
🟢 做多 BTCUSDC 5m K线分析
──────────────────────────────
⏰ 16:45-16:50 | 💰 $50,000.00 | 🟢

📊 条件检查
  基础: 成交量 1.16x ✅ | 振幅 1.25x ✅ | 实体 33% ✅
  技术: MA20 ✅ | RSI 65 ✅ | MACD 0.0123 ✅ | ADX 28 ✅
  高级: 市场 趋势 75% ✅ | 多周期 2/2 ✅ | 情绪 55 (贪婪) ✅ | ML 做多 85% ✅

💪 信号强度: 💪 STRONG
🎯 交易决策: 🟢 做多

──────────────────────────────
📋 详细信息
  📦 成交量: 1,000 (平均: 860)
  📊 振幅: $150.00 (平均: $120.00)
  🕯️ 实体: $50.00 | 上影: $25.00 | 下影: $15.00
  📈 MA20: $49,500.00 📈
  😊 恐惧贪婪: 55 (贪婪)
  🤖 ML预测: 做多 (置信度: 85%)

⏰ 2024-02-15 16:45:05
```

**Key Improvements:**
- Conditions organized by category (Basic, Technical, Advanced)
- Compact format with visual separators
- Detailed information only shown for trade decisions
- Better visual hierarchy with emojis and formatting
- Easier to scan and understand at a glance
- **Reduced noise**: No notifications when there's no trading signal

## Trading Notifications

### Position Opened Notification
Sent when a position is opened, including:
- Trading pair
- Direction (LONG/SHORT)
- Entry price
- Quantity
- Position value
- Leverage
- Stop loss price (if set)
- K-line time
- Fund information (balance, margin, fees)
- Market data (volume, range)

Example (LONG):
```
🟢 仓位已开仓
──────────────────────────────
📊 交易对: BTCUSDC
📈 方向: 做多
💰 开仓价格: $50,000.00
📦 数量: 0.2000
💵 仓位价值: $10,000.00
⚡ 杠杆: 10倍
🛡️ 止损价格: $49,500.00 (1.00%)
⏰ K线时间: 16:45-16:50

💰 资金信息
  账户余额: $1,000.00
  所需保证金: $989.60
  开仓手续费: $4.0000

📊 市场数据
  成交量: 1,000 (1.16x)
  振幅: $150.00 (1.25x)

⏰ 2024-02-15 16:45:05
```

Example (SHORT):
```
🔴 仓位已开仓
──────────────────────────────
📊 交易对: BTCUSDC
📈 方向: 做空
💰 开仓价格: $50,000.00
📦 数量: 0.2000
💵 仓位价值: $10,000.00
⚡ 杠杆: 10倍
🛡️ 止损价格: $50,500.00 (1.00%)
⏰ K线时间: 16:45-16:50

💰 资金信息
  账户余额: $1,000.00
  所需保证金: $989.60
  开仓手续费: $4.0000

📊 市场数据
  成交量: 1,000 (1.16x)
  振幅: $150.00 (1.25x)

⏰ 2024-02-15 16:45:05
```

**Key Improvements:**
- Visual separator for better structure
- Simplified fund information (only essential details)
- Combined market data section
- Stop loss percentage shown directly
- Cleaner, more compact format

### Position Closed Notification
Sent when a position is closed, including:
- Trading pair
- Direction (LONG/SHORT)
- Entry price
- Exit price
- Quantity
- Profit/Loss (PnL)
- PnL percentage
- Close reason (formatted for readability)

Example (Profit):
```
✅ 仓位已平仓
──────────────────────────────
📊 交易对: BTCUSDC
📈 方向: 做多
💰 开仓价格: $50,000.00
💰 平仓价格: $50,500.00
📦 数量: 0.2000
💵 盈亏: $100.00 (+1.00%)

📋 平仓原因
  止盈触发

⏰ 2024-02-15 16:46:00
```

Example (Loss with detailed reason):
```
❌ 仓位已平仓
──────────────────────────────
📊 交易对: BTCUSDC
📈 方向: 做多
💰 开仓价格: $50,000.00
💰 平仓价格: $49,500.00
📦 数量: 0.2000
💵 盈亏: -$100.00 (-1.00%)

📋 平仓原因
  实时止损触发
  当前价格: $49,500.00
  止损价格: $49,500.00
  价格缓冲: $99.00 (0.20%)
  持续时间: 5.2s
  距离开仓: $500.00 (1.00%)

⏰ 2024-02-15 16:46:00
```

**Key Improvements:**
- Visual separator for better structure
- Close reason formatted as a separate section
- Multi-line reasons properly indented
- Cleaner, more readable format

## Error Notifications

### Error Alert
Sent when an error occurs, including:
- Error message
- Context information
- Timestamp

Example:
```
⚠️ 错误提醒

📍 上下文: WebSocket connection
❌ 错误: Connection timeout
⏰ 时间: 2024-02-15 16:45:00
```

## Message Format

All messages are formatted with:
- Emojis for visual clarity
- Markdown formatting for bold text
- Timestamps for reference
- Structured information display

## Notification Triggers

1. **Startup**: When `main.py` starts
2. **Indicator Analysis**: When analyzing entry conditions and a trading signal is detected (5m K-line closes)
3. **Position Open**: When strategy opens a position
4. **Position Close**: When stop loss is triggered or position is closed
5. **Error**: When any error occurs in the system
6. **Shutdown**: When the bot stops gracefully
7. **Trailing Stop Update**: When trailing stop loss is updated (if enabled)

**Important Note**: No notification is sent when entry conditions are not met (reduces noise)

## Trailing Stop Update Notification

Sent when trailing stop loss is updated (only if `trailing_stop_enabled = true`), including:
- Trading pair
- Position direction (LONG/SHORT)
- Entry price
- Current price
- Unrealized PnL
- Stop loss price change (old → new)
- Number of reference K-lines
- Lowest/Highest price in recent K-lines

Example (LONG):
```
🔄 移动止损更新

交易对: BTCUSDC
方向: LONG
开仓价格: $50000.00
当前价格: $51500.00
未实现盈亏: $1500.00
止损价格: $49000.00 → $50600.00
参考K线数: 3
最低价: $50600.00
```

Example (SHORT):
```
🔄 移动止损更新

交易对: BTCUSDC
方向: SHORT
开仓价格: $50000.00
当前价格: $48500.00
未实现盈亏: $1500.00
止损价格: $51000.00 → $49400.00
参考K线数: 3
最高价: $49400.00
```

**Important Notes:**
- This notification is only sent when trailing stop loss is enabled
- Stop loss price can only move in favorable direction (up for LONG, down for SHORT)
- The update is based on recent K-line highs/lows
- This notification helps track profit protection in real-time

## Volume Calculation Notes

All volume-related calculations in notifications follow these rules:

1. **Closed K-lines Only**: Volume MA5 and MA10 are calculated using only closed K-lines to match Binance's display
2. **Include Current K-line**: When a K-line closes, the MA calculation includes this just-closed K-line to match Binance's update timing
3. **Calculation Timing**: Calculations are performed immediately after the 5m K-line closes
4. **Verification**: The K-line time displayed in notifications allows you to verify which K-line was used for calculations

This ensures that the volume ratios shown in notifications match exactly what you see on Binance's trading interface.