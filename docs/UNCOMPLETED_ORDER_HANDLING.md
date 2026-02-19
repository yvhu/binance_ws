# 未完成限价单处理功能说明

## 概述

本系统实现了完整的未完成限价单处理机制，确保在市场条件变化时能够及时处理未成交的限价单，避免错过交易机会或承担不必要的风险。

## 配置参数

在 `config.toml` 的 `[trading.limit_order]` 部分添加了以下配置：

```toml
# 未完成订单处理策略
action_on_timeout = "convert_to_market"  # 超时处理: "cancel" 或 "convert_to_market"
action_on_signal_reversal = "cancel"     # 信号反转处理: "cancel" 或 "convert_to_market"
cancel_on_new_signal = true              # 检测到新信号时是否取消旧订单
max_pending_orders = 1                   # 每个交易对最大挂单数量
cancel_on_kline_close = false            # K线关闭时是否取消未成交订单
cancel_on_price_move_away = true         # 价格远离时是否取消订单
```

## 处理策略

### 1. 超时处理 (`action_on_timeout`)

当限价单超过配置的超时时间仍未成交时：

- **`cancel`**: 取消订单，不执行交易
- **`convert_to_market`**: 取消限价单，立即以市价单执行

**推荐配置**: `convert_to_market` - 确保不会错过交易机会

### 2. 信号反转处理 (`action_on_signal_reversal`)

当检测到市场信号反转时（例如做多信号变为做空信号）：

- **`cancel`**: 取消订单，等待新信号
- **`convert_to_market`**: 立即以市价单执行

**推荐配置**: `cancel` - 避免在信号反转时开仓

### 3. 新信号处理 (`cancel_on_new_signal`)

当检测到新的交易信号时：

- **`true`**: 取消该交易对的所有未完成限价单
- **`false`**: 保留未完成订单

**推荐配置**: `true` - 避免重复开仓

### 4. 最大挂单数量 (`max_pending_orders`)

限制每个交易对同时挂起的限价单数量：

- 当达到最大数量时，自动取消最旧的订单
- 防止资金被过多挂单占用

**推荐配置**: `1` - 保持简单，避免复杂管理

### 5. K线关闭处理 (`cancel_on_kline_close`)

当K线关闭时：

- **`true`**: 取消所有未成交的限价单
- **`false`**: 保留订单继续等待

**推荐配置**: `false` - 给订单更多成交机会

### 6. 价格远离处理 (`cancel_on_price_move_away`)

当价格远离限价单价格时（由监控器检测）：

- **`true`**: 取消订单或转换为市价单
- **`false`**: 保留订单

**推荐配置**: `true` - 避免在不利价格成交

## 实现细节

### 订单跟踪

系统使用 `pending_limit_orders` 字典跟踪所有未完成的限价单：

```python
self.pending_limit_orders: Dict[str, Dict] = {}
# 结构: {symbol: {order_id: {side, order_price, quantity, timestamp, ...}}}
```

### 关键方法

#### 1. `_check_and_cancel_pending_orders()`

取消指定交易对的所有未完成订单：

```python
async def _check_and_cancel_pending_orders(symbol: str, reason: str) -> None:
    """检查并取消未完成的限价单"""
```

#### 2. `_check_signal_reversal()`

检测信号反转并处理：

```python
async def _check_signal_reversal(symbol: str, current_kline: Dict) -> None:
    """检查信号是否反转并处理未完成订单"""
```

#### 3. `_convert_limit_to_market()`

将限价单转换为市价单：

```python
async def _convert_limit_to_market(symbol: str, order_id: int, 
                                   order_info: Dict, reason: str) -> bool:
    """将限价单转换为市价单"""
```

### 触发时机

未完成订单处理在以下时机触发：

1. **K线关闭时** (`on_5m_kline_close`)
   - 检查信号反转
   - 检查是否需要取消订单（如果配置了 `cancel_on_kline_close`）

2. **新开仓时** (`_open_long_position_with_limit_order`, `_open_short_position_with_limit_order`)
   - 检查是否需要取消旧订单（如果配置了 `cancel_on_new_signal`）
   - 检查是否达到最大挂单数量

3. **订单监控时** (`LimitOrderMonitor`)
   - 检查超时
   - 检查价格远离
   - 检查快速价格变化

## 使用示例

### 配置示例

```toml
[trading.limit_order]
enabled = true
entry_enabled = true
take_profit_enabled = true
entry_price_offset_percent = 0.001
take_profit_price_offset_percent = 0.001
entry_limit_order_timeout = 30
take_profit_limit_order_timeout = 60
price_away_threshold_percent = 0.002
rapid_change_threshold_percent = 0.003
rapid_change_window = 5
use_support_resistance = true
support_resistance_period = 20

# 未完成订单处理
action_on_timeout = "convert_to_market"
action_on_signal_reversal = "cancel"
cancel_on_new_signal = true
max_pending_orders = 1
cancel_on_kline_close = false
cancel_on_price_move_away = true
```

### 推荐配置组合

#### 保守型配置

```toml
action_on_timeout = "cancel"
action_on_signal_reversal = "cancel"
cancel_on_new_signal = true
max_pending_orders = 1
cancel_on_kline_close = true
cancel_on_price_move_away = true
```

**特点**: 更严格的风险控制，宁可错过交易也不在不利条件下开仓

#### 平衡型配置（推荐）

```toml
action_on_timeout = "convert_to_market"
action_on_signal_reversal = "cancel"
cancel_on_new_signal = true
max_pending_orders = 1
cancel_on_kline_close = false
cancel_on_price_move_away = true
```

**特点**: 平衡交易机会和风险控制

#### 激进型配置

```toml
action_on_timeout = "convert_to_market"
action_on_signal_reversal = "convert_to_market"
cancel_on_new_signal = false
max_pending_orders = 3
cancel_on_kline_close = false
cancel_on_price_move_away = false
```

**特点**: 最大化交易机会，但风险较高

## 通知机制

系统会在以下情况发送Telegram通知：

1. **取消订单**: 🚫 取消限价单
2. **转换为市价单**: 🔄 限价单转市价单
3. **信号反转**: ⚠️ 信号反转检测

通知内容包括：
- 交易对
- 原因
- 订单数量/方向
- 时间戳

## 注意事项

1. **API限制**: 频繁取消和下单可能触及API限制
2. **滑点风险**: 转换为市价单时可能产生滑点
3. **资金占用**: 多个挂单会占用保证金
4. **市场波动**: 在高波动市场，订单可能快速被触发

## 监控和日志

系统会记录以下日志：

- 订单创建和跟踪
- 订单取消原因
- 信号反转检测
- 转换为市价单操作
- 超时处理

建议定期检查日志以优化配置参数。

## 未来优化方向

1. **智能取消策略**: 基于市场波动率动态调整取消策略
2. **订单优先级**: 为不同订单设置优先级
3. **部分成交处理**: 处理部分成交的订单
4. **历史数据分析**: 分析历史订单成交率以优化参数