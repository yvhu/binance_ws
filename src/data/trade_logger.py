"""
交易数据记录器
记录所有交易数据用于未来优化分析
"""

import json
import csv
import logging
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


class TradeLogger:
    """交易数据记录器"""
    
    def __init__(self, log_dir: str = "./logs/trades"):
        """
        初始化交易记录器
        
        Args:
            log_dir: 日志目录
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        self.trades_dir = self.log_dir / "trades"
        self.signals_dir = self.log_dir / "signals"
        self.indicators_dir = self.log_dir / "indicators"
        self.performance_dir = self.log_dir / "performance"
        
        for dir_path in [self.trades_dir, self.signals_dir, self.indicators_dir, self.performance_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # 当前日期
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        
        # 文件路径
        self.trades_file = self.trades_dir / f"trades_{self.current_date}.csv"
        self.signals_file = self.signals_dir / f"signals_{self.current_date}.csv"
        self.indicators_file = self.indicators_dir / f"indicators_{self.current_date}.csv"
        self.performance_file = self.performance_dir / f"performance_{self.current_date}.json"
        
        # 初始化CSV文件
        self._init_csv_files()
        
        # 性能统计
        self.performance_stats = {
            "date": self.current_date,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
            "profit_factor": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "long_win_rate": 0.0,
            "short_win_rate": 0.0,
            "avg_holding_time": 0.0,
            "trades_by_hour": {},
            "trades_by_symbol": {}
        }
        
    
    def _init_csv_files(self):
        """初始化CSV文件并写入表头"""
        # 交易记录表头
        trades_headers = [
            "timestamp", "symbol", "side", "entry_price", "exit_price",
            "quantity", "pnl", "pnl_percent", "holding_time_minutes",
            "entry_time", "exit_time", "close_reason",
            "signal_strength", "stop_loss_price", "take_profit_percent",
            "volume_ratio", "body_ratio", "range_ratio",
            "rsi", "macd", "adx", "market_type", "trend_strength",
            "position_ratio", "leverage"
        ]
        
        # 信号记录表头
        signals_headers = [
            "timestamp", "symbol", "direction", "signal_strength",
            "volume_valid", "range_valid", "body_valid",
            "trend_valid", "rsi_valid",
            "volume_ratio", "body_ratio", "range_ratio",
            "rsi", "macd", "adx", "market_type", "trend_strength"
        ]
        
        # 指标记录表头
        indicators_headers = [
            "timestamp", "symbol", "close", "high", "low", "volume",
            "ma20", "ma50", "rsi", "macd", "macd_signal", "macd_hist",
            "adx", "atr", "bb_upper", "bb_middle", "bb_lower",
            "market_type", "trend_direction", "trend_strength", "volatility"
        ]
        
        # 写入表头（如果文件不存在）
        for file_path, headers in [
            (self.trades_file, trades_headers),
            (self.signals_file, signals_headers),
            (self.indicators_file, indicators_headers)
        ]:
            if not file_path.exists():
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
    
    def log_trade(self, trade_data: Dict):
        """
        记录交易数据
        
        Args:
            trade_data: 交易数据字典
        """
        try:
            # 检查日期是否变化
            current_date = datetime.now().strftime("%Y-%m-%d")
            if current_date != self.current_date:
                self._rotate_logs(current_date)
            
            # 准备数据
            row = [
                trade_data.get("timestamp", datetime.now().isoformat()),
                trade_data.get("symbol", ""),
                trade_data.get("side", ""),
                trade_data.get("entry_price", 0),
                trade_data.get("exit_price", 0),
                trade_data.get("quantity", 0),
                trade_data.get("pnl", 0),
                trade_data.get("pnl_percent", 0),
                trade_data.get("holding_time_minutes", 0),
                trade_data.get("entry_time", ""),
                trade_data.get("exit_time", ""),
                trade_data.get("close_reason", ""),
                trade_data.get("signal_strength", ""),
                trade_data.get("stop_loss_price", 0),
                trade_data.get("take_profit_percent", 0),
                trade_data.get("volume_ratio", 0),
                trade_data.get("body_ratio", 0),
                trade_data.get("range_ratio", 0),
                trade_data.get("rsi", 0),
                trade_data.get("macd", 0),
                trade_data.get("adx", 0),
                trade_data.get("market_type", ""),
                trade_data.get("trend_strength", ""),
                trade_data.get("position_ratio", 0),
                trade_data.get("leverage", 0)
            ]
            
            # 写入CSV
            with open(self.trades_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            # 更新性能统计
            self._update_performance_stats(trade_data)
            
            
        except Exception as e:
            logger.error(f"Error logging trade: {e}")
    
    def log_signal(self, signal_data: Dict):
        """
        记录信号数据
        
        Args:
            signal_data: 信号数据字典
        """
        try:
            # 检查日期是否变化
            current_date = datetime.now().strftime("%Y-%m-%d")
            if current_date != self.current_date:
                self._rotate_logs(current_date)
            
            # 准备数据
            row = [
                signal_data.get("timestamp", datetime.now().isoformat()),
                signal_data.get("symbol", ""),
                signal_data.get("direction", ""),
                signal_data.get("signal_strength", ""),
                signal_data.get("volume_valid", False),
                signal_data.get("range_valid", False),
                signal_data.get("body_valid", False),
                signal_data.get("trend_valid", False),
                signal_data.get("rsi_valid", False),
                signal_data.get("volume_ratio", 0),
                signal_data.get("body_ratio", 0),
                signal_data.get("range_ratio", 0),
                signal_data.get("rsi", 0),
                signal_data.get("macd", 0),
                signal_data.get("adx", 0),
                signal_data.get("market_type", ""),
                signal_data.get("trend_strength", "")
            ]
            
            # 写入CSV
            with open(self.signals_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            logger.debug(f"Signal logged: {signal_data.get('symbol')} {signal_data.get('direction')}")
            
        except Exception as e:
            logger.error(f"Error logging signal: {e}")
    
    def log_indicators(self, indicator_data: Dict):
        """
        记录指标数据
        
        Args:
            indicator_data: 指标数据字典
        """
        try:
            # 检查日期是否变化
            current_date = datetime.now().strftime("%Y-%m-%d")
            if current_date != self.current_date:
                self._rotate_logs(current_date)
            
            # 准备数据
            row = [
                indicator_data.get("timestamp", datetime.now().isoformat()),
                indicator_data.get("symbol", ""),
                indicator_data.get("close", 0),
                indicator_data.get("high", 0),
                indicator_data.get("low", 0),
                indicator_data.get("volume", 0),
                indicator_data.get("ma20", 0),
                indicator_data.get("ma50", 0),
                indicator_data.get("rsi", 0),
                indicator_data.get("macd", 0),
                indicator_data.get("macd_signal", 0),
                indicator_data.get("macd_hist", 0),
                indicator_data.get("adx", 0),
                indicator_data.get("atr", 0),
                indicator_data.get("bb_upper", 0),
                indicator_data.get("bb_middle", 0),
                indicator_data.get("bb_lower", 0),
                indicator_data.get("market_type", ""),
                indicator_data.get("trend_direction", ""),
                indicator_data.get("trend_strength", ""),
                indicator_data.get("volatility", 0)
            ]
            
            # 写入CSV
            with open(self.indicators_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
        except Exception as e:
            logger.error(f"Error logging indicators: {e}")
    
    def _update_performance_stats(self, trade_data: Dict):
        """更新性能统计"""
        self.performance_stats["total_trades"] += 1
        
        pnl = trade_data.get("pnl", 0)
        side = trade_data.get("side", "")
        symbol = trade_data.get("symbol", "")
        entry_time = trade_data.get("entry_time", "")
        
        # 更新盈亏统计
        if pnl > 0:
            self.performance_stats["winning_trades"] += 1
            self.performance_stats["max_win"] = max(self.performance_stats["max_win"], pnl)
        elif pnl < 0:
            self.performance_stats["losing_trades"] += 1
            self.performance_stats["max_loss"] = min(self.performance_stats["max_loss"], pnl)
        
        self.performance_stats["total_pnl"] += pnl
        
        # 更新多空统计
        if side == "LONG":
            self.performance_stats["long_trades"] += 1
        elif side == "SHORT":
            self.performance_stats["short_trades"] += 1
        
        # 更新按小时统计
        if entry_time:
            try:
                hour = datetime.fromisoformat(entry_time).hour
                self.performance_stats["trades_by_hour"][hour] = \
                    self.performance_stats["trades_by_hour"].get(hour, 0) + 1
            except:
                pass
        
        # 更新按交易对统计
        self.performance_stats["trades_by_symbol"][symbol] = \
            self.performance_stats["trades_by_symbol"].get(symbol, 0) + 1
        
        # 计算衍生指标
        total = self.performance_stats["total_trades"]
        if total > 0:
            self.performance_stats["win_rate"] = \
                self.performance_stats["winning_trades"] / total
            
            if self.performance_stats["winning_trades"] > 0:
                self.performance_stats["avg_win"] = \
                    self.performance_stats["total_pnl"] / self.performance_stats["winning_trades"]
            
            if self.performance_stats["losing_trades"] > 0:
                self.performance_stats["avg_loss"] = \
                    self.performance_stats["total_pnl"] / self.performance_stats["losing_trades"]
            
            if self.performance_stats["long_trades"] > 0:
                self.performance_stats["long_win_rate"] = \
                    self.performance_stats["winning_trades"] / total  # 简化计算
            
            if self.performance_stats["short_trades"] > 0:
                self.performance_stats["short_win_rate"] = \
                    self.performance_stats["winning_trades"] / total  # 简化计算
            
            # 计算盈亏比
            if self.performance_stats["avg_loss"] != 0:
                self.performance_stats["profit_factor"] = \
                    abs(self.performance_stats["avg_win"] / self.performance_stats["avg_loss"])
        
        # 保存性能统计
        self._save_performance_stats()
    
    def _save_performance_stats(self):
        """保存性能统计到JSON文件"""
        try:
            with open(self.performance_file, 'w', encoding='utf-8') as f:
                json.dump(self.performance_stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving performance stats: {e}")
    
    def _rotate_logs(self, new_date: str):
        """日志轮转"""
        self.current_date = new_date
        
        # 更新文件路径
        self.trades_file = self.trades_dir / f"trades_{self.current_date}.csv"
        self.signals_file = self.signals_dir / f"signals_{self.current_date}.csv"
        self.indicators_file = self.indicators_dir / f"indicators_{self.current_date}.csv"
        self.performance_file = self.performance_dir / f"performance_{self.current_date}.json"
        
        # 重置性能统计
        self.performance_stats = {
            "date": self.current_date,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_win": 0.0,
            "max_loss": 0.0,
            "profit_factor": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "long_win_rate": 0.0,
            "short_win_rate": 0.0,
            "avg_holding_time": 0.0,
            "trades_by_hour": {},
            "trades_by_symbol": {}
        }
        
        # 初始化新文件
        self._init_csv_files()
    
    def get_trades_dataframe(self, days: int = 7) -> pd.DataFrame:
        """
        获取交易数据DataFrame
        
        Args:
            days: 获取最近几天的数据
            
        Returns:
            交易数据DataFrame
        """
        try:
            dfs = []
            for i in range(days):
                date = (datetime.now() - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
                file_path = self.trades_dir / f"trades_{date}.csv"
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    dfs.append(df)
            
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error reading trades dataframe: {e}")
            return pd.DataFrame()
    
    def get_signals_dataframe(self, days: int = 7) -> pd.DataFrame:
        """
        获取信号数据DataFrame
        
        Args:
            days: 获取最近几天的数据
            
        Returns:
            信号数据DataFrame
        """
        try:
            dfs = []
            for i in range(days):
                date = (datetime.now() - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
                file_path = self.signals_dir / f"signals_{date}.csv"
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    dfs.append(df)
            
            if dfs:
                return pd.concat(dfs, ignore_index=True)
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error reading signals dataframe: {e}")
            return pd.DataFrame()
    
    def get_performance_summary(self) -> Dict:
        """
        获取性能摘要
        
        Returns:
            性能摘要字典
        """
        return self.performance_stats.copy()