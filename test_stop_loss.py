"""
测试止损功能脚本
演示如何使用条件单设置止损
"""

import os
import sys
import logging
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.trading.trading_executor import TradingExecutor
from src.config.config_manager import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_stop_loss_functionality():
    """测试止损功能"""
    
    # 加载环境变量
    load_dotenv()
    
    # 获取API密钥
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("请设置 BINANCE_API_KEY 和 BINANCE_API_SECRET 环境变量")
        return
    
    # 加载配置
    config = ConfigManager('config.toml')
    
    # 初始化交易执行器
    leverage = config.get('trading.leverage', 10)
    executor = TradingExecutor(api_key, api_secret, leverage)
    
    # 测试交易对
    symbol = config.get('binance.symbols', ['BTCUSDC'])[0]
    stop_loss_roi = config.get('trading.stop_loss_roi', -0.40)
    
    logger.info(f"开始测试止损功能")
    logger.info(f"交易对: {symbol}")
    logger.info(f"止损ROI: {stop_loss_roi:.2%}")
    logger.info(f"杠杆倍数: {leverage}x")
    
    try:
        # 1. 设置杠杆和保证金模式
        logger.info("\n=== 步骤1: 设置杠杆和保证金模式 ===")
        margin_type = config.get('trading.margin_type', 'cross')
        
        executor.set_leverage(symbol, leverage)
        executor.set_margin_type(symbol, margin_type)
        
        # 2. 获取账户余额
        logger.info("\n=== 步骤2: 获取账户余额 ===")
        balance = executor.get_account_balance(symbol)
        if balance is None or balance <= 0:
            logger.error("账户余额不足，无法测试")
            return
        
        logger.info(f"可用余额: {balance:.2f}")
        
        # 3. 获取当前价格
        logger.info("\n=== 步骤3: 获取当前价格 ===")
        current_price = executor.get_current_price(symbol)
        if current_price is None:
            logger.error("无法获取当前价格")
            return
        
        logger.info(f"当前价格: {current_price:.2f}")
        
        # 4. 计算仓位大小（使用小仓位测试）
        logger.info("\n=== 步骤4: 计算仓位大小 ===")
        # 使用10%的余额进行测试
        test_balance = balance * 0.1
        quantity = executor.calculate_position_size(test_balance, current_price, symbol)
        logger.info(f"测试仓位数量: {quantity:.8f}")
        
        # 5. 开多仓并设置止损
        logger.info("\n=== 步骤5: 开多仓并设置止损 ===")
        order = executor.open_long_position(symbol, quantity, stop_loss_roi)
        
        if order:
            logger.info(f"开仓成功!")
            logger.info(f"订单ID: {order.get('orderId', 'N/A')}")
            logger.info(f"止损单ID: {order.get('stop_loss_order_id', 'N/A')}")
            
            # 6. 查看活跃的止损单
            logger.info("\n=== 步骤6: 查看活跃的止损单 ===")
            active_orders = executor.get_active_stop_loss_orders(symbol)
            logger.info(f"活跃止损单数量: {len(active_orders)}")
            for order_id, order_info in active_orders.items():
                logger.info(f"  订单ID: {order_id}")
                logger.info(f"  类型: {order_info['order_type']}")
                logger.info(f"  触发价格: {order_info['trigger_price']:.2f}")
                logger.info(f"  持仓方向: {order_info['position_side']}")
            
            # 7. 获取持仓信息
            logger.info("\n=== 步骤7: 获取持仓信息 ===")
            position_info = executor.get_position_info(symbol)
            if position_info:
                logger.info(f"持仓数量: {position_info['position_amount']:.8f}")
                logger.info(f"入场价格: {position_info['entry_price']:.2f}")
                logger.info(f"未实现盈亏: {position_info['unrealized_pnl']:.2f}")
                logger.info(f"杠杆: {position_info['leverage']}x")
            
            # 8. 等待用户确认是否平仓
            logger.info("\n=== 步骤8: 等待用户确认 ===")
            logger.info("止损单已设置，系统会在价格达到止损价时自动平仓")
            logger.info("如需手动平仓，请按 Ctrl+C 或输入 'close'")
            
            # 简单的交互式等待
            import time
            try:
                while True:
                    time.sleep(5)
                    
                    # 定期检查持仓状态
                    position_info = executor.get_position_info(symbol)
                    if not position_info:
                        logger.info("持仓已平仓（可能被止损单触发）")
                        break
                    
                    # 显示当前盈亏
                    current_price = executor.get_current_price(symbol)
                    if current_price:
                        entry_price = position_info['entry_price']
                        position_amount = position_info['position_amount']
                        leverage = position_info['leverage']
                        
                        # 计算ROI
                        price_diff = current_price - entry_price
                        roi = (price_diff / entry_price) * leverage
                        pnl = price_diff * position_amount
                        
                        logger.info(f"当前价格: {current_price:.2f}, ROI: {roi:.2%}, PnL: {pnl:.2f}")
                        
            except KeyboardInterrupt:
                logger.info("\n用户中断，准备平仓...")
                
                # 平仓
                logger.info("\n=== 步骤9: 平仓 ===")
                from src.trading.position_manager import PositionType
                close_order = executor.close_position(
                    symbol, 
                    PositionType.LONG, 
                    abs(position_info['position_amount'])
                )
                
                if close_order:
                    logger.info("平仓成功!")
                    
                    # 撤销止损单
                    logger.info("\n=== 步骤10: 撤销止损单 ===")
                    stop_loss_order_id = order.get('stop_loss_order_id')
                    if stop_loss_order_id:
                        executor.cancel_stop_loss_order(symbol, stop_loss_order_id)
                        logger.info("止损单已撤销")
                    
                    # 查看剩余的止损单
                    active_orders = executor.get_active_stop_loss_orders(symbol)
                    logger.info(f"剩余止损单数量: {len(active_orders)}")
        
        else:
            logger.error("开仓失败")
    
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info("\n=== 测试完成 ===")


if __name__ == '__main__':
    test_stop_loss_functionality()