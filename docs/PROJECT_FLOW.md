# Project Execution Flow

> **注意**：本文档描述的是项目执行流程。策略已从15分钟K线策略更新为5分钟K线策略。请查看 [Strategy Flow](STRATEGY_FLOW.md) 获取最新的策略详情。

## 1. Project Startup Flow

### 1.1 Initialization Phase
```
main.py starts
    ↓
BinanceTelegramBot.__init__()
    ↓
Load configuration (ConfigManager)
    ↓
Initialize logging system
    ↓
Initialize components:
    - BinanceDataHandler (Data processor)
    - BinanceWSClient (WebSocket client)
    - TelegramClient (Telegram client)
    - TechnicalAnalyzer (Technical analyzer)
    - PositionManager (Position manager)
    - TradingExecutor (Trading executor)
    - FiveMinuteStrategy (5-minute strategy)
```

### 1.2 Startup Phase
```
bot.run()
    ↓
bot.initialize()
    ↓
Initialize Telegram client
    ↓
Start Telegram Bot
    ↓
Register WebSocket callbacks
    ↓
⚠️ Sync positions from exchange (CRITICAL SAFETY CHECK)
    ├── Query current positions from Binance API
    ├── Sync to local position manager
    ├── Check if each position has stop loss order
    └── Create stop loss order if missing
    ↓
Load historical kline data
    ↓
Register user data stream callbacks
    ↓
Send startup notification to Telegram
    ↓
Start Binance WebSocket connection
```

## 2. Data Reception Flow

### 2.1 WebSocket Connection
```
BinanceWSClient.start()
    ↓
Connect to Binance Futures WebSocket
    ↓
Subscribe to data streams:
- kline_5m (5-minute K-line)
- markPrice (Mark price)
- forceOrder (Force order)
```

### 2.2 Data Reception and Processing
```
WebSocket receives data
    ↓
Parse message type
    ↓
Call corresponding callback:
    - _on_kline() - K-line data
    - _on_mark_price() - Mark price
    - _on_force_order() - Force order
    - _on_error() - Error message
```

## 3. K-line Data Processing Flow

### 3.1 K-line Data Reception
```
_on_kline(kline_info)
    ↓
BinanceDataHandler.process_kline()
    ↓
Store K-line data in memory
    ↓
Check if K-line is closed (is_closed)
```

### 3.2 5-minute K-line Processing
```
5m K-line closes
    ↓
FiveMinuteStrategy.on_5m_kline_close()
    ↓
Check if position exists
    ↓
If position exists:
    ↓
    Check engulfing stop loss
    ↓
If no position exists:
    ↓
    Check opening conditions
    ↓
    Execute opening position logic

## 3.5 Startup Position and Stop Loss Check (CRITICAL SAFETY MECHANISM)

### 3.5.1 Position Sync from Exchange
```
PositionManager.sync_from_exchange(symbols)
    ↓
For each symbol:
    ↓
    Query position from Binance API
    ↓
    If position exists (positionAmt != 0):
        ↓
        Sync to local position manager
        ↓
        Check if stop loss order exists
        ↓
        If no stop loss order:
            ↓
            Calculate stop loss price based on:
            ├── Current price
            ├── Latest 5m K-line range
            └── Strategy config (stop_loss_range_multiplier, stop_loss_min_distance_percent)
            ↓
            Create STOP_MARKET order
            ↓
            Log success/failure
        ↓
    Else (no position on exchange):
        ↓
        Remove local position if exists
```

### 3.5.2 Stop Loss Price Calculation
```
Get current price
    ↓
Get latest 5m K-line
    ↓
Calculate current range = high - low
    ↓
Calculate stop loss distance:
    ├── If range > 0: distance = range × stop_loss_range_multiplier (0.8)
    └── If range == 0: distance = price × stop_loss_min_distance_percent (0.3%)
    ↓
Calculate stop loss price:
    ├── LONG: stop_loss_price = current_price - distance
    └── SHORT: stop_loss_price = current_price + distance
```

### 3.5.3 Purpose
- Avoid "logic empty but real has position" risk after restart
- Ensure all positions have stop loss protection
- Automatically recover from errors where position opened but stop loss failed
- Reduce need for manual intervention
- Provide automatic recovery mechanism

### 3.5.4 Implementation
- Location: [`../src/trading/position_manager.py`](../src/trading/position_manager.py:139)
- Method: `sync_from_exchange()`
- Called during: System initialization (bot.initialize())
```


## 4. Opening Position Decision Flow

### 4.1 Opening Condition Check
```
_check_and_open_position(symbol, kline_5m)
    ↓
Get 5m K-line direction
    ↓
Check volume condition (ratio >= threshold)
    ↓
Check range condition (ratio >= threshold)
    ↓
Check body ratio condition (body/range >= threshold)
    ↓
Check shadow ratio condition (shadow/range < threshold)
    ↓
Determine opening direction
```

### 4.2 Direction Judgment Logic
```
K-line direction judgment:
    - Compare close price with open price
    - Close > Open = UP
    - Close < Open = DOWN
```

### 4.3 Opening Execution
```
Both directions match
    ↓
Choose based on direction:
    - UP → _open_long_position()
    - DOWN → _open_short_position()
```

## 5. Opening Position Execution Flow

### 5.1 LONG Position Opening
```
_open_long_position(symbol)
    ↓
Get current price
    ↓
Calculate position size:
    ├── Get account balance
    ├── max_position_value = balance × leverage
    ├── opening_fee = max_position_value × fee_rate
    ├── safety_margin = max_position_value × safety_margin_rate
    ├── available_position_value = max_position_value - opening_fee - safety_margin
    ├── quantity = available_position_value / current_price
    ├── required_margin = available_position_value / leverage
    ├── Validate: required_margin <= balance
    └── Round quantity to symbol precision
    ↓
TradingExecutor.open_long_position()
    ↓
Re-check account balance
    ↓
Get latest current price
    ↓
Recalculate position size with latest balance and price:
    ├── Get account balance (latest)
    ├── max_position_value = balance × leverage
    ├── opening_fee = max_position_value × fee_rate
    ├── safety_margin = max_position_value × safety_margin_rate
    ├── available_position_value = max_position_value - opening_fee - safety_margin
    ├── quantity = available_position_value / current_price
    ├── required_margin = available_position_value / leverage
    ├── Validate: required_margin <= balance
    └── Round quantity to symbol precision
    ↓
Use recalculated quantity for order
    ↓
Send market buy order to Binance
    ↓
Check if order is filled:
    ├── If filled: Continue to next steps
    └── If not filled: Cancel all orders, return None (NO STOP LOSS SET)
    ↓
PositionManager.open_position()
    ↓
Record position information
    ↓
Set stop loss order (ONLY if opening succeeded):
    ├── If stop loss set successfully: Continue
    └── If stop loss failed:
        ├── Log CRITICAL error
        ├── Send emergency Telegram notification
        ├── Keep position open (NO auto-close)
        └── Rely on engulfing stop loss for protection
    ↓
Send opening notification to Telegram
```

### 5.2 SHORT Position Opening
```
_open_short_position(symbol)
    ↓
Get current price
    ↓
Calculate position size (same as LONG):
    ├── Get account balance
    ├── max_position_value = balance × leverage
    ├── opening_fee = max_position_value × fee_rate
    ├── safety_margin = max_position_value × safety_margin_rate
    ├── available_position_value = max_position_value - opening_fee - safety_margin
    ├── quantity = available_position_value / current price
    ├── required_margin = available_position_value / leverage
    ├── Validate: required_margin <= balance
    └── Round quantity to symbol precision
    ↓
TradingExecutor.open_short_position()
    ↓
Re-check account balance
    ↓
Get latest current price
    ↓
Recalculate position size with latest balance and price:
    ├── Get account balance (latest)
    ├── max_position_value = balance × leverage
    ├── opening_fee = max_position_value × fee_rate
    ├── safety_margin = max_position_value × safety_margin_rate
    ├── available_position_value = max_position_value - opening_fee - safety_margin
    ├── quantity = available_position_value / current price
    ├── required_margin = available_position_value / leverage
    ├── Validate: required_margin <= balance
    └── Round quantity to symbol precision
    ↓
Use recalculated quantity for order
    ↓
Send market sell order to Binance
    ↓
Check if order is filled:
    ├── If filled: Continue to next steps
    └── If not filled: Cancel all orders, return None (NO STOP LOSS SET)
    ↓
PositionManager.open_position()
    ↓
Record position information
    ↓
Set stop loss order (ONLY if opening succeeded):
    ├── If stop loss set successfully: Continue
    └── If stop loss failed:
        ├── Log CRITICAL error
        ├── Send emergency Telegram notification
        ├── Keep position open (NO auto-close)
        └── Rely on engulfing stop loss for protection
    ↓
Send opening notification to Telegram
```

## 6. Closing Position Execution Flow

### 6.1 Stop Loss Trigger
```
Fixed stop loss triggered
    ↓
STOP_MARKET order executes
    ↓
Position closed automatically
    ↓
Send closing notification to Telegram

OR

Engulfing stop loss triggered
    ↓
TradingExecutor.close_all_positions()
    ↓
Get current positions
    ↓
Send market closing order
    ↓
Calculate profit/loss
    ↓
PositionManager.close_position()
    ↓
Send closing notification to Telegram
```

## 7. Notification Sending Flow

### 7.1 System Status Notification
```
Startup/Stop event
    ↓
TelegramClient.send_system_status()
    ↓
MessageFormatter.format_system_status()
    ↓
Format message (Chinese)
    ↓
Send to Telegram
```

### 7.2 Trading Notification
```
Opening/Closing event
    ↓
TelegramClient.send_trade_notification()
    ↓
MessageFormatter.format_trade_notification()
    ↓
Format message (Chinese)
    ↓
Send to Telegram
```

### 7.3 Error Notification
```
Error event
    ↓
TelegramClient.send_error_message()
    ↓
MessageFormatter.format_error_message()
    ↓
Format message (Chinese)
    ↓
Send to Telegram
```

## 8. Error Handling Flow

### 8.1 WebSocket Error
```
WebSocket connection error
    ↓
_on_error(error_info)
    ↓
Log error
    ↓
Send error notification to Telegram
    ↓
Attempt reconnection (auto-reconnect)
```

### 8.2 Trading Error
```
Trading execution fails
    ↓
Log error
    ↓
Send error notification to Telegram
    ↓
Skip current trade
```

## 9. Shutdown Flow

### 9.1 Graceful Shutdown
```
Shutdown signal received
    ↓
bot.shutdown()
    ↓
Send shutdown notification to Telegram
    ↓
Disconnect Binance WebSocket
    ↓
Shutdown Telegram client
    ↓
Log shutdown complete
```

## 10. Complete Trading Cycle Example

### Time: 12:05:00
```
5m K-line closes
    ↓
Check opening conditions:
    - 5m K-line direction: UP
    - Volume ratio >= 0.70
    - Range ratio >= 0.7
    - Body ratio >= 0.6
    - Shadow ratio < 0.5
    ↓
All match → Open LONG position
    ↓
Check if order is filled:
    ├── If filled: Set stop loss order, Send opening notification
    └── If not filled: Cancel all orders, NO stop loss set, NO notification
```

### Time: 12:10:00
```
Next 5m K-line closes
    ↓
Check engulfing stop loss
    ↓
If engulfing pattern detected:
    ↓
    Close position immediately
    ↓
    Send closing notification
```

### Time: 12:15:00
```
Another 5m K-line closes
    ↓
If stop loss price hit:
    ↓
    Position closed automatically
    ↓
    Send closing notification
```

## Component Interaction Diagram

```
┌─────────────────┐
│   main.py       │
│  (Entry Point)  │
└────────┬────────┘
         │
         ├─────────────────────────────────────────────────────┐
         │                                                     │
         ▼                                                     ▼
┌─────────────────┐                                   ┌─────────────────┐
│ BinanceWSClient │◄──────────────────────────────────│  main.py        │
│  (WebSocket)    │                                   │  (Coordinator)  │
└────────┬────────┘                                   └────────┬────────┘
         │                                                      │
         │                                                      │
         ▼                                                      ▼
┌─────────────────┐                                   ┌─────────────────┐
│BinanceDataHandler│                                   │TelegramClient   │
│  (Data Storage) │                                   │ (Notifications) │
└────────┬────────┘                                   └─────────────────┘
         │
         │
         ▼
┌─────────────────┐
│  FiveMinute     │
│   Strategy      │
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│TechnicalAnalyzer│ │PositionManager  │ │TradingExecutor  │
│  (Indicators)   │ │ (Position Mgmt) │ │ (Order Execution)│
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Key Points

1. **Data Flow**: WebSocket → DataHandler → Strategy → TradingExecutor
2. **Decision Flow**: Strategy checks conditions → TradingExecutor executes orders
3. **Notification Flow**: All events → TelegramClient → Telegram
4. **Error Handling**: All errors logged and sent to Telegram
5. **Position Management**: Full position (100%) with configurable leverage
6. **Risk Control**: Fixed stop loss + Engulfing stop loss
7. **Strategy**: 5-minute K-line based trading strategy