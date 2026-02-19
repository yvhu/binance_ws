# 限价单系统优化执行方案

## 概述

本文档将限价单系统的优化建议整理为可执行的方案列表，按照优先级和依赖关系组织，便于逐步实施和完善。

## 第一阶段：核心稳定性优化（必需）

### 任务 1.1：订单状态持久化
**优先级**: 🔴 P0 - 最高
**预计工时**: 4-6小时
**依赖**: 无

#### 目标
实现订单状态的持久化存储，确保程序重启后订单信息不丢失。

#### 实施步骤

1. **创建订单持久化类**
   ```python
   # src/trading/order_persistence.py
   import sqlite3
   import json
   from datetime import datetime
   from typing import Dict, Optional
   
   class OrderPersistence:
       def __init__(self, db_path: str = "data/orders.db"):
           self.db_path = db_path
           self._init_db()
       
       def _init_db(self):
           """初始化数据库"""
           conn = sqlite3.connect(self.db_path)
           cursor = conn.cursor()
           cursor.execute('''
               CREATE TABLE IF NOT EXISTS orders (
                   order_id INTEGER PRIMARY KEY,
                   symbol TEXT NOT NULL,
                   side TEXT NOT NULL,
                   order_price REAL NOT NULL,
                   quantity REAL NOT NULL,
                   timestamp REAL NOT NULL,
                   status TEXT NOT NULL,
                   order_info TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL
               )
           ''')
           conn.commit()
           conn.close()
       
       def save_order(self, order_id: int, symbol: str, order_info: Dict):
           """保存订单"""
           conn = sqlite3.connect(self.db_path)
           cursor = conn.cursor()
           now = datetime.now().isoformat()
           
           cursor.execute('''
               INSERT OR REPLACE INTO orders 
               (order_id, symbol, side, order_price, quantity, timestamp, 
                status, order_info, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ''', (
               order_id,
               symbol,
               order_info['side'],
               order_info['order_price'],
               order_info['quantity'],
               order_info['timestamp'],
               'PENDING',
               json.dumps(order_info),
               now,
               now
           ))
           
           conn.commit()
           conn.close()
       
       def load_pending_orders(self) -> Dict[str, Dict]:
           """加载所有未完成订单"""
           conn = sqlite3.connect(self.db_path)
           cursor = conn.cursor()
           
           cursor.execute('''
               SELECT order_id, symbol, order_info 
               FROM orders 
               WHERE status = 'PENDING'
           ''')
           
           orders = {}
           for row in cursor.fetchall():
               order_id, symbol, order_info_json = row
               order_info = json.loads(order_info_json)
               if symbol not in orders:
                   orders[symbol] = {}
               orders[symbol][order_id] = order_info
           
           conn.close()
           return orders
       
       def update_order_status(self, order_id: int, status: str):
           """更新订单状态"""
           conn = sqlite3.connect(self.db_path)
           cursor = conn.cursor()
           now = datetime.now().isoformat()
           
           cursor.execute('''
               UPDATE orders 
               SET status = ?, updated_at = ?
               WHERE order_id = ?
           ''', (status, now, order_id))
           
           conn.commit()
           conn.close()
       
       def delete_order(self, order_id: int):
           """删除订单"""
           conn = sqlite3.connect(self.db_path)
           cursor = conn.cursor()
           
           cursor.execute('DELETE FROM orders WHERE order_id = ?', (order_id,))
           
           conn.commit()
           conn.close()
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..trading.order_persistence import OrderPersistence
   
   self.order_persistence = OrderPersistence()
   
   # 启动时加载未完成订单
   self.pending_limit_orders = self.order_persistence.load_pending_orders()
   
   # 同步订单状态
   await self._sync_orders_with_exchange()
   ```

3. **添加订单状态同步方法**
   ```python
   async def _sync_orders_with_exchange(self):
       """与交易所同步订单状态"""
       for symbol in list(self.pending_limit_orders.keys()):
           try:
               # 获取交易所的未完成订单
               open_orders = await asyncio.to_thread(
                   self.trading_executor.get_open_orders,
                   symbol
               )
               
               exchange_order_ids = {order['orderId'] for order in open_orders}
               local_order_ids = set(self.pending_limit_orders[symbol].keys())
               
               # 处理本地有但交易所没有的订单（可能已成交或取消）
               for order_id in local_order_ids - exchange_order_ids:
                   logger.info(f"Order {order_id} not found in exchange, removing from tracking")
                   self.order_persistence.update_order_status(order_id, 'UNKNOWN')
                   del self.pending_limit_orders[symbol][order_id]
               
               # 处理交易所有但本地没有的订单（程序重启前创建的）
               for order_id in exchange_order_ids - local_order_ids:
                   logger.info(f"Found new order {order_id} in exchange, adding to tracking")
                   # 从交易所获取订单详情并添加到跟踪
                   order_detail = await asyncio.to_thread(
                       self.trading_executor.get_order,
                       symbol,
                       order_id
                   )
                   if order_detail:
                       self._add_order_to_tracking(symbol, order_detail)
               
           except Exception as e:
               logger.error(f"Error syncing orders for {symbol}: {e}")
   ```

4. **在订单操作时更新持久化**
   - 创建订单时调用 `save_order()`
   - 订单成交时调用 `update_order_status(order_id, 'FILLED')`
   - 取消订单时调用 `update_order_status(order_id, 'CANCELLED')`

#### 验证标准
- [ ] 程序重启后能正确加载未完成订单
- [ ] 与交易所订单状态保持同步
- [ ] 订单状态更新能正确持久化

---

### 任务 1.2：部分成交处理
**优先级**: 🔴 P0 - 最高
**预计工时**: 3-4小时
**依赖**: 任务 1.1

#### 目标
正确处理订单的部分成交情况，跟踪已成交和剩余数量。

#### 实施步骤

1. **扩展订单信息结构**
   ```python
   # 在创建订单时添加部分成交字段
   self.pending_limit_orders[symbol][order_id] = {
       'side': 'LONG',
       'order_price': limit_price,
       'original_quantity': quantity,      # 原始数量
       'filled_quantity': 0,               # 已成交数量
       'remaining_quantity': quantity,     # 剩余数量
       'avg_fill_price': 0,                # 平均成交价
       'partial_fills': [],                # 部分成交记录
       'timestamp': time.time(),
       # ... 其他字段
   }
   ```

2. **添加部分成交处理方法**
   ```python
   async def handle_partial_fill(self, symbol: str, order_id: int, fill_info: Dict):
       """处理部分成交"""
       try:
           if symbol not in self.pending_limit_orders:
               return
           
           if order_id not in self.pending_limit_orders[symbol]:
               return
           
           order = self.pending_limit_orders[symbol][order_id]
           fill_qty = float(fill_info['executedQty'])
           fill_price = float(fill_info['price'])
           
           # 更新成交信息
           order['filled_quantity'] += fill_qty
           order['remaining_quantity'] -= fill_qty
           
           # 计算平均成交价
           if order['filled_quantity'] > 0:
               total_value = order['avg_fill_price'] * (order['filled_quantity'] - fill_qty)
               total_value += fill_price * fill_qty
               order['avg_fill_price'] = total_value / order['filled_quantity']
           
           # 记录部分成交
           order['partial_fills'].append({
               'quantity': fill_qty,
               'price': fill_price,
               'time': datetime.now().isoformat()
           })
           
           # 更新持久化
           self.order_persistence.save_order(order_id, symbol, order)
           
           # 发送部分成交通知
           await self.telegram_client.send_message(
               f"📊 部分成交\n\n"
               f"交易对: {symbol}\n"
               f"订单ID: {order_id}\n"
               f"成交数量: {fill_qty:.4f}\n"
               f"成交价格: ${fill_price:.2f}\n"
               f"已成交: {order['filled_quantity']:.4f}\n"
               f"剩余: {order['remaining_quantity']:.4f}\n"
               f"平均价: ${order['avg_fill_price']:.2f}"
           )
           
           # 如果完全成交，处理持仓
           if order['remaining_quantity'] <= 0.0001:  # 考虑精度
               await self.on_order_fully_filled(symbol, order_id)
               
       except Exception as e:
           logger.error(f"Error handling partial fill: {e}")
   ```

3. **添加完全成交处理**
   ```python
   async def on_order_fully_filled(self, symbol: str, order_id: int):
       """订单完全成交时的处理"""
       try:
           order = self.pending_limit_orders[symbol][order_id]
           
           # 更新订单状态
           self.order_persistence.update_order_status(order_id, 'FILLED')
           
           # 创建持仓
           self.position_manager.open_position(
               symbol=symbol,
               side=order['side'],
               entry_price=order['avg_fill_price'],
               quantity=order['filled_quantity'],
               entry_kline=order.get('entry_kline')
           )
           
           # 设置止损
           position = self.position_manager.get_position(symbol)
           if position and order.get('stop_loss_price'):
               position['stop_loss_price'] = order['stop_loss_price']
           
           # 初始化跟踪
           self.position_peak_prices[symbol] = order['avg_fill_price']
           self.position_entry_times[symbol] = order.get('kline_time', int(time.time() * 1000))
           self.partial_take_profit_status[symbol] = {i: False for i in range(len(self.partial_take_profit_levels))}
           
           # 发送成交通知
           await self.telegram_client.send_trade_notification(
               symbol=symbol,
               side=order['side'],
               price=order['avg_fill_price'],
               quantity=order['filled_quantity'],
               leverage=self.config.leverage,
               volume_info=order.get('volume_info'),
               range_info=order.get('range_info'),
               stop_loss_price=order.get('stop_loss_price'),
               position_calc_info=None,
               kline_time=order.get('kline_time')
           )
           
           # 清理订单跟踪
           del self.pending_limit_orders[symbol][order_id]
           
           logger.info(f"Order {order_id} fully filled for {symbol}")
           
       except Exception as e:
           logger.error(f"Error handling fully filled order: {e}")
   ```

4. **集成到订单监控器**
   - 在 `LimitOrderMonitor` 中添加部分成交检测
   - 定期查询订单状态，检测部分成交

#### 验证标准
- [ ] 能正确跟踪部分成交
- [ ] 能计算平均成交价
- [ ] 完全成交后能正确创建持仓
- [ ] 部分成交通知正常发送

---

### 任务 1.3：错误处理和重试机制
**优先级**: 🔴 P0 - 最高
**预计工时**: 3-4小时
**依赖**: 任务 1.1

#### 目标
为所有订单操作添加完善的错误处理和重试机制。

#### 实施步骤

1. **创建重试装饰器**
   ```python
   # src/utils/retry.py
   import asyncio
   import functools
   import logging
   
   logger = logging.getLogger(__name__)
   
   def async_retry(max_retries: int = 3, backoff_factor: float = 2.0):
       """异步重试装饰器"""
       def decorator(func):
           @functools.wraps(func)
           async def wrapper(*args, **kwargs):
               last_exception = None
               
               for attempt in range(max_retries):
                   try:
                       return await func(*args, **kwargs)
                   except Exception as e:
                       last_exception = e
                       if attempt < max_retries - 1:
                           wait_time = backoff_factor ** attempt
                           logger.warning(
                               f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                               f"retrying in {wait_time}s: {e}"
                           )
                           await asyncio.sleep(wait_time)
                       else:
                           logger.error(
                               f"{func.__name__} failed after {max_retries} attempts: {e}"
                           )
               
               raise last_exception
           
           return wrapper
       return decorator
   ```

2. **为关键操作添加重试**
   ```python
   from ..utils.retry import async_retry
   
   @async_retry(max_retries=3, backoff_factor=2.0)
   async def _convert_limit_to_market(self, symbol: str, order_id: int, 
                                     order_info: Dict, reason: str) -> bool:
       """带重试的限价单转市价单"""
       # 原有实现
       pass
   
   @async_retry(max_retries=3, backoff_factor=2.0)
   async def _check_and_cancel_pending_orders(self, symbol: str, reason: str) -> None:
       """带重试的取消订单"""
       # 原有实现
       pass
   ```

3. **添加错误恢复机制**
   ```python
   async def handle_order_operation_failure(self, symbol: str, order_id: int, 
                                           operation: str, error: Exception):
       """处理订单操作失败"""
       logger.error(f"Order operation failed: {operation} for {symbol} order {order_id}: {error}")
       
       # 发送错误通知
       await self.telegram_client.send_message(
           f"❌ 订单操作失败\n\n"
           f"交易对: {symbol}\n"
           f"订单ID: {order_id}\n"
           f"操作: {operation}\n"
           f"错误: {str(error)}"
       )
       
       # 根据错误类型采取不同措施
       if "insufficient" in str(error).lower():
           # 资金不足，取消订单
           await self._check_and_cancel_pending_orders(symbol, "资金不足")
       elif "network" in str(error).lower() or "timeout" in str(error).lower():
           # 网络问题，标记为需要同步
           self.orders_need_sync.add(symbol)
       else:
           # 其他错误，记录日志
           logger.error(f"Unhandled error: {error}")
   ```

4. **添加订单状态检查**
   ```python
   async def verify_order_status(self, symbol: str, order_id: int) -> Optional[str]:
       """验证订单状态"""
       try:
           order_status = await asyncio.to_thread(
               self.trading_executor.get_order_status,
               symbol,
               order_id
           )
           return order_status
       except Exception as e:
           logger.error(f"Error verifying order status: {e}")
           return None
   ```

#### 验证标准
- [ ] 网络错误能自动重试
- [ ] 重试失败后能正确处理
- [ ] 错误通知能正常发送
- [ ] 不会因为错误导致程序崩溃

---

### 任务 1.4：资金管理优化
**优先级**: 🔴 P0 - 最高
**预计工时**: 2-3小时
**依赖**: 任务 1.1

#### 目标
优化资金管理，避免保证金不足问题。

#### 实施步骤

1. **添加保证金检查**
   ```python
   def check_available_margin(self, symbol: str, new_order_quantity: float) -> Tuple[bool, float]:
       """检查是否有足够保证金"""
       try:
           # 获取账户信息
           account_info = self.trading_executor.get_account_info()
           available_balance = account_info['availableBalance']
           
           # 计算已占用保证金
           used_margin = 0.0
           if symbol in self.pending_limit_orders:
               for order_info in self.pending_limit_orders[symbol].values():
                   order_price = order_info['order_price']
                   quantity = order_info['remaining_quantity']  # 使用剩余数量
                   leverage = self.config.leverage
                   used_margin += (order_price * quantity) / leverage
           
           # 计算新订单需要的保证金
           current_price = self.data_handler.get_current_price(symbol)
           new_order_margin = (current_price * new_order_quantity) / self.config.leverage
           
           # 检查是否足够
           total_required = used_margin + new_order_margin
           available = available_balance - total_required
           
           if available < 0:
               logger.warning(
                   f"Insufficient margin: available={available_balance:.2f}, "
                   f"used={used_margin:.2f}, required={total_required:.2f}"
               )
               return False, available
           
           return True, available
           
       except Exception as e:
           logger.error(f"Error checking margin: {e}")
           return False, 0
   ```

2. **优化订单数量**
   ```python
   def optimize_order_quantity(self, symbol: str, desired_quantity: float) -> float:
       """根据可用资金优化订单数量"""
       try:
           account_info = self.trading_executor.get_account_info()
           available_balance = account_info['availableBalance']
           
           # 计算最大可用数量
           current_price = self.data_handler.get_current_price(symbol)
           max_quantity = (available_balance * self.config.leverage) / current_price
           
           # 考虑已占用保证金
           if symbol in self.pending_limit_orders:
               used_quantity = sum(
                   order_info['remaining_quantity'] 
                   for order_info in self.pending_limit_orders[symbol].values()
               )
               max_quantity -= used_quantity
           
           # 保留10%缓冲
           max_quantity *= 0.9
           
           # 返回较小值
           optimized_quantity = min(desired_quantity, max_quantity)
           
           if optimized_quantity < desired_quantity:
               logger.info(
                   f"Order quantity optimized: {desired_quantity:.4f} -> {optimized_quantity:.4f}"
               )
           
           return max(0, optimized_quantity)
           
       except Exception as e:
           logger.error(f"Error optimizing quantity: {e}")
           return desired_quantity
   ```

3. **集成到开仓流程**
   ```python
   # 在 _open_long_position_with_limit_order 中添加
   # 检查保证金
   has_margin, available = self.check_available_margin(symbol, quantity)
   if not has_margin:
       logger.warning(f"Insufficient margin for {symbol}, cancelling pending orders")
       await self._check_and_cancel_pending_orders(symbol, "保证金不足")
       return
   
   # 优化订单数量
   optimized_quantity = self.optimize_order_quantity(symbol, quantity)
   if optimized_quantity < quantity * 0.5:  # 如果优化后数量减少超过50%
       logger.warning(f"Order quantity too small after optimization: {optimized_quantity:.4f}")
       return
   
   quantity = optimized_quantity
   ```

#### 验证标准
- [ ] 能正确计算已占用保证金
- [ ] 能根据可用资金优化订单数量
- [ ] 保证金不足时能正确处理
- [ ] 不会因为保证金问题导致交易失败

---

### 任务 1.5：风险控制增强
**优先级**: 🔴 P0 - 最高
**预计工时**: 3-4小时
**依赖**: 任务 1.1

#### 目标
增强订单级别的风险控制。

#### 实施步骤

1. **创建风险控制类**
   ```python
   # src/trading/order_risk_control.py
   class OrderRiskControl:
       def __init__(self, config):
           self.config = config
           self.max_price_deviation = 0.01  # 最大价格偏离 1%
           self.max_stop_loss_distance = 0.05  # 最大止损距离 5%
           self.min_order_book_depth = 1000  # 最小订单簿深度
           self.max_volatility = 0.05  # 最大波动率 5%
       
       def check_order_risk(self, order_info: Dict, current_price: float) -> Tuple[bool, str]:
           """检查订单风险"""
           order_price = order_info['order_price']
           side = order_info['side']
           
           # 检查价格偏离
           price_deviation = abs(order_price - current_price) / current_price
           if price_deviation > self.max_price_deviation:
               return False, f"价格偏离过大: {price_deviation*100:.2f}%"
           
           # 检查止损距离
           stop_loss_price = order_info.get('stop_loss_price')
           if stop_loss_price:
               if side == 'LONG':
                   stop_loss_distance = (current_price - stop_loss_price) / current_price
               else:
                   stop_loss_distance = (stop_loss_price - current_price) / current_price
               
               if stop_loss_distance > self.max_stop_loss_distance:
                   return False, f"止损距离过大: {stop_loss_distance*100:.2f}%"
           
           # 检查订单数量
           quantity = order_info['quantity']
           max_quantity = self.config.get_max_order_quantity()
           if quantity > max_quantity:
               return False, f"订单数量过大: {quantity} > {max_quantity}"
           
           return True, "OK"
       
       def check_market_conditions(self, symbol: str, data_handler) -> Tuple[bool, str]:
           """检查市场条件"""
           # 检查流动性
           order_book = data_handler.get_order_book(symbol)
           if order_book and len(order_book.get('bids', [])) > 0:
               bid_quantity = order_book['bids'][0][1]
               if bid_quantity < self.min_order_book_depth:
                   return False, f"市场流动性不足: {bid_quantity}"
           
           # 检查价格波动
           recent_prices = data_handler.get_recent_prices(symbol, 60)
           if recent_prices and len(recent_prices) > 1:
               volatility = self.calculate_volatility(recent_prices)
               if volatility > self.max_volatility:
                   return False, f"市场波动率过高: {volatility*100:.2f}%"
           
           return True, "OK"
       
       def calculate_volatility(self, prices: list) -> float:
           """计算价格波动率"""
           if len(prices) < 2:
               return 0
           
           returns = []
           for i in range(1, len(prices)):
               ret = (prices[i] - prices[i-1]) / prices[i-1]
               returns.append(ret)
           
           if not returns:
               return 0
           
           import statistics
           return statistics.stdev(returns) if len(returns) > 1 else 0
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..trading.order_risk_control import OrderRiskControl
   
   self.order_risk_control = OrderRiskControl(self.config)
   ```

3. **在开仓前进行风险检查**
   ```python
   # 在 _open_long_position_with_limit_order 中添加
   # 检查市场条件
   market_ok, market_reason = self.order_risk_control.check_market_conditions(
       symbol, self.data_handler
   )
   if not market_ok:
       logger.warning(f"Market conditions not suitable for {symbol}: {market_reason}")
       return
   
   # 检查订单风险
   order_info = {
       'side': 'LONG',
       'order_price': limit_price,
       'quantity': quantity,
       'stop_loss_price': stop_loss_price
   }
   
   order_ok, order_reason = self.order_risk_control.check_order_risk(
       order_info, current_price
   )
   if not order_ok:
       logger.warning(f"Order risk check failed for {symbol}: {order_reason}")
       return
   ```

#### 验证标准
- [ ] 能正确检测价格偏离
- [ ] 能正确检查止损距离
- [ ] 能正确评估市场条件
- [ ] 风险检查失败时能正确处理

---

## 第二阶段：功能优化（重要）

### 任务 2.1：订单修改功能
**优先级**: 🟡 P1 - 高
**预计工时**: 2-3小时
**依赖**: 任务 1.1, 1.2

#### 目标
实现订单价格和数量的修改功能。

#### 实施步骤

1. **实现订单修改方法**
   ```python
   async def modify_limit_order(self, symbol: str, order_id: int, 
                               new_price: float, new_quantity: float = None) -> bool:
       """修改限价单价格或数量"""
       try:
           # 检查订单是否存在
           if symbol not in self.pending_limit_orders:
               return False
           
           if order_id not in self.pending_limit_orders[symbol]:
               return False
           
           order_info = self.pending_limit_orders[symbol][order_id]
           
           # 取消原订单
           cancel_result = await self._check_and_cancel_pending_orders(
               symbol, 
               f"修改订单: order_id={order_id}"
           )
           
           if not cancel_result:
               logger.error(f"Failed to cancel order {order_id} for modification")
               return False
           
           # 使用新参数重新下单
           quantity = new_quantity or order_info['quantity']
           
           if order_info['side'] == 'LONG':
               result = self.trading_executor.open_long_position_limit(
                   symbol=symbol,
                   quantity=quantity,
                   price=new_price
               )
           else:
               result = self.trading_executor.open_short_position_limit(
                   symbol=symbol,
                   quantity=quantity,
                   price=new_price
               )
           
           if result:
               # 更新订单跟踪
               new_order_id = result['order']['orderId']
               del self.pending_limit_orders[symbol][order_id]
               
               # 更新订单信息
               order_info['order_price'] = new_price
               if new_quantity:
                   order_info['quantity'] = new_quantity
                   order_info['original_quantity'] = new_quantity
                   order_info['remaining_quantity'] = new_quantity
               
               self.pending_limit_orders[symbol][new_order_id] = order_info
               
               # 更新持久化
               self.order_persistence.save_order(new_order_id, symbol, order_info)
               
               # 发送通知
               await self.telegram_client.send_message(
                   f"✏️ 订单修改\n\n"
                   f"交易对: {symbol}\n"
                   f"原订单ID: {order_id}\n"
                   f"新订单ID: {new_order_id}\n"
                   f"新价格: ${new_price:.2f}\n"
                   f"新数量: {quantity:.4f}"
               )
               
               logger.info(f"Order modified successfully: {order_id} -> {new_order_id}")
               return True
           
           return False
           
       except Exception as e:
           logger.error(f"Error modifying order: {e}")
           return False
   ```

2. **添加智能修改策略**
   ```python
   async def smart_modify_order(self, symbol: str, order_id: int) -> bool:
       """智能修改订单价格"""
       try:
           order_info = self.pending_limit_orders[symbol][order_id]
           current_price = self.data_handler.get_current_price(symbol)
           
           # 计算新的限价价格
           if order_info['side'] == 'LONG':
               # 做多：价格略低于当前价
               new_price = current_price * (1 - self.limit_order_entry_price_offset_percent)
           else:
               # 做空：价格略高于当前价
               new_price = current_price * (1 + self.limit_order_entry_price_offset_percent)
           
           # 检查价格变化幅度
           price_change = abs(new_price - order_info['order_price']) / order_info['order_price']
           if price_change < 0.001:  # 变化小于0.1%，不修改
               return False
           
           # 修改订单
           return await self.modify_limit_order(symbol, order_id, new_price)
           
       except Exception as e:
           logger.error(f"Error in smart modify: {e}")
           return False
   ```

#### 验证标准
- [ ] 能成功修改订单价格
- [ ] 能成功修改订单数量
- [ ] 修改后订单跟踪正确
- [ ] 修改通知正常发送

---

### 任务 2.2：订单优先级系统
**优先级**: 🟡 P1 - 高
**预计工时**: 2-3小时
**依赖**: 任务 1.1

#### 目标
实现订单优先级管理，优化资源利用。

#### 实施步骤

1. **创建优先级管理类**
   ```python
   # src/trading/order_priority.py
   class OrderPriority:
       def __init__(self):
           pass
       
       def calculate_priority(self, order_info: Dict, current_price: float) -> float:
           """计算订单优先级分数"""
           score = 0.0
           
           # 信号强度权重 (30分)
           signal_strength = order_info.get('signal_strength', 'MEDIUM')
           if signal_strength == 'STRONG':
               score += 30
           elif signal_strength == 'MEDIUM':
               score += 20
           else:
               score += 10
           
           # 时间权重 (越新越好，最多20分)
           import time
           age = time.time() - order_info.get('timestamp', time.time())
           time_score = max(0, 20 - age * 0.1)  # 每秒减少0.1分
           score += time_score
           
           # 价格优势权重 (最多30分)
           order_price = order_info['order_price']
           if order_info['side'] == 'LONG':
               # 做多：限价越低越好
               price_advantage = (current_price - order_price) / current_price
           else:
               # 做空：限价越高越好
               price_advantage = (order_price - current_price) / current_price
           
           price_score = min(30, price_advantage * 1000)  # 最多30分
           score += price_score
           
           # 成交概率权重 (最多20分)
           # 基于价格距离和订单簿深度
           price_distance = abs(order_price - current_price) / current_price
           probability_score = max(0, 20 - price_distance * 1000)
           score += probability_score
           
           return score
       
       def get_lowest_priority_order(self, orders: Dict, current_price: float) -> Optional[int]:
           """获取优先级最低的订单ID"""
           lowest_order_id = None
           lowest_score = float('inf')
           
           for order_id, order_info in orders.items():
               score = self.calculate_priority(order_info, current_price)
               if score < lowest_score:
                   lowest_score = score
                   lowest_order_id = order_id
           
           return lowest_order_id
       
       def sort_orders_by_priority(self, orders: Dict, current_price: float) -> list:
           """按优先级排序订单"""
           order_scores = []
           for order_id, order_info in orders.items():
               score = self.calculate_priority(order_info, current_price)
               order_scores.append((order_id, score))
           
           # 按分数降序排序
           order_scores.sort(key=lambda x: x[1], reverse=True)
           
           return order_scores
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..trading.order_priority import OrderPriority
   
   self.order_priority = OrderPriority()
   ```

3. **在达到最大订单数时使用优先级**
   ```python
   # 修改 _open_long_position_with_limit_order 中的检查
   if symbol in self.pending_limit_orders and len(self.pending_limit_orders[symbol]) >= self.limit_order_max_pending_orders:
       logger.warning(f"Max pending orders reached for {symbol}")
       
       # 使用优先级系统选择要取消的订单
       current_price = self.data_handler.get_current_price(symbol)
       lowest_priority_order_id = self.order_priority.get_lowest_priority_order(
           self.pending_limit_orders[symbol],
           current_price
       )
       
       if lowest_priority_order_id:
           await self._convert_limit_to_market(
               symbol,
               lowest_priority_order_id,
               self.pending_limit_orders[symbol][lowest_priority_order_id],
               "达到最大挂单数量，取消最低优先级订单"
           )
   ```

#### 验证标准
- [ ] 能正确计算订单优先级
- [ ] 能正确识别最低优先级订单
- [ ] 优先级排序符合预期
- [ ] 资源紧张时能智能选择订单

---

### 任务 2.3：动态策略调整
**优先级**: 🟡 P1 - 高
**预计工时**: 3-4小时
**依赖**: 任务 1.1

#### 目标
根据市场条件动态调整订单策略。

#### 实施步骤

1. **创建动态策略类**
   ```python
   # src/trading/dynamic_order_strategy.py
   class DynamicOrderStrategy:
       def __init__(self, config):
           self.config = config
           self.base_timeout = config.get_config("trading.limit_order", "entry_limit_order_timeout", default=30)
       
       def get_timeout(self, market_volatility: float, market_trend: str) -> int:
           """根据市场波动率和趋势动态调整超时时间"""
           timeout = self.base_timeout
           
           # 根据波动率调整
           if market_volatility > 0.02:  # 高波动
               timeout = int(timeout * 0.5)  # 缩短超时
           elif market_volatility < 0.005:  # 低波动
               timeout = int(timeout * 2)  # 延长超时
           
           # 根据趋势调整
           if market_trend == 'STRONG':
               timeout = int(timeout * 0.8)  # 强趋势时缩短
           elif market_trend == 'WEAK':
               timeout = int(timeout * 1.2)  # 弱趋势时延长
           
           return max(10, min(120, timeout))  # 限制在10-120秒
       
       def get_action_on_timeout(self, market_trend: str, signal_strength: str) -> str:
           """根据市场趋势和信号强度决定超时处理方式"""
           if market_trend == 'STRONG' and signal_strength == 'STRONG':
               return 'convert_to_market'  # 强趋势+强信号：转为市价单
           elif market_trend == 'WEAK':
               return 'cancel'  # 弱趋势：取消订单
           else:
               return 'convert_to_market'  # 默认：转为市价单
       
       def should_cancel_on_price_move(self, price_move_percent: float, 
                                      order_age: float, market_volatility: float) -> bool:
           """根据价格移动幅度、订单年龄和市场波动率决定是否取消"""
           # 基础阈值
           if order_age < 10:  # 10秒内
               threshold = 0.005  # 0.5%
           elif order_age < 30:  # 30秒内
               threshold = 0.003  # 0.3%
           else:
               threshold = 0.002  # 0.2%
           
           # 根据波动率调整
           if market_volatility > 0.02:  # 高波动
               threshold *= 1.5  # 提高容忍度
           elif market_volatility < 0.005:  # 低波动
               threshold *= 0.7  # 降低容忍度
           
           return abs(price_move_percent) > threshold
       
       def get_price_offset(self, market_volatility: float, signal_strength: str) -> float:
           """根据市场波动率和信号强度动态调整价格偏移"""
           base_offset = 0.001  # 基础偏移 0.1%
           
           # 根据波动率调整
           if market_volatility > 0.02:  # 高波动
               offset = base_offset * 1.5  # 增加偏移
           elif market_volatility < 0.005:  # 低波动
               offset = base_offset * 0.7  # 减少偏移
           else:
               offset = base_offset
           
           # 根据信号强度调整
           if signal_strength == 'STRONG':
               offset *= 0.8  # 强信号：减少偏移，更快成交
           elif signal_strength == 'WEAK':
               offset *= 1.2  # 弱信号：增加偏移，更好价格
           
           return offset
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..trading.dynamic_order_strategy import DynamicOrderStrategy
   
   self.dynamic_strategy = DynamicOrderStrategy(self.config)
   ```

3. **在订单创建时使用动态策略**
   ```python
   # 在 _open_long_position_with_limit_order 中添加
   # 获取市场条件
   market_volatility = self._calculate_market_volatility(symbol)
   market_trend = self._get_market_trend(symbol)
   
   # 使用动态策略
   dynamic_offset = self.dynamic_strategy.get_price_offset(
       market_volatility, signal_strength
   )
   
   limit_price = self.trading_executor.calculate_entry_limit_price(
       symbol=symbol,
       side='LONG',
       current_price=current_price,
       offset_percent=dynamic_offset,
       use_support_resistance=self.limit_order_use_support_resistance,
       period=self.limit_order_support_resistance_period
   )
   
   # 使用动态超时
   dynamic_timeout = self.dynamic_strategy.get_timeout(
       market_volatility, market_trend
   )
   
   # 在监控器中使用动态超时
   monitor_task = asyncio.create_task(
       self.limit_order_monitor.start_monitor(
           symbol=symbol,
           order_id=order['orderId'],
           side='LONG',
           order_price=limit_price,
           quantity=final_quantity,
           stop_loss_price=stop_loss_price,
           take_profit_percent=take_profit_percent,
           volume_info=volume_info,
           range_info=range_info,
           entry_kline=entry_kline,
           kline_time=kline_time,
           signal_strength=signal_strength,
           timeout=dynamic_timeout
       )
   )
   ```

#### 验证标准
- [ ] 能根据市场条件动态调整超时时间
- [ ] 能根据市场条件动态调整处理策略
- [ ] 能根据市场条件动态调整价格偏移
- [ ] 动态调整符合预期效果

---

### 任务 2.4：性能监控和分析
**优先级**: 🟡 P1 - 高
**预计工时**: 3-4小时
**依赖**: 任务 1.1, 1.2

#### 目标
实现订单性能监控和分析。

#### 实施步骤

1. **创建性能跟踪类**
   ```python
   # src/trading/order_performance_tracker.py
   import time
   from datetime import datetime
   from typing import Dict, List
   
   class OrderPerformanceTracker:
       def __init__(self):
           self.order_stats = {
               'total_orders': 0,
               'filled_orders': 0,
               'cancelled_orders': 0,
               'timeout_orders': 0,
               'converted_to_market': 0,
               'partial_fills': 0,
               'total_fill_time': 0,
               'total_price_improvement': 0,
               'orders': {}  # order_id -> order_data
           }
       
       def record_order_placed(self, order_id: int, order_info: Dict):
           """记录订单创建"""
           self.order_stats['total_orders'] += 1
           self.order_stats['orders'][order_id] = {
               'order_info': order_info,
               'placed_time': time.time(),
               'filled_time': None,
               'fill_price': None,
               'status': 'PENDING'
           }
       
       def record_order_filled(self, order_id: int, fill_price: float):
           """记录订单成交"""
           if order_id not in self.order_stats['orders']:
               return
           
           order_data = self.order_stats['orders'][order_id]
           order_data['filled_time'] = time.time()
           order_data['fill_price'] = fill_price
           order_data['status'] = 'FILLED'
           
           self.order_stats['filled_orders'] += 1
           
           # 计算成交时间
           fill_time = order_data['filled_time'] - order_data['placed_time']
           self.order_stats['total_fill_time'] += fill_time
           
           # 计算价格改善
           order_price = order_data['order_info']['order_price']
           side = order_data['order_info']['side']
           
           if side == 'LONG':
               price_improvement = (order_price - fill_price) / order_price
           else:
               price_improvement = (fill_price - order_price) / order_price
           
           self.order_stats['total_price_improvement'] += price_improvement
       
       def record_order_cancelled(self, order_id: int, reason: str):
           """记录订单取消"""
           if order_id not in self.order_stats['orders']:
               return
           
           order_data = self.order_stats['orders'][order_id]
           order_data['status'] = 'CANCELLED'
           order_data['cancel_reason'] = reason
           
           self.order_stats['cancelled_orders'] += 1
           
           if reason == 'timeout':
               self.order_stats['timeout_orders'] += 1
       
       def record_order_converted(self, order_id: int):
           """记录订单转换为市价单"""
           if order_id not in self.order_stats['orders']:
               return
           
           self.order_stats['converted_to_market'] += 1
       
       def record_partial_fill(self, order_id: int):
           """记录部分成交"""
           self.order_stats['partial_fills'] += 1
       
       def get_performance_report(self) -> Dict:
           """获取性能报告"""
           total = self.order_stats['total_orders']
           if total == 0:
               return {}
           
           filled = self.order_stats['filled_orders']
           
           return {
               'total_orders': total,
               'fill_rate': filled / total if total > 0 else 0,
               'cancel_rate': self.order_stats['cancelled_orders'] / total if total > 0 else 0,
               'timeout_rate': self.order_stats['timeout_orders'] / total if total > 0 else 0,
               'conversion_rate': self.order_stats['converted_to_market'] / total if total > 0 else 0,
               'partial_fill_rate': self.order_stats['partial_fills'] / total if total > 0 else 0,
               'avg_fill_time': self.order_stats['total_fill_time'] / filled if filled > 0 else 0,
               'avg_price_improvement': self.order_stats['total_price_improvement'] / filled if filled > 0 else 0
           }
       
       def get_detailed_report(self) -> str:
           """获取详细报告"""
           report = self.get_performance_report()
           
           text = "📊 订单性能报告\n\n"
           text += f"总订单数: {report.get('total_orders', 0)}\n"
           text += f"成交率: {report.get('fill_rate', 0)*100:.1f}%\n"
           text += f"取消率: {report.get('cancel_rate', 0)*100:.1f}%\n"
           text += f"超时率: {report.get('timeout_rate', 0)*100:.1f}%\n"
           text += f"转换率: {report.get('conversion_rate', 0)*100:.1f}%\n"
           text += f"部分成交率: {report.get('partial_fill_rate', 0)*100:.1f}%\n"
           text += f"平均成交时间: {report.get('avg_fill_time', 0):.1f}秒\n"
           text += f"平均价格改善: {report.get('avg_price_improvement', 0)*100:.3f}%\n"
           
           return text
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..trading.order_performance_tracker import OrderPerformanceTracker
   
   self.performance_tracker = OrderPerformanceTracker()
   ```

3. **在订单操作时记录性能**
   ```python
   # 在创建订单时
   self.performance_tracker.record_order_placed(order['orderId'], order_info)
   
   # 在订单成交时
   self.performance_tracker.record_order_filled(order_id, fill_price)
   
   # 在订单取消时
   self.performance_tracker.record_order_cancelled(order_id, reason)
   
   # 在转换为市价单时
   self.performance_tracker.record_order_converted(order_id)
   
   # 在部分成交时
   self.performance_tracker.record_partial_fill(order_id)
   ```

4. **添加定期报告**
   ```python
   async def send_performance_report(self):
       """发送性能报告"""
       report = self.performance_tracker.get_detailed_report()
       await self.telegram_client.send_message(report)
   ```

#### 验证标准
- [ ] 能正确记录订单生命周期
- [ ] 能计算准确的性能指标
- [ ] 能生成详细的性能报告
- [ ] 报告数据准确可靠

---

## 第三阶段：用户体验优化（可选）

### 任务 3.1：订单管理API
**优先级**: 🟢 P2 - 中
**预计工时**: 2-3小时
**依赖**: 任务 1.1, 2.1

#### 目标
提供订单管理API，方便用户手动管理订单。

#### 实施步骤

1. **创建订单管理API类**
   ```python
   # src/trading/order_management_api.py
   class OrderManagementAPI:
       def __init__(self, strategy):
           self.strategy = strategy
       
       async def get_all_pending_orders(self) -> Dict:
           """获取所有未完成订单"""
           return self.strategy.pending_limit_orders
       
       async def get_order_info(self, symbol: str, order_id: int) -> Optional[Dict]:
           """获取订单信息"""
           if symbol in self.strategy.pending_limit_orders:
               return self.strategy.pending_limit_orders[symbol].get(order_id)
           return None
       
       async def cancel_order(self, symbol: str, order_id: int) -> bool:
           """手动取消订单"""
           return await self.strategy._check_and_cancel_pending_orders(
               symbol, 
               f"手动取消: order_id={order_id}"
           )
       
       async def modify_order(self, symbol: str, order_id: int, 
                             new_price: float) -> bool:
           """修改订单价格"""
           return await self.strategy.modify_limit_order(
               symbol, order_id, new_price
           )
       
       async def convert_to_market(self, symbol: str, order_id: int) -> bool:
           """转换为市价单"""
           if symbol in self.strategy.pending_limit_orders:
               order_info = self.strategy.pending_limit_orders[symbol].get(order_id)
               if order_info:
                   return await self.strategy._convert_limit_to_market(
                       symbol, order_id, order_info, "手动转换"
                   )
           return False
       
       async def get_performance_report(self) -> Dict:
           """获取性能报告"""
           return self.strategy.performance_tracker.get_performance_report()
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..trading.order_management_api import OrderManagementAPI
   
   self.order_api = OrderManagementAPI(self)
   ```

#### 验证标准
- [ ] API能正确获取订单信息
- [ ] API能正确取消订单
- [ ] API能正确修改订单
- [ ] API能正确转换订单

---

### 任务 3.2：增强通知系统
**优先级**: 🟢 P2 - 中
**预计工时**: 1-2小时
**依赖**: 任务 1.1

#### 目标
增强订单通知的详细程度和可读性。

#### 实施步骤

1. **创建通知格式化类**
   ```python
   # src/telegram/order_notification_formatter.py
   class OrderNotificationFormatter:
       @staticmethod
       def format_order_placed(order_info: Dict, symbol: str) -> str:
           """格式化订单创建通知"""
           message = f"📋 限价单已创建\n\n"
           message += f"交易对: {symbol}\n"
           message += f"方向: {order_info['side']}\n"
           message += f"订单价格: ${order_info['order_price']:.2f}\n"
           message += f"订单数量: {order_info['quantity']:.4f}\n"
           message += f"信号强度: {order_info['signal_strength']}\n"
           message += f"创建时间: {datetime.fromtimestamp(order_info['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}\n"
           
           if 'stop_loss_price' in order_info:
               message += f"止损价格: ${order_info['stop_loss_price']:.2f}\n"
           
           if 'take_profit_percent' in order_info:
               message += f"止盈比例: {order_info['take_profit_percent']*100:.1f}%\n"
           
           return message
       
       @staticmethod
       def format_order_filled(order_info: Dict, fill_price: float, 
                              fill_time: float, symbol: str) -> str:
           """格式化订单成交通知"""
           message = f"✅ 限价单已成交\n\n"
           message += f"交易对: {symbol}\n"
           message += f"方向: {order_info['side']}\n"
           message += f"订单价格: ${order_info['order_price']:.2f}\n"
           message += f"成交价格: ${fill_price:.2f}\n"
           message += f"成交数量: {order_info['filled_quantity']:.4f}\n"
           message += f"成交时间: {fill_time:.1f}秒\n"
           
           # 计算价格改善
           if order_info['side'] == 'LONG':
               improvement = (order_info['order_price'] - fill_price) / order_info['order_price']
           else:
               improvement = (fill_price - order_info['order_price']) / order_info['order_price']
           
           message += f"价格改善: {improvement*100:.3f}%\n"
           
           return message
       
       @staticmethod
       def format_order_cancelled(order_info: Dict, reason: str, symbol: str) -> str:
           """格式化订单取消通知"""
           message = f"🚫 限价单已取消\n\n"
           message += f"交易对: {symbol}\n"
           message += f"方向: {order_info['side']}\n"
           message += f"订单价格: ${order_info['order_price']:.2f}\n"
           message += f"取消原因: {reason}\n"
           
           return message
   ```

2. **集成到策略类**
   ```python
   # 在 FifteenMinuteStrategy.__init__ 中添加
   from ..telegram.order_notification_formatter import OrderNotificationFormatter
   
   self.notification_formatter = OrderNotificationFormatter()
   ```

3. **使用格式化器发送通知**
   ```python
   # 在创建订单时
   message = self.notification_formatter.format_order_placed(order_info, symbol)
   await self.telegram_client.send_message(message)
   
   # 在订单成交时
   message = self.notification_formatter.format_order_filled(
       order_info, fill_price, fill_time, symbol
   )
   await self.telegram_client.send_message(message)
   
   # 在订单取消时
   message = self.notification_formatter.format_order_cancelled(
       order_info, reason, symbol
   )
   await self.telegram_client.send_message(message)
   ```

#### 验证标准
- [ ] 通知格式清晰易读
- [ ] 包含所有关键信息
- [ ] 支持多种通知类型
- [ ] 通知发送及时准确

---

## 实施时间表

### 第1周：核心稳定性
- 周一-周二：任务 1.1 订单状态持久化
- 周三-周四：任务 1.2 部分成交处理
- 周五：任务 1.3 错误处理和重试机制

### 第2周：核心稳定性（续）
- 周一：任务 1.4 资金管理优化
- 周二-周三：任务 1.5 风险控制增强
- 周四-周五：测试和修复

### 第3周：功能优化
- 周一-周二：任务 2.1 订单修改功能
- 周三：任务 2.2 订单优先级系统
- 周四-周五：任务 2.3 动态策略调整

### 第4周：功能优化（续）
- 周一-周二：任务 2.4 性能监控和分析
- 周三-周四：测试和优化
- 周五：文档更新

### 第5周：用户体验优化（可选）
- 周一-周二：任务 3.1 订单管理API
- 周三：任务 3.2 增强通知系统
- 周四-周五：测试和文档

## 验收标准

### 第一阶段验收
- [ ] 程序重启后订单状态正确恢复
- [ ] 部分成交能正确处理
- [ ] 网络错误能自动恢复
- [ ] 资金管理不会导致保证金不足
- [ ] 风险控制能有效保护资金

### 第二阶段验收
- [ ] 订单修改功能正常工作
- [ ] 优先级系统能优化资源利用
- [ ] 动态策略能适应市场变化
- [ ] 性能监控数据准确可靠

### 第三阶段验收
- [ ] 管理API功能完整
- [ ] 通知系统清晰易用
- [ ] 用户体验良好

## 风险和注意事项

1. **测试环境**: 所有改动先在测试环境验证
2. **数据备份**: 实施前备份现有数据
3. **回滚计划**: 准备回滚方案
4. **监控告警**: 实施后密切监控系统
5. **文档更新**: 及时更新相关文档

## 总结

本优化方案按照优先级和依赖关系组织，分为三个阶段：

1. **第一阶段（必需）**: 确保系统稳定性和可靠性
2. **第二阶段（重要）**: 提升系统功能和性能
3. **第三阶段（可选）**: 改善用户体验

建议按照此方案逐步实施，确保每个阶段都经过充分测试后再进入下一阶段。