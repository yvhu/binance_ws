# Binance Futures Telegram Bot

A cryptocurrency futures trading bot that fetches real-time market data from Binance Futures WebSocket and sends notifications via Telegram.

# Binance 合约交易 Telegram 机器人

一个加密货币合约交易机器人，通过Binance合约WebSocket实时获取市场数据，并通过Telegram发送通知。

## Features / 功能特性

- Real-time data fetching via Binance Futures WebSocket / 通过Binance合约WebSocket实时获取数据
- Telegram notifications / Telegram通知功能
- Support for mark price and funding rate monitoring / 支持标记价格和资金费率监控
- Support for liquidation order monitoring / 支持强平订单监控
- Docker deployment support / 支持Docker部署
- Modular and extensible code design / 模块化可扩展的代码设计

## Project Structure / 项目结构

```
binance_ws/
├── src/
│   ├── config/                 # Configuration management / 配置管理
│   ├── binance/                # Binance Futures WebSocket module / Binance合约WebSocket模块
│   ├── telegram/               # Telegram communication module / Telegram通讯模块
│   └── utils/                  # Utility functions / 工具函数
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
- TELEGRAM_BOT_TOKEN: Telegram Bot Token / Telegram Bot令牌
- TELEGRAM_CHAT_ID: Telegram Chat ID / Telegram聊天ID

### Configuration File (config.toml) / 配置文件

Configure futures trading pairs and WebSocket streams in config.toml.
在config.toml中配置合约交易对和WebSocket数据流。

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
- kline_5m: 5分钟K线数据 / 5-minute Kline data
- kline_15m: 15分钟K线数据 / 15-minute Kline data
- kline_1h: 1小时K线数据 / 1-hour Kline data

## Module Descriptions / 模块说明

### Binance Module / Binance模块
- **WebSocket Client**: Real-time market data connection / 实时市场数据连接
- **Data Handler**: Process and manage incoming data / 处理和管理传入数据
- **User Data Client**: Account information and order management / 账户信息和订单管理

### Telegram Module / Telegram模块
- **Telegram Client**: Send notifications to Telegram / 发送通知到Telegram
- **Message Formatter**: Format messages for better readability / 格式化消息以提高可读性

### Config Module / 配置模块
- **Config Manager**: Load and manage configuration / 加载和管理配置

### Utils Module / 工具模块
- **Logger**: Logging functionality / 日志功能
- **Retry Decorator**: Retry mechanism for API calls / API调用重试机制

## License / 许可证

MIT License