# Binance Futures Telegram Bot

A cryptocurrency futures trading bot that fetches real-time market data from Binance Futures WebSocket, performs technical analysis using TA-Lib, and sends trading signals via Telegram.

# Binance 合约交易 Telegram 机器人

一个加密货币合约交易机器人，通过Binance合约WebSocket实时获取市场数据，使用TA-Lib进行技术指标分析，并通过Telegram发送交易信号。

## Features / 功能特性

- Real-time data fetching via Binance Futures WebSocket / 通过Binance合约WebSocket实时获取数据
- Technical indicator analysis using TA-Lib / 使用TA-Lib进行技术指标分析
- Telegram notifications for trading signals / Telegram交易信号通知
- Support for mark price and funding rate monitoring / 支持标记价格和资金费率监控
- Support for liquidation order monitoring / 支持强平订单监控
- Docker deployment support / 支持Docker部署
- Modular and extensible code design / 模块化可扩展的代码设计
- 15-minute K-line trading strategy with SAR indicator / 15分钟K线+SAR指标交易策略
- Comprehensive Telegram notifications (Chinese) / 完整的Telegram通知（中文）

## Project Structure / 项目结构

```
binance_ws/
├── src/
│   ├── config/                 # Configuration management / 配置管理
│   ├── binance/                # Binance Futures WebSocket module / Binance合约WebSocket模块
│   ├── telegram/               # Telegram communication module / Telegram通讯模块
│   ├── indicators/             # Technical indicators module / 技术指标模块
│   ├── strategy/               # Trading strategy module / 交易策略模块
│   ├── trading/                # Trading execution module / 交易执行模块
│   └── utils/                  # Utility functions / 工具函数
├── docs/                       # Documentation / 文档
├── main.py                     # Main entry point / 主程序入口
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
6. Run: `python main.py` / 运行程序

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
- BINANCE_WS_URL: Binance Futures WebSocket URL / Binance合约WebSocket地址
- LEVERAGE: Trading leverage (default: 10) / 交易杠杆倍数（默认：10）
- TELEGRAM_BOT_TOKEN: Telegram Bot Token / Telegram Bot令牌
- TELEGRAM_CHAT_ID: Telegram Chat ID / Telegram聊天ID

### Configuration File (config.toml) / 配置文件

Configure futures trading pairs, indicators, and strategy parameters in config.toml.
在config.toml中配置合约交易对、指标和策略参数。

**Current Focus / 当前重点:**
- Trading is currently focused on BTCUSDC only for production use
- 当前实盘交易仅专注于BTCUSDC
- The codebase supports multiple symbols for future expansion
- 代码库支持多币种扩展，只需在配置中添加即可

**To add more symbols / 添加更多币种:**
```toml
symbols = ["BTCUSDC", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
```

Available streams for futures / 合约可用数据流:
- ticker: 24小时价格变动 / 24-hour ticker
- kline_1m, kline_5m, kline_15m: K线数据 / Kline data
- markPrice: 标记价格 / Mark price
- forceOrder: 强平订单 / Liquidation orders

## Technical Indicators / 技术指标

- Moving Averages (MA) / 移动平均线
- Relative Strength Index (RSI) / 相对强弱指标
- MACD / 指数平滑异同移动平均线
- Bollinger Bands / 布林带
- ATR / 平均真实波幅
- Stochastic Oscillator / 随机指标
- SAR / 抛物线转向指标

## Documentation / 文档

- [Project Execution Flow](docs/PROJECT_FLOW.md) - 项目执行流程说明
- [Trading Flow Documentation](docs/TRADING_FLOW.md) - 详细交易流程说明
- [Telegram Notifications](docs/TELEGRAM_NOTIFICATIONS.md) - Telegram通知说明

## License / 许可证

MIT License