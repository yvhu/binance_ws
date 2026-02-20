# HMA Breakout Trading Bot

A cryptocurrency futures trading bot based on Hull Moving Average (HMA) Breakout strategy, with real-time market data from Binance Futures and Telegram notifications.

# HMA Breakout 策略交易机器人

基于 Hull Moving Average (HMA) Breakout 策略的加密货币合约交易机器人，通过Binance合约WebSocket实时获取市场数据，并通过Telegram发送通知。

## Features / 功能特性

- **HMA Breakout Strategy**: Based on three HMA periods (10, 20, 100) for signal generation / 基于三个HMA周期（10, 20, 100）生成交易信号
- **Real-time Data**: Real-time K-line data via Binance Futures WebSocket / 通过Binance合约WebSocket实时获取K线数据
- **Automatic Trading**: Automatic position opening and closing / 自动开仓和平仓
- **Stop Loss**: Automatic -40% ROI stop loss orders / 自动设置-40% ROI止损单
- **Telegram Notifications**: Real-time trading notifications / 实时交易通知
- **Position Management**: Full position tracking and management / 完整的持仓跟踪和管理
- **Docker Support**: Docker deployment support / 支持Docker部署
- **Modular Design**: Clean and extensible code structure / 清晰可扩展的代码结构

## Project Structure / 项目结构

```
binance_ws/
├── src/
│   ├── config/                 # Configuration management / 配置管理
│   ├── binance/                # Binance API and WebSocket / Binance API和WebSocket
│   ├── data/                   # K-line data management / K线数据管理
│   ├── indicators/             # Technical indicators / 技术指标
│   ├── strategy/               # Trading strategy / 交易策略
│   ├── trading/                # Trading execution / 交易执行
│   ├── telegram/               # Telegram notifications / Telegram通知
│   └── utils/                  # Utility functions / 工具函数
├── docs/                       # Documentation / 文档
│   └── HMA_BREAKOUT_GUIDE.md   # Strategy guide / 策略指南
├── main_hma.py                 # Main entry point / 主程序入口
├── config.toml                 # Configuration file / 配置文件
├── .env.example                # Environment variables example / 环境变量示例
├── requirements.txt            # Python dependencies / Python依赖
├── Dockerfile                  # Docker image build file / Docker镜像构建文件
├── docker-compose.yml          # Docker Compose configuration / Docker Compose配置
└── README.md                   # Project documentation / 项目文档
```

## Quick Start / 快速开始

### Prerequisites / 前置要求

- Python 3.11+
- Docker (optional) / Docker（可选）
- Binance Futures API keys / Binance合约API密钥
- Telegram Bot Token and Chat ID / Telegram Bot Token和Chat ID

### Installation / 安装步骤

1. Clone the repository / 克隆仓库
2. Create virtual environment: `python -m venv venv` / 创建虚拟环境
3. Activate virtual environment / 激活虚拟环境
4. Install dependencies: `pip install -r requirements.txt` / 安装依赖
5. Copy `.env.example` to `.env` and configure / 复制`.env.example`为`.env`并配置
6. Run: `python main_hma.py` / 运行程序

For detailed strategy information, see [HMA_BREAKOUT_GUIDE.md](docs/HMA_BREAKOUT_GUIDE.md)

## Docker Deployment / Docker部署

### Using Docker Compose / 使用Docker Compose

```bash
docker-compose up -d
```

### Using Docker Commands / 使用Docker命令

```bash
docker build -t binance-telegram-bot .
docker run -d --name binance-telegram-bot --env-file .env binance-telegram-bot
```

## Configuration / 配置说明

### Environment Variables (.env) / 环境变量

- BINANCE_API_KEY: Binance Futures API key / Binance合约API密钥
- BINANCE_API_SECRET: Binance Futures API secret / Binance合约API密钥
- TELEGRAM_BOT_TOKEN: Telegram Bot Token / Telegram Bot令牌
- TELEGRAM_CHAT_ID: Telegram Chat ID / Telegram聊天ID

### Configuration File (config.toml) / 配置文件

**Binance Configuration / 币安配置:**
- symbols: Trading pairs (e.g., ["BTCUSDC"]) / 交易对
- streams: WebSocket streams (e.g., ["kline_5m"]) / WebSocket数据流

**HMA Strategy Configuration / HMA策略配置:**
- hma1: Short-term HMA period (default: 10) / 短期HMA周期
- hma2: Medium-term HMA period (default: 20) / 中期HMA周期
- hma3: Long-term HMA period (default: 100) / 长期HMA周期
- kline_interval: K-line interval (default: "5m") / K线周期

**Trading Configuration / 交易配置:**
- leverage: Leverage multiplier (default: 10) / 杠杆倍数
- margin_type: Margin type ("cross" or "isolated") / 保证金模式
- stop_loss_roi: Stop loss ROI (default: -0.40) / 止损ROI

**Data Management Configuration / 数据管理配置:**
- max_klines: Maximum K-lines to keep (default: 200) / 最大保留K线数
- init_klines: Initial K-lines to load (default: 200) / 初始化加载K线数

For detailed configuration examples, see [HMA_BREAKOUT_GUIDE.md](docs/HMA_BREAKOUT_GUIDE.md)

## Module Descriptions / 模块说明

### Binance Module / Binance模块
- **WebSocket Client**: Real-time K-line data connection / 实时K线数据连接
- **User Data Client**: Order updates and account monitoring / 订单更新和账户监控

### Data Module / 数据模块
- **Kline Manager**: K-line data storage and management / K线数据存储和管理

### Indicators Module / 指标模块
- **HMA Calculator**: Hull Moving Average calculation / HMA指标计算
- **HMA Indicator**: Multi-period HMA management / 多周期HMA管理

### Strategy Module / 策略模块
- **HMA Breakout Strategy**: Signal generation based on HMA crossover / 基于HMA交叉生成信号

### Trading Module / 交易模块
- **Position Manager**: Position tracking and PnL calculation / 持仓跟踪和盈亏计算
- **Trading Executor**: Order execution and API interaction / 订单执行和API交互

### Telegram Module / Telegram模块
- **Telegram Client**: Send trading notifications / 发送交易通知

### Config Module / 配置模块
- **Config Manager**: Load and manage configuration / 加载和管理配置

### Utils Module / 工具模块
- **Logger**: Logging functionality / 日志功能
- **Retry Decorator**: Retry mechanism for API calls / API调用重试机制

## Strategy Overview / 策略概述

The HMA Breakout strategy uses three Hull Moving Average periods to generate trading signals:

**Signal Conditions / 信号条件:**
- **LONG (Green)**: HMA3 < HMA2 AND HMA3 < HMA1 AND HMA1 > HMA2
- **SHORT (Red)**: HMA3 > HMA2 AND HMA3 > HMA1 AND HMA2 > HMA1
- **CLOSE (Gray)**: Neither LONG nor SHORT conditions met

**Trading Rules / 交易规则:**
- Open position only when color changes (signal reversal) / 仅在颜色变化时开仓
- Maintain position when color remains the same / 颜色不变时保持持仓
- Close position when GRAY signal received / 收到GRAY信号时平仓
- Set -40% ROI stop loss on position opening / 开仓时设置-40% ROI止损
- 10x leverage, cross margin / 10倍杠杆，全仓模式

For complete strategy documentation, see [HMA_BREAKOUT_GUIDE.md](docs/HMA_BREAKOUT_GUIDE.md)

## Risk Warning / 风险提示

⚠️ **High Risk Strategy / 高风险策略**
- 10x leverage trading carries significant risk / 10倍杠杆交易风险极高
- -40% stop loss means potential 40% capital loss / -40%止损意味着可能损失40%本金
- Cryptocurrency markets are highly volatile / 加密货币市场波动剧烈
- Past performance does not guarantee future results / 历史表现不代表未来收益
- Use at your own risk / 使用风险自负

## License / 许可证

MIT License