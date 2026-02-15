# Project Execution Flow

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
    - FifteenMinuteStrategy (15-minute strategy)
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
    - kline_3m (3-minute K-line)
    - kline_5m (5-minute K-line)
    - kline_15m (15-minute K-line)
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

### 3.2 15-minute K-line Processing
```
15m K-line closes
    ↓
FifteenMinuteStrategy.on_15m_kline_close()
    ↓
TradingExecutor.close_all_positions()
    ↓
Close all positions
    ↓
PositionManager.reset_cycle()
    ↓
Reset cycle state
```

### 3.3 5-minute K-line Processing
```
5m K-line closes
    ↓
FifteenMinuteStrategy.on_5m_kline_close()
    ↓
Check if it's the first 5m K-line in 15m cycle
    ↓
If first 5m:
    ↓
Check if position can be opened (can_open_position)
    ↓
Execute opening position check logic
```

## 4. Opening Position Decision Flow

### 4.1 Opening Condition Check
```
_check_and_open_position(symbol)
    ↓
Get 3m K-line direction
    ↓
Get 5m K-line direction
    ↓
Check volume condition (ratio >= threshold)
    ↓
Check body ratio condition (body/range >= threshold)
    ↓
Check if both directions match
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
PositionManager.open_position()
    ↓
Record position information
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
PositionManager.open_position()
    ↓
Record position information
    ↓
Send opening notification to Telegram
```

## 6. Closing Position Execution Flow

### 6.1 15-minute K-line Close Position
```
15m K-line closes
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

### Time: 12:00:00
```
15m K-line starts
    ↓
PositionManager.set_15m_cycle_start()
    ↓
Record cycle start time
```

### Time: 12:05:00
```
First 5m K-line closes
    ↓
Check opening conditions:
    - 3m K-line direction: UP
    - 5m K-line direction: UP
    - Volume ratio >= 0.70
    - Body ratio >= 0.6
    ↓
All match → Open LONG position
    ↓
Send opening notification
```

### Time: 12:15:00
```
15m K-line closes
    ↓
Close LONG position
    ↓
Calculate PnL
    ↓
Send closing notification
    ↓
Reset cycle
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
│FifteenMinute    │
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
5. **Cycle Management**: 15m cycle tracked by PositionManager
6. **Position Management**: Full position (100%) with 10x leverage
7. **Risk Control**: Auto-close at 15m K-line close