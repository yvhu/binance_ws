# Telegram Notifications Documentation

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

  Trading Pairs: BTCUSDT
  Leverage: 10x
  Strategy: 15m K-line with SAR
  Position Size: 100% (Full Position)
  Streams: kline_3m, kline_5m, kline_15m

⏰ Time: 2024-01-01 12:00:00
```

### Shutdown Notification
Sent when the project stops

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
🟢 Position Opened

📊 Symbol: BTCUSDT
📈 Side: LONG
💰 Entry Price: $50,000.00
📦 Quantity: 0.2000
💵 Position Value: $10,000.00
⚡ Leverage: 10x
⏰ Time: 2024-01-01 12:05:00
```

Example (SHORT):
```
🔴 Position Opened

📊 Symbol: BTCUSDT
📈 Side: SHORT
💰 Entry Price: $50,000.00
📦 Quantity: 0.2000
💵 Position Value: $10,000.00
⚡ Leverage: 10x
⏰ Time: 2024-01-01 12:05:00
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
✅ Position Closed

📊 Symbol: BTCUSDT
📈 Side: LONG
💰 Entry Price: $50,000.00
💰 Exit Price: $50,500.00
📦 Quantity: 0.2000
💵 PnL: $100.00 (+1.00%)
⏰ Time: 2024-01-01 12:15:00
```

Example (Loss):
```
❌ Position Closed

📊 Symbol: BTCUSDT
📈 Side: LONG
💰 Entry Price: $50,000.00
💰 Exit Price: $49,500.00
📦 Quantity: 0.2000
💵 PnL: -$100.00 (-1.00%)
⏰ Time: 2024-01-01 12:15:00
```

### No Trade Notification
Sent when no trade is executed, including:
- Trading pair
- Reason for not trading

Example:
```
⏭️ No Trade - BTCUSDT

📋 Reason: Directions mismatch: SAR=UP, 3m=DOWN, 5m=UP
⏰ Time: 2024-01-01 12:05:00
```

## Error Notifications

### Error Alert
Sent when an error occurs, including:
- Error message
- Context information
- Timestamp

Example:
```
⚠️ Error Alert

📍 Context: WebSocket connection
❌ Error: Connection timeout
⏰ Time: 2024-01-01 12:00:00
```

## Message Format

All messages are formatted with:
- Emojis for visual clarity
- Markdown formatting for bold text
- Timestamps for reference
- Structured information display

## Notification Triggers

1. **Startup**: When `main.py` starts
2. **Position Open**: When strategy opens a position
3. **Position Close**: When 15m K-line closes
4. **No Trade**: When entry conditions are not met
5. **Error**: When any error occurs in the system
6. **Shutdown**: When the bot stops gracefully