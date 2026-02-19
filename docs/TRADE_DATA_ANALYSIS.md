# 交易数据记录与分析系统

## 概述

本系统实现了完整的交易数据记录和分析功能，用于记录所有交易数据、信号数据和指标数据，并提供数据分析工具生成优化建议。

## 系统架构

### 1. 数据记录模块 (`src/data/trade_logger.py`)

**TradeLogger** 类负责记录以下数据：

#### 交易数据 (trades/)
每笔交易的完整信息：
- 交易ID、时间戳、方向（做多/做空）
- 入场价格、入场时间、入场原因
- 出场价格、出场时间、出场原因
- 盈亏金额、盈亏百分比
- 持仓时间（分钟）
- 信号强度（STRONG/MEDIUM/WEAK）
- 市场类型（TRENDING/RANGING）
- 技术指标值（RSI、ADX、MACD、ATR等）
- 成交量比例、实体比例、影线比例
- 多周期分析结果
- 情绪指标、ML预测结果

#### 信号数据 (signals/)
所有检测到的信号（包括有效和无效）：
- 信号ID、时间戳、方向
- 信号类型、信号强度
- 是否有效、无效原因
- 所有技术指标值
- 成交量比例、实体比例、影线比例
- 市场类型、多周期分析结果

#### 指标数据 (indicators/)
历史指标数据：
- 时间戳
- 所有技术指标值
- 成交量数据
- 价格数据

#### 性能数据 (performance/)
性能统计：
- 总交易数、胜率
- 总盈亏、平均盈亏
- 最大盈利、最大亏损
- 盈亏比
- 多空统计
- 按信号强度统计
- 按市场类型统计
- 按平仓原因统计

### 2. 数据分析模块 (`src/data/trade_analyzer.py`)

**TradeAnalyzer** 类提供以下分析功能：

#### 性能分析
- 整体性能统计
- 多空分析
- 信号强度分析
- 市场环境分析
- 平仓原因分析

#### 指标分析
- RSI与盈亏关系
- ADX与盈亏关系
- 成交量与盈亏关系
- 实体比例与盈亏关系

#### 优化建议生成
- 胜率分析
- 盈亏比分析
- 多空偏好分析
- 信号强度分析
- 市场环境分析
- 止损策略分析
- 各指标过滤器分析

### 3. 数据分析脚本 (`analyze_trades.py`)

命令行工具，用于分析交易数据并生成报告。

## 使用方法

### 1. 启动交易机器人

交易机器人会自动记录所有交易数据：

```bash
# 使用Docker启动
docker-compose up -d

# 或直接运行
python main.py
```

### 2. 提取日志文件（Docker部署）

如果使用Docker部署，可以使用提取脚本将日志文件从容器中提取到本地：

```bash
# 提取日志文件到本地
python extract_logs.py

# 指定容器名称
python extract_logs.py --container binance-telegram-bot

# 指定本地保存目录
python extract_logs.py --local-dir ./my_logs
```

日志文件会被提取到 `./logs/temp_extract/` 目录，然后可以用于分析。

### 3. 查看日志文件

日志文件保存在 `./logs/trades/` 目录下（或提取后的目录）：

```bash
# 查看交易数据
ls -la ./logs/trades/trades/

# 查看信号数据
ls -la ./logs/trades/signals/

# 查看指标数据
ls -la ./logs/trades/indicators/

# 查看性能数据
ls -la ./logs/trades/performance/
```

### 4. 分析交易数据

运行数据分析脚本：

```bash
# 分析最近30天的数据（使用默认目录）
python analyze_trades.py

# 分析最近7天的数据
python analyze_trades.py --days 7

# 使用提取后的数据目录
python analyze_trades.py --data-dir ./logs/temp_extract/trades

# 指定输出文件
python analyze_trades.py --output ./logs/trades/analysis_report.md
```

**完整流程示例：**

```bash
# 1. 从Docker容器提取日志
python extract_logs.py

# 2. 分析提取的数据
python analyze_trades.py --data-dir ./logs/temp_extract/trades --days 30

# 3. 查看分析报告
cat ./logs/temp_extract/trades/analysis_report.md
```

### 5. 查看分析报告

分析报告会保存在 `./logs/trades/analysis_report.md`，包含：

- 整体性能统计
- 多空分析
- 信号强度分析
- 市场环境分析
- 平仓原因分析
- 优化建议

## Docker部署

### 日志持久化配置

`docker-compose.yml` 已配置日志持久化：

```yaml
volumes:
  - ./config.toml:/app/config.toml:ro
  - ./logs:/app/logs
```

这会将容器内的 `/app/logs` 目录映射到宿主机的 `./logs` 目录。

### 访问日志文件

在宿主机上可以直接访问日志文件：

```bash
# 查看日志目录
ls -la ./logs/

# 查看交易数据
cat ./logs/trades/trades/trades_2026-02-19.csv

# 查看分析报告
cat ./logs/trades/analysis_report.md
```

### 在容器内分析数据

如果需要在容器内分析数据：

```bash
# 进入容器
docker exec -it binance-telegram-bot bash

# 运行分析脚本
python analyze_trades.py

# 退出容器
exit
```

## 数据格式

### 交易数据CSV格式

```csv
trade_id,timestamp,side,entry_price,entry_time,entry_reason,exit_price,exit_time,close_reason,pnl,pnl_percent,holding_time_minutes,signal_strength,market_type,rsi,adx,macd,macd_signal,macd_hist,atr,volume_ratio,body_ratio,shadow_ratio,ema_20,ema_50,ema_200,higher_trend,lower_trend,sentiment_score,sentiment_label,ml_prediction,ml_confidence
```

### 信号数据CSV格式

```csv
signal_id,timestamp,side,signal_type,signal_strength,is_valid,invalid_reason,rsi,adx,macd,macd_signal,macd_hist,atr,volume_ratio,body_ratio,shadow_ratio,ema_20,ema_50,ema_200,higher_trend,lower_trend,market_type,sentiment_score,sentiment_label,ml_prediction,ml_confidence
```

### 指标数据CSV格式

```csv
timestamp,open,high,low,close,volume,rsi,adx,macd,macd_signal,macd_hist,atr,ema_20,ema_50,ema_200
```

## 自主优化流程

### 1. 收集数据

运行交易机器人一段时间（建议至少1-2周），收集足够的交易数据。

### 2. 分析数据

运行分析脚本：

```bash
python analyze_trades.py --days 30
```

### 3. 查看优化建议

分析报告会提供详细的优化建议，包括：

- **CRITICAL**: 严重问题，需要立即解决
- **WARNING**: 警告问题，建议优化
- **INFO**: 信息性建议，可以参考

### 4. 调整参数

根据优化建议调整 `config.toml` 中的参数：

```toml
# 例如：如果RSI在超卖区间胜率最高
[filters]
rsi_long_max = 30  # 只在RSI低于30时做多
rsi_short_min = 70  # 只在RSI高于70时做空

# 例如：如果成交量高时胜率最高
[entry_conditions]
volume_ratio_threshold = 1.5  # 提高成交量阈值
```

### 5. 验证效果

重新运行交易机器人，观察优化效果：

```bash
# 重启机器人
docker-compose restart

# 等待一段时间后再次分析
python analyze_trades.py --days 7
```

### 6. 持续优化

定期分析数据，持续优化策略参数。

## 数据导出

### 导出为DataFrame

```python
from src.data.trade_analyzer import TradeAnalyzer

analyzer = TradeAnalyzer()

# 导出交易数据
trades_df = analyzer.get_trades_dataframe()

# 导出信号数据
signals_df = analyzer.get_signals_dataframe()

# 保存为CSV
trades_df.to_csv('trades_export.csv', index=False)
signals_df.to_csv('signals_export.csv', index=False)
```

### 导出性能统计

```python
# 获取性能统计
performance = analyzer.get_performance_summary()

# 保存为JSON
import json
with open('performance.json', 'w') as f:
    json.dump(performance, f, indent=2)
```

## 注意事项

1. **数据隐私**: 交易数据包含敏感信息，请妥善保管
2. **数据备份**: 定期备份日志文件
3. **磁盘空间**: 日志文件会持续增长，建议定期清理旧数据
4. **数据质量**: 确保数据记录完整，避免数据丢失
5. **分析周期**: 建议至少收集1-2周的数据再进行分析
6. **参数调整**: 每次只调整少量参数，观察效果后再继续调整

## 故障排查

### 日志文件未生成

检查日志目录权限：

```bash
# 确保日志目录存在且有写权限
mkdir -p ./logs/trades/trades
mkdir -p ./logs/trades/signals
mkdir -p ./logs/trades/indicators
mkdir -p ./logs/trades/performance

chmod -R 755 ./logs
```

### Docker容器无法访问日志

检查Docker卷挂载：

```bash
# 查看容器卷挂载
docker inspect binance-telegram-bot | grep -A 10 Mounts

# 确保日志目录正确映射
```

### 分析脚本报错

检查数据文件是否存在：

```bash
# 查看是否有数据文件
ls -la ./logs/trades/trades/

# 如果没有数据，等待交易机器人运行一段时间
```

## 未来扩展

1. **机器学习优化**: 使用历史数据训练模型，自动优化参数
2. **实时监控**: 实时监控交易表现，自动调整策略
3. **回测集成**: 将历史数据用于回测，验证优化效果
4. **可视化**: 添加图表可视化，更直观地展示数据
5. **自动优化**: 实现自动参数优化功能

## 相关文档

- [策略优化总结](STRATEGY_OPTIMIZATION_SUMMARY.md)
- [策略损失分析](STRATEGY_LOSS_ANALYSIS.md)
- [策略流程](STRATEGY_FLOW.md)
- [交易流程](TRADING_FLOW.md)