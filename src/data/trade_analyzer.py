"""
交易数据分析工具
分析记录的交易数据，提供优化建议
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TradeAnalyzer:
    """交易数据分析器"""
    
    def __init__(self, data_dir: str = "./logs/trades"):
        """
        初始化交易分析器
        
        Args:
            data_dir: 数据目录
        """
        self.data_dir = Path(data_dir)
        self.trades_dir = self.data_dir / "trades"
        self.signals_dir = self.data_dir / "signals"
        self.indicators_dir = self.data_dir / "indicators"
        self.performance_dir = self.data_dir / "performance"
    
    def load_trades(self, days: int = 30) -> pd.DataFrame:
        """
        加载交易数据
        
        Args:
            days: 加载最近几天的数据
            
        Returns:
            交易数据DataFrame
        """
        try:
            dfs = []
            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                file_path = self.trades_dir / f"trades_{date}.csv"
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    dfs.append(df)
            
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['entry_time'] = pd.to_datetime(df['entry_time'])
                df['exit_time'] = pd.to_datetime(df['exit_time'])
                return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return pd.DataFrame()
    
    def load_signals(self, days: int = 30) -> pd.DataFrame:
        """
        加载信号数据
        
        Args:
            days: 加载最近几天的数据
            
        Returns:
            信号数据DataFrame
        """
        try:
            dfs = []
            for i in range(days):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                file_path = self.signals_dir / f"signals_{date}.csv"
                if file_path.exists():
                    df = pd.read_csv(file_path)
                    dfs.append(df)
            
            if dfs:
                df = pd.concat(dfs, ignore_index=True)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading signals: {e}")
            return pd.DataFrame()
    
    def analyze_performance(self, df: pd.DataFrame) -> Dict:
        """
        分析交易性能
        
        Args:
            df: 交易数据DataFrame
            
        Returns:
            性能分析结果
        """
        if df.empty:
            return {}
        
        try:
            # 基本统计
            total_trades = len(df)
            winning_trades = len(df[df['pnl'] > 0])
            losing_trades = len(df[df['pnl'] < 0])
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            total_pnl = df['pnl'].sum()
            avg_pnl = df['pnl'].mean()
            
            avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
            avg_loss = df[df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
            
            max_win = df['pnl'].max()
            max_loss = df['pnl'].min()
            
            # 盈亏比
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            # 多空分析
            long_trades = df[df['side'] == 'LONG']
            short_trades = df[df['side'] == 'SHORT']
            
            long_win_rate = len(long_trades[long_trades['pnl'] > 0]) / len(long_trades) if len(long_trades) > 0 else 0
            short_win_rate = len(short_trades[short_trades['pnl'] > 0]) / len(short_trades) if len(short_trades) > 0 else 0
            
            long_pnl = long_trades['pnl'].sum() if len(long_trades) > 0 else 0
            short_pnl = short_trades['pnl'].sum() if len(short_trades) > 0 else 0
            
            # 持仓时间分析
            avg_holding_time = df['holding_time_minutes'].mean()
            
            # 按信号强度分析
            signal_strength_stats = {}
            for strength in ['STRONG', 'MEDIUM', 'WEAK']:
                strength_trades = df[df['signal_strength'] == strength]
                if len(strength_trades) > 0:
                    signal_strength_stats[strength] = {
                        'count': len(strength_trades),
                        'win_rate': len(strength_trades[strength_trades['pnl'] > 0]) / len(strength_trades),
                        'avg_pnl': strength_trades['pnl'].mean(),
                        'total_pnl': strength_trades['pnl'].sum()
                    }
            
            # 按市场类型分析
            market_type_stats = {}
            for market_type in df['market_type'].unique():
                market_trades = df[df['market_type'] == market_type]
                if len(market_trades) > 0:
                    market_type_stats[market_type] = {
                        'count': len(market_trades),
                        'win_rate': len(market_trades[market_trades['pnl'] > 0]) / len(market_trades),
                        'avg_pnl': market_trades['pnl'].mean(),
                        'total_pnl': market_trades['pnl'].sum()
                    }
            
            # 按平仓原因分析
            close_reason_stats = {}
            for reason in df['close_reason'].unique():
                reason_trades = df[df['close_reason'] == reason]
                if len(reason_trades) > 0:
                    close_reason_stats[reason] = {
                        'count': len(reason_trades),
                        'win_rate': len(reason_trades[reason_trades['pnl'] > 0]) / len(reason_trades),
                        'avg_pnl': reason_trades['pnl'].mean(),
                        'total_pnl': reason_trades['pnl'].sum()
                    }
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'max_win': max_win,
                'max_loss': max_loss,
                'profit_factor': profit_factor,
                'long_win_rate': long_win_rate,
                'short_win_rate': short_win_rate,
                'long_pnl': long_pnl,
                'short_pnl': short_pnl,
                'avg_holding_time': avg_holding_time,
                'signal_strength_stats': signal_strength_stats,
                'market_type_stats': market_type_stats,
                'close_reason_stats': close_reason_stats
            }
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {}
    
    def analyze_indicators(self, df: pd.DataFrame) -> Dict:
        """
        分析指标与盈亏的关系
        
        Args:
            df: 交易数据DataFrame
            
        Returns:
            指标分析结果
        """
        if df.empty:
            return {}
        
        try:
            results = {}
            
            # RSI分析
            if 'rsi' in df.columns:
                rsi_bins = [0, 30, 40, 50, 60, 70, 100]
                rsi_labels = ['超卖', '偏空', '中性偏空', '中性偏多', '偏多', '超买']
                df['rsi_range'] = pd.cut(df['rsi'], bins=rsi_bins, labels=rsi_labels)
                
                rsi_stats = {}
                for label in rsi_labels:
                    rsi_trades = df[df['rsi_range'] == label]
                    if len(rsi_trades) > 0:
                        rsi_stats[label] = {
                            'count': len(rsi_trades),
                            'win_rate': len(rsi_trades[rsi_trades['pnl'] > 0]) / len(rsi_trades),
                            'avg_pnl': rsi_trades['pnl'].mean()
                        }
                results['rsi'] = rsi_stats
            
            # ADX分析
            if 'adx' in df.columns:
                adx_bins = [0, 20, 25, 30, 40, 100]
                adx_labels = ['震荡', '弱趋势', '中等趋势', '强趋势', '极强趋势']
                df['adx_range'] = pd.cut(df['adx'], bins=adx_bins, labels=adx_labels)
                
                adx_stats = {}
                for label in adx_labels:
                    adx_trades = df[df['adx_range'] == label]
                    if len(adx_trades) > 0:
                        adx_stats[label] = {
                            'count': len(adx_trades),
                            'win_rate': len(adx_trades[adx_trades['pnl'] > 0]) / len(adx_trades),
                            'avg_pnl': adx_trades['pnl'].mean()
                        }
                results['adx'] = adx_stats
            
            # 成交量比例分析
            if 'volume_ratio' in df.columns:
                volume_bins = [0, 1.0, 1.2, 1.5, 2.0, 10]
                volume_labels = ['低', '正常', '偏高', '高', '极高']
                df['volume_range'] = pd.cut(df['volume_ratio'], bins=volume_bins, labels=volume_labels)
                
                volume_stats = {}
                for label in volume_labels:
                    volume_trades = df[df['volume_range'] == label]
                    if len(volume_trades) > 0:
                        volume_stats[label] = {
                            'count': len(volume_trades),
                            'win_rate': len(volume_trades[volume_trades['pnl'] > 0]) / len(volume_trades),
                            'avg_pnl': volume_trades['pnl'].mean()
                        }
                results['volume_ratio'] = volume_stats
            
            # 实体比例分析
            if 'body_ratio' in df.columns:
                body_bins = [0, 0.5, 0.6, 0.7, 0.8, 1.0]
                body_labels = ['小', '偏小', '中等', '偏大', '大']
                df['body_range'] = pd.cut(df['body_ratio'], bins=body_bins, labels=body_labels)
                
                body_stats = {}
                for label in body_labels:
                    body_trades = df[df['body_range'] == label]
                    if len(body_trades) > 0:
                        body_stats[label] = {
                            'count': len(body_trades),
                            'win_rate': len(body_trades[body_trades['pnl'] > 0]) / len(body_trades),
                            'avg_pnl': body_trades['pnl'].mean()
                        }
                results['body_ratio'] = body_stats
            
            return results
        except Exception as e:
            logger.error(f"Error analyzing indicators: {e}")
            return {}
    
    def generate_optimization_suggestions(self, df: pd.DataFrame) -> List[Dict]:
        """
        生成优化建议
        
        Args:
            df: 交易数据DataFrame
            
        Returns:
            优化建议列表
        """
        suggestions = []
        
        if df.empty:
            return suggestions
        
        try:
            performance = self.analyze_performance(df)
            indicators = self.analyze_indicators(df)
            
            # 1. 胜率分析
            if performance.get('win_rate', 0) < 0.4:
                suggestions.append({
                    'type': 'CRITICAL',
                    'category': '胜率',
                    'issue': f"胜率过低: {performance.get('win_rate', 0)*100:.1f}%",
                    'suggestion': '建议提高入场条件阈值，减少假信号',
                    'priority': 'HIGH'
                })
            elif performance.get('win_rate', 0) < 0.5:
                suggestions.append({
                    'type': 'WARNING',
                    'category': '胜率',
                    'issue': f"胜率偏低: {performance.get('win_rate', 0)*100:.1f}%",
                    'suggestion': '考虑添加更多过滤器或提高现有过滤器阈值',
                    'priority': 'MEDIUM'
                })
            
            # 2. 盈亏比分析
            if performance.get('profit_factor', 0) < 1.5:
                suggestions.append({
                    'type': 'WARNING',
                    'category': '盈亏比',
                    'issue': f"盈亏比偏低: {performance.get('profit_factor', 0):.2f}",
                    'suggestion': '建议提高止盈目标或优化止损策略',
                    'priority': 'MEDIUM'
                })
            
            # 3. 多空分析
            long_win_rate = performance.get('long_win_rate', 0)
            short_win_rate = performance.get('short_win_rate', 0)
            
            if abs(long_win_rate - short_win_rate) > 0.2:
                better_side = '做多' if long_win_rate > short_win_rate else '做空'
                suggestions.append({
                    'type': 'INFO',
                    'category': '方向偏好',
                    'issue': f"{better_side}胜率明显更高",
                    'suggestion': f"考虑增加{better_side}的仓位比例或减少另一方向的交易",
                    'priority': 'LOW'
                })
            
            # 4. 信号强度分析
            signal_stats = performance.get('signal_strength_stats', {})
            if signal_stats:
                best_strength = max(signal_stats.items(), key=lambda x: x[1]['win_rate'])
                worst_strength = min(signal_stats.items(), key=lambda x: x[1]['win_rate'])
                
                if best_strength[1]['win_rate'] - worst_strength[1]['win_rate'] > 0.2:
                    suggestions.append({
                        'type': 'INFO',
                        'category': '信号强度',
                        'issue': f"{best_strength[0]}信号胜率最高: {best_strength[1]['win_rate']*100:.1f}%",
                        'suggestion': f"考虑只交易{best_strength[0]}信号或提高其他信号的入场条件",
                        'priority': 'LOW'
                    })
            
            # 5. 市场类型分析
            market_stats = performance.get('market_type_stats', {})
            if market_stats:
                best_market = max(market_stats.items(), key=lambda x: x[1]['win_rate'])
                worst_market = min(market_stats.items(), key=lambda x: x[1]['win_rate'])
                
                if best_market[1]['win_rate'] - worst_market[1]['win_rate'] > 0.2:
                    suggestions.append({
                        'type': 'INFO',
                        'category': '市场环境',
                        'issue': f"{best_market[0]}市场胜率最高: {best_market[1]['win_rate']*100:.1f}%",
                        'suggestion': f"考虑只在{best_market[0]}市场交易",
                        'priority': 'LOW'
                    })
            
            # 6. 平仓原因分析
            close_reason_stats = performance.get('close_reason_stats', {})
            if close_reason_stats:
                stop_loss_trades = close_reason_stats.get('止损触发', {})
                if stop_loss_trades and stop_loss_trades.get('count', 0) > 0:
                    stop_loss_win_rate = stop_loss_trades.get('win_rate', 0)
                    if stop_loss_win_rate < 0.3:
                        suggestions.append({
                            'type': 'WARNING',
                            'category': '止损策略',
                            'issue': f"止损胜率过低: {stop_loss_win_rate*100:.1f}%",
                            'suggestion': '建议增加止损距离或优化止损触发条件',
                            'priority': 'MEDIUM'
                        })
            
            # 7. RSI分析
            if 'rsi' in indicators:
                rsi_stats = indicators['rsi']
                best_rsi = max(rsi_stats.items(), key=lambda x: x[1]['win_rate'])
                if best_rsi[1]['win_rate'] > 0.6:
                    suggestions.append({
                        'type': 'INFO',
                        'category': 'RSI过滤器',
                        'issue': f"RSI在{best_rsi[0]}区间胜率最高: {best_rsi[1]['win_rate']*100:.1f}%",
                        'suggestion': f"考虑调整RSI过滤器，只在{best_rsi[0]}区间交易",
                        'priority': 'LOW'
                    })
            
            # 8. ADX分析
            if 'adx' in indicators:
                adx_stats = indicators['adx']
                best_adx = max(adx_stats.items(), key=lambda x: x[1]['win_rate'])
                if best_adx[1]['win_rate'] > 0.6:
                    suggestions.append({
                        'type': 'INFO',
                        'category': 'ADX过滤器',
                        'issue': f"ADX在{best_adx[0]}区间胜率最高: {best_adx[1]['win_rate']*100:.1f}%",
                        'suggestion': f"考虑调整ADX过滤器，只在{best_adx[0]}市场交易",
                        'priority': 'LOW'
                    })
            
            # 9. 成交量分析
            if 'volume_ratio' in indicators:
                volume_stats = indicators['volume_ratio']
                best_volume = max(volume_stats.items(), key=lambda x: x[1]['win_rate'])
                if best_volume[1]['win_rate'] > 0.6:
                    suggestions.append({
                        'type': 'INFO',
                        'category': '成交量过滤器',
                        'issue': f"成交量在{best_volume[0]}区间胜率最高: {best_volume[1]['win_rate']*100:.1f}%",
                        'suggestion': f"考虑调整成交量阈值，只在{best_volume[0]}成交量时交易",
                        'priority': 'LOW'
                    })
            
            return suggestions
        except Exception as e:
            logger.error(f"Error generating optimization suggestions: {e}")
            return []
    
    def generate_report(self, days: int = 30) -> str:
        """
        生成分析报告
        
        Args:
            days: 分析最近几天的数据
            
        Returns:
            分析报告文本
        """
        df = self.load_trades(days)
        
        if df.empty:
            return "没有可用的交易数据"
        
        try:
            performance = self.analyze_performance(df)
            indicators = self.analyze_indicators(df)
            suggestions = self.generate_optimization_suggestions(df)
            
            report = f"""
# 交易策略分析报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
数据范围: 最近 {days} 天
交易数量: {performance.get('total_trades', 0)}

## 1. 整体性能

- 总盈亏: ${performance.get('total_pnl', 0):.2f}
- 胜率: {performance.get('win_rate', 0)*100:.1f}%
- 平均盈亏: ${performance.get('avg_pnl', 0):.2f}
- 平均盈利: ${performance.get('avg_win', 0):.2f}
- 平均亏损: ${performance.get('avg_loss', 0):.2f}
- 最大盈利: ${performance.get('max_win', 0):.2f}
- 最大亏损: ${performance.get('max_loss', 0):.2f}
- 盈亏比: {performance.get('profit_factor', 0):.2f}
- 平均持仓时间: {performance.get('avg_holding_time', 0):.1f} 分钟

## 2. 多空分析

- 做多交易: {len(df[df['side'] == 'LONG'])} 笔
- 做多胜率: {performance.get('long_win_rate', 0)*100:.1f}%
- 做多盈亏: ${performance.get('long_pnl', 0):.2f}
- 做空交易: {len(df[df['side'] == 'SHORT'])} 笔
- 做空胜率: {performance.get('short_win_rate', 0)*100:.1f}%
- 做空盈亏: ${performance.get('short_pnl', 0):.2f}

## 3. 信号强度分析
"""
            
            signal_stats = performance.get('signal_strength_stats', {})
            for strength, stats in signal_stats.items():
                report += f"""
- {strength}信号: {stats['count']} 笔, 胜率 {stats['win_rate']*100:.1f}%, 平均盈亏 ${stats['avg_pnl']:.2f}
"""
            
            report += "\n## 4. 市场环境分析\n"
            market_stats = performance.get('market_type_stats', {})
            for market_type, stats in market_stats.items():
                report += f"""
- {market_type}: {stats['count']} 笔, 胜率 {stats['win_rate']*100:.1f}%, 平均盈亏 ${stats['avg_pnl']:.2f}
"""
            
            report += "\n## 5. 平仓原因分析\n"
            close_reason_stats = performance.get('close_reason_stats', {})
            for reason, stats in close_reason_stats.items():
                report += f"""
- {reason}: {stats['count']} 笔, 胜率 {stats['win_rate']*100:.1f}%, 平均盈亏 ${stats['avg_pnl']:.2f}
"""
            
            report += "\n## 6. 优化建议\n"
            for suggestion in suggestions:
                report += f"""
### [{suggestion['type']}] {suggestion['category']}
**问题**: {suggestion['issue']}
**建议**: {suggestion['suggestion']}
**优先级**: {suggestion['priority']}
"""
            
            return report
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"生成报告时出错: {e}"