# HMA Breakout 策略使用指南

## 策略概述

HMA Breakout 策略基于 Hull Moving Average (HMA) 指标，通过三个不同周期的 HMA 交叉来生成交易信号。

### 策略逻辑

- **多头信号（绿色）**：HMA3 < HMA2 且 HMA3 < HMA1 且 HMA1 > HMA2
- **空头信号（红色）**：HMA3 > HMA2 且 HMA3 > HMA1 且 HMA2 > HMA1
- **平仓信号（灰色）**：不满足多头或空头条件

### 交易规则

1. **开仓**：收到多头或空头信号时开仓，同时在币安设置 -40% ROI 止损单
2. **平仓**：收到平仓信号时平仓（会自动取消止损单）
3. **持仓管理**：只要颜色不变，保持当前仓位
4. **止损**：开仓时在币安设置止损单，ROI 达到 -40% 时自动触发
5. **杠杆**：10倍杠杆，全仓交易
6. **信号确认**：启用信号确认后，信号反转需要经过多次确认才会执行交易，避免市场噪音

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
# Binance API 配置
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Telegram 配置
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

```

### 3. 配置策略参数

编辑 `config.toml` 文件：

```toml
# HMA Breakout 策略配置
[hma_strategy]
# HMA 参数
hma1 = 10
hma2 = 20
hma3 = 100

# K 线周期
kline_interval = "5m"  # 5分钟K线

# 交易配置
[trading]
# 杠杆倍数
leverage = 10
# 交易模式：'cross' 为全仓，'isolated' 为逐仓
margin_type = "cross"
# 止损配置
stop_loss_roi = -0.40  # 投资回报率 -40% 止损
# 条件单类型：'CONDITIONAL' 为条件单
algo_type = "CONDITIONAL"

# 信号确认配置
[signal_confirmation]
# 是否启用信号确认
enabled = true
# 确认时间点（秒），例如 [30, 60] 表示在30秒和60秒时确认
confirmation_times = [30, 60]
# 确认次数要求，例如 2 表示需要在所有确认时间点都确认
required_confirmations = 2
```

### 4. 运行策略

```bash
# 运行 HMA Breakout 策略
python main_hma.py
```

## 完整流程

### 初始化阶段

1. **加载配置**：从 `config.toml` 和 `.env` 加载配置
2. **初始化组件**：
   - K 线管理器
   - HMA 指标计算器
   - 策略信号生成器
   - 仓位管理器
   - 交易执行器
   - Telegram 通知客户端
3. **设置杠杆和保证金模式**：设置 10 倍杠杆和全仓模式
4. **获取账户信息**：获取当前账户余额
5. **检查现有持仓**：同步交易所的持仓信息
6. **加载历史数据**：从 Binance REST API 获取 200 根历史 K 线
7. **发送启动通知**：通过 Telegram 发送启动消息

### 运行阶段

1. **WebSocket 连接**：
   - 连接到 Binance WebSocket，订阅 K 线数据流
   - 连接到用户数据流，监听订单更新
2. **实时数据处理**：
   - 接收实时 K 线更新
   - 更新当前 K 线数据
3. **K 线关闭时处理**：
   - 将 K 线加入历史数据
   - 计算 HMA 指标
   - 生成交易信号
   - 处理交易逻辑
4. **订单更新处理**：
   - 监听止损单成交
   - 止损触发时自动平仓并发送通知

### 信号处理逻辑

#### 信号生成规则

- **GREEN 信号**：仅在颜色从其他状态变为 GREEN 时生成（颜色反转）
- **RED 信号**：仅在颜色从其他状态变为 RED 时生成（颜色反转）
- **GRAY 信号**：当颜色为 GRAY 时始终生成（无论是否反转）

#### 无持仓时

```
等待信号 → 收到 GREEN 信号（颜色反转）→ 开多仓 → 设置止损 → 发送通知
等待信号 → 收到 RED 信号（颜色反转）→ 开空仓 → 设置止损 → 发送通知
等待信号 → 收到 GRAY 信号 → 不开仓，保持空仓
```

#### 有持仓时

```
收到 GREEN 信号（颜色反转）→ 检查持仓类型 → 空仓则平空仓开多仓 → 多仓则保持
收到 RED 信号（颜色反转）→ 检查持仓类型 → 多仓则平多仓开空仓 → 空仓则保持
收到 GRAY 信号 → 平仓 → 发送通知
```

#### 重要规则

- **开仓条件**：只有在颜色变为 GREEN 或 RED 时才能开仓（颜色反转）
- **持仓保持**：颜色保持 GREEN 或 RED 时，保持当前持仓，不开新仓
- **平仓条件**：
  - 收到 GRAY 信号时平仓
  - 信号反转时先平旧仓再开新仓（如：空仓时收到 GREEN 信号，先平空仓再开多仓）

#### 止损

止损在开仓时自动在币安设置，通过用户数据流监听止损单成交：

```
开仓 → 在币安设置 -40% ROI 止损单 → 用户数据流监听订单更新 → 止损单成交 → 自动平仓 → 发送通知
```

平仓时会自动取消止损单。

## 配置说明

### HMA 策略参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| hma1 | 短期 HMA 周期 | 10 |
| hma2 | 中期 HMA 周期 | 20 |
| hma3 | 长期 HMA 周期 | 100 |

### 交易参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| leverage | 杠杆倍数 | 10 |
| margin_type | 保证金模式 | cross |
| stop_loss_roi | 止损 ROI | -0.40 |
| algo_type | 条件单类型 | CONDITIONAL |

### 信号确认参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| enabled | 是否启用信号确认 | true |
| confirmation_times | 确认时间点（秒） | [30, 60] |
| required_confirmations | 需要的确认次数 | 2 |

### 数据管理参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| max_klines | 最大保留 K 线数 | 200 |
| init_klines | 初始化获取的 K 线数 | 200 |

## Telegram 通知

### 启动通知

```
🚀 HMA Breakout 机器人已启动

交易对: BTCUSDC
K线周期: 5m
杠杆: 10倍
策略: HMA Breakout
账户余额: 1000.00 USDT
止损: -40%
```

### 开仓通知

```
🟢 开仓通知

交易对: BTCUSDC
方向: 做多
入场价格: 50000.00
数量: 0.2000
杠杆: 10x
止损价格: 48000.00 (-40%)
```

### 平仓通知

#### 正常平仓（信号变化）

```
🟢 平仓通知

交易对: BTCUSDC
方向: LONG
入场价格: 50000.00
平仓价格: 51000.00
盈亏: 2.00%
盈亏金额: 20.00 USDT
原因: 平仓信号
```

#### 止损平仓

```
🔴 平仓通知

交易对: BTCUSDC
方向: LONG
入场价格: 50000.00
平仓价格: 48000.00
盈亏: -4.00%
盈亏金额: -40.00 USDT
原因: 止损触发
```

## 止损功能详解

### 止损机制

系统使用币安条件单（Conditional Order）实现自动止损，通过 `algoOrder.place` API 创建止损单：

1. **开仓时自动设置止损**：
   - 根据入场价格和-40% ROI计算止损价格
   - 创建STOP_MARKET条件单，设置`closePosition=True`
   - 条件单ID（algoId）被保存到仓位管理器中
   - 使用AlgoOrderManager管理所有活跃的条件单

2. **市价单成交价格处理**：
   - 市价单返回时`avgPrice`为0.0（订单尚未成交）
   - 系统自动轮询等待订单成交（最多10秒）
   - 获取实际成交价格后计算止损价格
   - 确保止损价格基于真实入场价格

3. **止损触发**：
   - 当价格达到止损价时，条件单自动触发
   - 系统通过用户数据流监听订单更新
   - 检测到止损单成交后自动平仓
   - 发送止损平仓通知

4. **平仓时自动清理**：
   - 手动平仓时自动撤销止损条件单
   - 从AlgoOrderManager中移除对应的条件单
   - 避免订单冲突和资源浪费

5. **系统启动时处理现有持仓**：
   - 检测现有持仓时自动设置止损单
   - 检查是否已存在活跃的止损单
   - 避免重复创建止损单

6. **避免重复止损单**：
   - 创建止损单前检查是否已存在
   - 通过`has_active_stop_loss_order()`方法检查
   - 确保每个持仓只有一个止损单

### 止损价格计算

```
ROI = (价格变化 / 入场价格) × 杠杆
价格变化 = ROI × 入场价格 / 杠杆
止损价格 = 入场价格 ± 价格变化

多头止损：止损价格 = 入场价格 - 价格变化
空头止损：止损价格 = 入场价格 + 价格变化
```

示例：
- 入场价格：50000 USDT
- 杠杆：10倍
- 止损ROI：-40%
- 价格变化 = -0.40 × 50000 / 10 = -200 USDT
- 多头止损价格 = 50000 - 200 = 49800 USDT

### 条件单API说明

系统使用币安WebSocket条件单API进行止损管理：

#### 创建条件单（algoOrder.place）

```json
{
  "id": "unique-request-id",
  "method": "algoOrder.place",
  "params": {
    "algoType": "CONDITIONAL",
    "symbol": "BTCUSDT",
    "side": "SELL",
    "positionSide": "LONG",
    "type": "STOP_MARKET",
    "stopPrice": "49800.00",
    "closePosition": "true",
    "timeInForce": "GTC",
    "workingType": "CONTRACT_PRICE",
    "timestamp": 1702555533821,
    "signature": "..."
  }
}
```

**关键参数说明**：
- `algoType`: 固定为"CONDITIONAL"
- `type`: 止损单类型，使用"STOP_MARKET"
- `stopPrice`: 触发价格（止损价格）
- `closePosition`: "true"表示触发后全部平仓
- `workingType`: 触发类型，"CONTRACT_PRICE"为合约最新价

#### 撤销条件单（algoOrder.cancel）

```json
{
  "id": "unique-cancel-id",
  "method": "algoOrder.cancel",
  "params": {
    "algoId": 3000000000003505,
    "timestamp": 1703439070722,
    "signature": "..."
  }
}
```

**重要说明**：
- 条件单使用`algoId`而非`orderId`
- `algoId`与`orderId`是不同的标识符
- 撤销时必须使用`algoId`

### 止损单管理

系统提供完整的止损单管理功能：

```python
# 查看活跃的止损单
active_orders = executor.get_active_stop_loss_orders(symbol)

# 检查是否已有止损单
has_stop_loss = executor.has_active_stop_loss_order(symbol, position_side)

# 撤销指定止损单
executor.cancel_stop_loss_order(symbol, algo_id)

# 撤销所有止损单
executor.cancel_all_stop_loss_orders(symbol)

# 为现有持仓设置止损
executor.set_stop_loss_for_existing_position(position)
```

### AlgoOrderManager

系统使用AlgoOrderManager类管理所有活跃的条件单：

```python
class AlgoOrderManager:
    def __init__(self):
        self.active_orders = {}  # {symbol: {algo_id: order_info}}
    
    def add_order(self, symbol, algo_id, order_info):
        """添加条件单"""
    
    def remove_order(self, symbol, algo_id):
        """移除条件单"""
    
    def get_orders(self, symbol):
        """获取指定交易对的所有条件单"""
    
    def has_order(self, symbol, algo_id):
        """检查条件单是否存在"""
```

**管理规则**：
- 每个交易对维护独立的条件单列表
- 条件单按algo_id索引
- 平仓时自动清理对应的条件单
- 系统重启时重新同步条件单状态

## 信号确认功能详解

### 信号确认机制

为了避免市场噪音导致的频繁交易，系统引入了信号确认机制：

1. **信号反转检测**：
   - K线关闭时检测到颜色反转
   - 创建待确认信号
   - 不立即执行交易

2. **信号确认过程**：
   - 在配置的时间点（如30秒、60秒）检查信号
   - 重新计算当前颜色
   - 如果颜色保持一致，添加确认
   - 如果颜色发生变化，取消信号

3. **信号执行**：
   - 达到确认次数要求后执行交易
   - 确保信号稳定可靠

### 信号确认流程

```
0秒: 检测到信号反转 (GRAY -> GREEN)
     ↓
     创建待确认信号，等待确认
     ↓
30秒: 检查确认
     ↓
     颜色仍然是GREEN → 确认1/2
     颜色变为RED → 取消信号
     ↓
60秒: 检查确认
     ↓
     颜色仍然是GREEN → 确认2/2 → 执行交易
     颜色变为RED → 取消信号
```

### 配置建议

| 策略类型 | confirmation_times | required_confirmations | 特点 |
|---------|-------------------|----------------------|------|
| 保守策略 | [30, 60, 90] | 3 | 需要多次确认，避免假信号 |
| 平衡策略 | [30, 60] | 2 | 平衡速度和准确性（默认） |
| 激进策略 | [30] | 1 | 快速响应，但可能受噪音影响 |
| 禁用确认 | - | - | 立即执行，无延迟 |

### 信号确认配置示例

```toml
# 平衡策略（默认）
[signal_confirmation]
enabled = true
confirmation_times = [30, 60]
required_confirmations = 2

# 保守策略
[signal_confirmation]
enabled = true
confirmation_times = [30, 60, 90]
required_confirmations = 3

# 激进策略
[signal_confirmation]
enabled = true
confirmation_times = [30]
required_confirmations = 1

# 禁用确认
[signal_confirmation]
enabled = false
```

### 信号确认的优势

1. **避免市场噪音**：过滤短期价格波动导致的假信号
2. **提高交易质量**：确保信号稳定可靠后再执行
3. **减少交易频率**：避免频繁开平仓
4. **降低交易成本**：减少手续费和滑点
5. **提高胜率**：通过确认机制提高交易成功率

## 风险提示

1. **高风险策略**：10倍杠杆全仓交易风险极高
2. **止损设置**：-40% 止损意味着可能损失 40% 的本金
3. **市场风险**：加密货币市场波动剧烈
4. **技术风险**：网络中断、API 故障等可能导致交易失败
5. **策略风险**：历史表现不代表未来收益

## 常见问题

### Q: 如何调整止损比例？

A: 修改 `config.toml` 中的 `stop_loss_roi`：

```toml
[trading]
stop_loss_roi = -0.30  # 改为 -30%
```

### Q: 如何查看当前持仓？

A: 程序启动时会自动同步交易所的持仓信息，也可以通过 Telegram 通知查看。

### Q: 如何调整信号确认参数？

A: 修改 `config.toml` 中的 `signal_confirmation` 配置：

```toml
[signal_confirmation]
enabled = true
confirmation_times = [30, 60]  # 在30秒和60秒时确认
required_confirmations = 2  # 需要两次确认
```

### Q: 如何禁用信号确认？

A: 将 `enabled` 设置为 `false`：

```toml
[signal_confirmation]
enabled = false
```

### Q: 信号确认会延迟交易吗？

A: 是的，信号确认会延迟交易。默认配置下，信号反转后需要等待60秒（两次确认）才会执行交易。这是为了避免市场噪音，提高交易质量。

### Q: 止损单会自动撤销吗？

A: 是的，平仓时会自动撤销止损条件单。系统会自动管理止损单的生命周期，避免订单冲突。

### Q: 如何查看活跃的止损单？

A: 可以通过日志查看，或者使用交易执行器的方法：

```python
active_orders = executor.get_active_stop_loss_orders(symbol)
```

### Q: 条件单和普通订单有什么区别？

A: 条件单（Conditional Order）和普通订单的主要区别：

| 特性 | 普通订单 | 条件单 |
|------|---------|--------|
| API | order.place | algoOrder.place |
| 订单ID | orderId | algoId |
| 触发方式 | 立即执行 | 价格达到触发价后执行 |
| 用途 | 开仓、平仓 | 止损、止盈 |
| 返回字段 | orderId | algoId |

### Q: 为什么市价单的avgPrice是0？

A: 市价单返回时订单可能尚未成交，因此`avgPrice`为0.0。系统会自动轮询等待订单成交（最多10秒），获取实际成交价格后再计算止损价格。

### Q: 系统重启后如何处理现有持仓的止损？

A: 系统启动时会自动检测现有持仓，并为每个持仓设置止损单。在设置前会检查是否已存在活跃的止损单，避免重复创建。

### Q: 如何避免重复创建止损单？

A: 系统在创建止损单前会调用`has_active_stop_loss_order()`方法检查是否已存在止损单。如果已存在，则跳过创建，避免重复。

### Q: 条件单触发后如何通知？

A: 条件单触发后，系统通过用户数据流监听订单更新。检测到止损单成交后，会自动平仓并发送Telegram通知。

## 技术支持

如有问题，请检查：
1. 日志文件：`logs/app.log`
2. Telegram 通知消息
3. Binance API 密钥是否正确
4. 网络连接是否正常

## 免责声明

本策略仅供学习和研究使用，不构成投资建议。使用本策略进行交易的所有风险由使用者自行承担。作者不对任何损失负责。