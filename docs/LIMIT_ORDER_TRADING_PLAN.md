# 限价单交易方案设计文档

## 一、方案概述

### 1.1 目标
- 降低交易成本：使用限价单享受maker费率（0.02%）而非taker费率（0.04%）
- 提高成交质量：在更优价格成交
- 防止无法成交：实时监控，必要时转为市价单
- 控制风险：止损时确保及时平仓

### 1.2 核心原则
1. **开仓**：优先使用限价单，等待价格回调/反弹
2. **平仓**：止盈使用限价单，止损使用市价单（确保及时性）
3. **实时监控**：持续监控价格变化，防止错失机会
4. **风险控制**：价格快速远离时立即转为市价单

---

## 二、开仓限价单策略

### 2.1 价格计算方法

#### 方案A：固定偏移法（简单）
```python
# 做多：等待价格回调
limit_price = current_price * (1 - entry_price_offset_percent)

# 做空：等待价格反弹
limit_price = current_price * (1 + entry_price_offset_percent)
```

**配置参数**：
- `entry_price_offset_percent = 0.001` (0.1%)
- `entry_price_offset_max_percent = 0.002` (0.2%)

#### 方案B：技术指标法（推荐）
```python
# 做多：使用支撑位
limit_price = min(
    current_price * (1 - entry_price_offset_percent),
    recent_low,  # 最近N根K线的最低点
    support_level  # 支撑位
)

# 做空：使用阻力位
limit_price = max(
    current_price * (1 + entry_price_offset_percent),
    recent_high,  # 最近N根K线的最高点
    resistance_level  # 阻力位
)
```

**配置参数**：
- `entry_price_offset_percent = 0.001` (0.1%)
- `entry_use_support_resistance = true` (使用支撑/阻力位)
- `entry_support_resistance_lookback = 5` (回看5根K线)

### 2.2 监控机制

#### 监控条件
1. **价格远离监控**：
   - 做多：当前价格 > 限价单价格 * (1 + price_away_threshold)
   - 做空：当前价格 < 限价单价格 * (1 - price_away_threshold)
   - 触发：取消限价单，转为市价单

2. **超时监控**：
   - 限价单挂单时间 > limit_order_timeout
   - 触发：取消限价单，转为市价单

3. **价格快速变化监控**：
   - 短时间内价格变化 > rapid_price_change_threshold
   - 触发：取消限价单，转为市价单

**配置参数**：
```toml
[trading.limit_order]
# 开仓限价单配置
entry_limit_order_enabled = true  # 启用开仓限价单
entry_price_offset_percent = 0.001  # 开仓价格偏移 0.1%
entry_price_offset_max_percent = 0.002  # 最大偏移 0.2%
entry_use_support_resistance = true  # 使用支撑/阻力位
entry_support_resistance_lookback = 5  # 回看K线数

# 监控配置
entry_price_away_threshold = 0.005  # 价格远离阈值 0.5%
entry_limit_order_timeout = 30  # 限价单超时时间（秒）
entry_rapid_price_change_threshold = 0.003  # 快速价格变化阈值 0.3%
entry_rapid_price_change_window = 5  # 快速变化时间窗口（秒）
```

### 2.3 执行流程

```
1. 检测到开仓信号
   ↓
2. 计算限价单价格
   ↓
3. 下达限价单
   ↓
4. 启动监控任务
   ↓
5. 实时监控价格
   ├─ 价格成交 → 完成
   ├─ 价格远离 → 取消限价单，转为市价单
   ├─ 超时 → 取消限价单，转为市价单
   └─ 快速变化 → 取消限价单，转为市价单
```

---

## 三、平仓限价单策略

### 3.1 止盈限价单

#### 价格计算
```python
# 做多止盈
limit_price = entry_price * (1 + take_profit_percent - take_profit_price_offset)

# 做空止盈
limit_price = entry_price * (1 - take_profit_percent + take_profit_price_offset)
```

**配置参数**：
- `take_profit_price_offset = 0.001` (0.1%)
- `take_profit_limit_order_enabled = true`

#### 监控机制
1. **价格远离监控**：
   - 做多：当前价格 < 限价单价格 * (1 - price_away_threshold)
   - 做空：当前价格 > 限价单价格 * (1 + price_away_threshold)
   - 触发：取消限价单，转为市价单

2. **超时监控**：
   - 限价单挂单时间 > limit_order_timeout
   - 触发：取消限价单，转为市价单

### 3.2 止损市价单（推荐）

**原因**：
- 止损需要确保及时性
- 市价单能立即成交
- 避免价格快速下跌时无法成交

**配置参数**：
```toml
[trading.limit_order]
# 止盈限价单配置
take_profit_limit_order_enabled = true  # 启用止盈限价单
take_profit_price_offset = 0.001  # 止盈价格偏移 0.1%
take_profit_price_away_threshold = 0.005  # 止盈价格远离阈值 0.5%
take_profit_limit_order_timeout = 60  # 止盈限价单超时时间（秒）

# 止损配置（始终使用市价单）
stop_loss_use_market_order = true  # 止损使用市价单
```

### 3.3 紧急平仓机制

当价格快速接近止损位时，立即市价平仓：

```python
# 做多紧急平仓
if current_price < stop_loss_price * (1 + emergency_close_threshold):
    # 立即市价平仓
    close_position_market_order()

# 做空紧急平仓
if current_price > stop_loss_price * (1 - emergency_close_threshold):
    # 立即市价平仓
    close_position_market_order()
```

**配置参数**：
- `emergency_close_threshold = 0.002` (0.2%)

---

## 四、实时监控要求

### 4.1 监控频率
- **正常监控**：每1秒检查一次
- **紧急监控**：每0.5秒检查一次（价格接近止损/止盈时）

### 4.2 监控数据源
- 使用WebSocket实时价格流
- 订阅 `ticker` 流获取最新价格

### 4.3 监控任务管理
```python
class LimitOrderMonitor:
    def __init__(self):
        self.active_orders = {}  # 活跃订单
        self.monitor_tasks = {}  # 监控任务
    
    async def start_monitor(self, order_id, order_info):
        """启动监控任务"""
        task = asyncio.create_task(self._monitor_order(order_id, order_info))
        self.monitor_tasks[order_id] = task
    
    async def _monitor_order(self, order_id, order_info):
        """监控订单"""
        while True:
            # 检查订单状态
            order_status = self.get_order_status(order_id)
            
            if order_status == 'FILLED':
                # 订单成交，停止监控
                self.stop_monitor(order_id)
                break
            
            # 检查监控条件
            current_price = self.get_current_price()
            
            if self.should_cancel_order(order_info, current_price):
                # 取消订单，转为市价单
                self.cancel_order(order_id)
                self.place_market_order(order_info)
                break
            
            # 等待下一次检查
            await asyncio.sleep(self.check_interval)
```

---

## 五、配置文件更新

### 5.1 config.toml 新增配置

```toml
[trading]
# Fee rate (0.0002 = 0.02%, 0.0004 = 0.04%)
# Binance futures default fee: 0.02% (maker) / 0.04% (taker)
fee_rate = 0.0002  # 0.02% for limit orders (maker fee)

# Limit order configuration
[trading.limit_order]
# Enable limit orders
enabled = true  # 启用限价单交易

# Entry limit order configuration
entry_limit_order_enabled = true  # 启用开仓限价单
entry_price_offset_percent = 0.001  # 开仓价格偏移 0.1%
entry_price_offset_max_percent = 0.002  # 最大偏移 0.2%
entry_use_support_resistance = true  # 使用支撑/阻力位
entry_support_resistance_lookback = 5  # 回看K线数

# Entry monitoring
entry_price_away_threshold = 0.005  # 价格远离阈值 0.5%
entry_limit_order_timeout = 30  # 限价单超时时间（秒）
entry_rapid_price_change_threshold = 0.003  # 快速价格变化阈值 0.3%
entry_rapid_price_change_window = 5  # 快速变化时间窗口（秒）

# Take profit limit order configuration
take_profit_limit_order_enabled = true  # 启用止盈限价单
take_profit_price_offset = 0.001  # 止盈价格偏移 0.1%
take_profit_price_away_threshold = 0.005  # 止盈价格远离阈值 0.5%
take_profit_limit_order_timeout = 60  # 止盈限价单超时时间（秒）

# Stop loss configuration (always use market order)
stop_loss_use_market_order = true  # 止损使用市价单
emergency_close_threshold = 0.002  # 紧急平仓阈值 0.2%

# Monitoring configuration
monitor_check_interval = 1  # 监控检查间隔（秒）
emergency_check_interval = 0.5  # 紧急监控检查间隔（秒）
```

---

## 六、实现方案

### 6.1 需要修改的文件

1. **src/trading/trading_executor.py**
   - 添加限价单方法：`open_long_position_limit()`, `open_short_position_limit()`
   - 添加止盈限价单方法：`close_long_position_limit()`, `close_short_position_limit()`
   - 添加订单监控类：`LimitOrderMonitor`

2. **src/strategy/fifteen_minute_strategy.py**
   - 修改开仓逻辑，使用限价单
   - 修改止盈逻辑，使用限价单
   - 集成订单监控

3. **config.toml**
   - 添加限价单配置参数

### 6.2 实现步骤

#### 步骤1：创建限价单监控器
```python
# src/trading/limit_order_monitor.py
class LimitOrderMonitor:
    """限价单监控器"""
    
    def __init__(self, trading_executor, config):
        self.trading_executor = trading_executor
        self.config = config
        self.active_orders = {}
        self.monitor_tasks = {}
    
    async def start_monitor(self, order_id, order_info):
        """启动监控任务"""
        task = asyncio.create_task(self._monitor_order(order_id, order_info))
        self.monitor_tasks[order_id] = task
    
    async def _monitor_order(self, order_id, order_info):
        """监控订单"""
        # 实现监控逻辑
        pass
```

#### 步骤2：扩展TradingExecutor
```python
# src/trading/trading_executor.py
class TradingExecutor:
    # ... 现有代码 ...
    
    def open_long_position_limit(self, symbol: str, quantity: float, limit_price: float) -> Optional[Dict]:
        """使用限价单开多仓"""
        order = self.client.futures_create_order(
            symbol=symbol,
            side=SIDE_BUY,
            type=ORDER_TYPE_LIMIT,
            quantity=quantity,
            price=limit_price,
            timeInForce='GTC'  # Good Till Cancel
        )
        return order
    
    def open_short_position_limit(self, symbol: str, quantity: float, limit_price: float) -> Optional[Dict]:
        """使用限价单开空仓"""
        order = self.client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL,
            type=ORDER_TYPE_LIMIT,
            quantity=quantity,
            price=limit_price,
            timeInForce='GTC'
        )
        return order
```

#### 步骤3：修改策略逻辑
```python
# src/strategy/fifteen_minute_strategy.py
class FifteenMinuteStrategy:
    # ... 现有代码 ...
    
    async def _check_and_open_position(self):
        """检查并开仓"""
        # ... 检测信号 ...
        
        if self.config.get_config("trading.limit_order", "entry_limit_order_enabled", default=True):
            # 使用限价单
            limit_price = self._calculate_entry_limit_price(current_price, signal_type)
            result = await self.trading_executor.open_long_position_limit(
                symbol, quantity, limit_price
            )
            
            # 启动监控
            if result:
                await self.limit_order_monitor.start_monitor(
                    result['orderId'],
                    {'type': 'entry', 'side': 'LONG', 'original_quantity': quantity}
                )
        else:
            # 使用市价单
            result = await self.trading_executor.open_long_position(symbol, quantity)
```

---

## 七、实时性要求

### 7.1 开仓实时性
- **当前方案**：K线结束时检查信号
- **限价单方案**：K线结束时检查信号，下达限价单，实时监控

**结论**：开仓不需要改为实时判断，因为：
1. 限价单会等待价格回调/反弹
2. 实时监控会确保及时成交
3. K线结束时的信号已经足够准确

### 7.2 平仓实时性
- **当前方案**：实时监控止损/止盈
- **限价单方案**：
  - 止盈：使用限价单，实时监控
  - 止损：使用市价单，实时监控

**结论**：平仓必须保持实时判断，因为：
1. 止损需要确保及时性
2. 价格快速变化时需要立即反应
3. 限价单监控也需要实时价格数据

---

## 八、优势与风险

### 8.1 优势
1. **降低交易成本**：maker费率0.02% vs taker费率0.04%，节省50%手续费
2. **提高成交质量**：在更优价格成交
3. **减少滑点**：避免市价单的滑点
4. **风险可控**：实时监控，必要时转为市价单

### 8.2 风险
1. **无法成交风险**：价格快速变化时可能无法成交
   - **缓解措施**：实时监控，超时或价格远离时转为市价单

2. **错失机会风险**：等待价格回调时价格继续上涨/下跌
   - **缓解措施**：设置合理的偏移量和超时时间

3. **监控任务复杂度**：需要管理多个监控任务
   - **缓解措施**：使用异步任务管理，确保稳定性

---

## 九、实施建议

### 9.1 分阶段实施
1. **第一阶段**：实现开仓限价单
   - 实现限价单下单
   - 实现基本监控
   - 测试验证

2. **第二阶段**：实现止盈限价单
   - 实现止盈限价单
   - 实现监控机制
   - 测试验证

3. **第三阶段**：优化监控策略
   - 添加价格快速变化检测
   - 优化监控频率
   - 性能优化

### 9.2 测试建议
1. **模拟测试**：在测试网测试限价单功能
2. **小资金测试**：使用小资金在实盘测试
3. **逐步推广**：验证稳定后逐步增加资金

### 9.3 监控指标
1. 限价单成交率
2. 限价单转市价单比例
3. 平均成交价格与目标价格偏差
4. 手续费节省金额

---

## 十、总结

### 10.1 核心要点
1. **开仓**：使用限价单，等待价格回调/反弹，实时监控
2. **止盈**：使用限价单，实时监控
3. **止损**：使用市价单，确保及时性
4. **监控**：实时监控价格变化，必要时转为市价单

### 10.2 实时性要求
- **开仓**：不需要改为实时判断，K线结束时检查信号即可
- **平仓**：必须保持实时判断，确保及时止损/止盈

### 10.3 预期效果
- 手续费降低50%
- 成交价格更优
- 风险可控
- 整体收益提升