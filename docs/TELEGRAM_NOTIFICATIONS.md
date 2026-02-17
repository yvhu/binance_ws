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

Sent when analyzing entry conditions, including:
- Trading pair
- 5m K-line time (the specific K-line being analyzed)
- Current price
- 5m K-line direction
- Volume information (based on closed K-lines only)
- K-line range information
- Body ratio information
- Shadow ratio information
- Trend filter information (MA20)
- Trading decision

Example:
```
📊 BTCUSDC 指标分析

⏰ 5m K线时间: 2024-02-15 16:45:00

💰 当前价格: $50,000.00

📊 5m K线方向:
  • 🟢 上涨

📊 5m K线振幅:
  • 当前振幅: 150.00
  • 近5根平均: 120.00 (比例: 1.25x)
  • 阈值要求: ≥0.5x
  • 振幅检查: ✅ 通过

📊 5m K线实体比例:
  • 实体长度: 50.00
  • 整体振幅: 150.00
  • 实体比例: 0.3333
  • 阈值要求: ≥0.7
  • 实体检查: ❌ 未通过

📊 5m K线影线比例:
  • 上影线比例: 0.25
  • 下影线比例: 0.15
  • 阈值要求: <0.4
  • 影线检查: ✅ 通过

📊 趋势过滤 (MA20):
  • 当前价格: $50,000.00
  • MA20: $49,500.00
  • MA20方向: 上升
  • 价格位置: MA20上方
  • 趋势检查: ✅ 通过

📦 5m K线成交量 (基于已关闭K线):
  • 第一个5m成交量: 1,000.00
  • 近5根平均: 860.00 (比例: 1.16x)
  • 近10根平均: 848.00 (比例: 1.18x)
  • 阈值要求: ≥0.55x
  • 成交量检查: ✅ 通过

<b>交易决策:</b> 🟢 做多

⏰ 时间: 2024-02-15 16:45:05
```

**Important Notes:**
- Volume calculations are based on **closed K-lines only** to match Binance's display
- MA5 and MA10 include the current K-line (just closed) to match Binance's update timing
- The K-line time shown is the close time of the 5m K-line being analyzed

## Trading Notifications

### Position Opened Notification
Sent when a position is opened, including:
- Trading pair
- Direction (LONG/SHORT)
- Entry price
- Quantity
- Position value
- Leverage

Example (LONG):
```
🟢 仓位已开仓

📊 交易对: BTCUSDC
📈 方向: 做多
💰 开仓价格: $50,000.00
📦 数量: 0.2000
💵 仓位价值: $10,000.00
⚡ 杠杆: 10倍
⏰ 5m K线时间: 2024-02-15 16:45:00

💰 仓位计算详情:
  • 账户余额: $1,000.00
  • 最大仓位价值: $10,000.00
  • 开仓手续费: $4.0000
  • 安全边际: $100.0000
  • 可用仓位价值: $9,896.00
  • 所需保证金: $989.60

📦 5m K线成交量 (基于已关闭K线):
  • 第一个5m成交量: 1,000.00
  • 近5根平均: 860.00 (比例: 1.16x)
  • 近10根平均: 848.00 (比例: 1.18x)

⏰ 时间: 2024-02-15 16:45:05
```

Example (SHORT):
```
🔴 仓位已开仓

📊 交易对: BTCUSDC
📈 方向: 做空
💰 开仓价格: $50,000.00
📦 数量: 0.2000
💵 仓位价值: $10,000.00
⚡ 杠杆: 10倍
⏰ 5m K线时间: 2024-02-15 16:45:00

💰 仓位计算详情:
  • 账户余额: $1,000.00
  • 最大仓位价值: $10,000.00
  • 开仓手续费: $4.0000
  • 安全边际: $100.0000
  • 可用仓位价值: $9,896.00
  • 所需保证金: $989.60

📦 5m K线成交量 (基于已关闭K线):
  • 第一个5m成交量: 1,000.00
  • 近5根平均: 860.00 (比例: 1.16x)
  • 近10根平均: 848.00 (比例: 1.18x)

⏰ 时间: 2024-02-15 16:45:05
```

### Position Closed Notification
Sent when a position is closed, including:
- Trading pair
- Direction (LONG/SHORT)
- Entry price
- Exit price
- Quantity
- Profit/Loss (PnL)
- PnL percentage

Example (Profit):
```
✅ 仓位已平仓

📊 交易对: BTCUSDC
📈 方向: 做多
💰 开仓价格: $50,000.00
💰 平仓价格: $50,500.00
📦 数量: 0.2000
💵 盈亏: $100.00 (+1.00%)
⏰ 时间: 2024-02-15 16:46:00
```

Example (Loss):
```
❌ 仓位已平仓

📊 交易对: BTCUSDC
📈 方向: 做多
💰 开仓价格: $50,000.00
💰 平仓价格: $49,500.00
📦 数量: 0.2000
💵 盈亏: -$100.00 (-1.00%)
⏰ 时间: 2024-02-15 16:46:00
```

### No Trade Notification
Sent when no trade is executed, including:
- Trading pair
- Reason for not trading

Example:
```
⏭️ 未交易 - BTCUSDC

📋 原因: Directions mismatch: 3m=DOWN, 5m=UP
⏰ 时间: 2024-02-15 16:45:05
```

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
2. **Indicator Analysis**: When analyzing entry conditions (5m K-line closes)
3. **Position Open**: When strategy opens a position
4. **Position Close**: When stop loss is triggered or position is closed
5. **No Trade**: When entry conditions are not met
6. **Error**: When any error occurs in the system
7. **Shutdown**: When the bot stops gracefully

## Volume Calculation Notes

All volume-related calculations in notifications follow these rules:

1. **Closed K-lines Only**: Volume MA5 and MA10 are calculated using only closed K-lines to match Binance's display
2. **Include Current K-line**: When a K-line closes, the MA calculation includes this just-closed K-line to match Binance's update timing
3. **Calculation Timing**: Calculations are performed immediately after the 5m K-line closes
4. **Verification**: The K-line time displayed in notifications allows you to verify which K-line was used for calculations

This ensures that the volume ratios shown in notifications match exactly what you see on Binance's trading interface.