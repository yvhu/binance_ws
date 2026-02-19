"""
交易数据分析脚本
分析记录的交易数据，生成优化建议
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from src.data.trade_analyzer import TradeAnalyzer
from src.utils.logger import setup_logger


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='分析交易数据')
    parser.add_argument('--days', type=int, default=30, help='分析最近几天的数据')
    parser.add_argument('--data-dir', type=str, default='./logs/trades', help='数据目录')
    parser.add_argument('--output', type=str, default='./logs/trades/analysis_report.md', help='输出报告文件')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logger('trade_analyzer', './logs/trade_analyzer.log')
    
    logger.info(f"开始分析交易数据，数据范围: 最近 {args.days} 天")
    
    # 创建分析器
    analyzer = TradeAnalyzer(data_dir=args.data_dir)
    
    # 生成报告
    report = analyzer.generate_report(days=args.days)
    
    # 保存报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    logger.info(f"分析报告已保存到: {output_path}")
    
    # 打印报告
    print("\n" + "="*80)
    print(report)
    print("="*80 + "\n")


if __name__ == '__main__':
    main()