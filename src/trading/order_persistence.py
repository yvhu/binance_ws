"""
订单持久化管理
实现订单状态的持久化存储，确保程序重启后订单信息不丢失
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


class OrderPersistence:
    """订单持久化管理类"""
    
    def __init__(self, db_path: str = "data/orders.db"):
        """
        初始化订单持久化管理
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        try:
            # 确保数据库目录存在
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建订单表
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
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_symbol_status 
                ON orders(symbol, status)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status 
                ON orders(status)
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def save_order(self, order_id: int, symbol: str, order_info: Dict):
        """
        保存订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            order_info: 订单信息字典
        """
        try:
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
                order_info.get('side', 'UNKNOWN'),
                order_info.get('order_price', 0),
                order_info.get('quantity', 0),
                order_info.get('timestamp', 0),
                'PENDING',
                json.dumps(order_info, ensure_ascii=False),
                now,
                now
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving order {order_id}: {e}")
            raise
    
    def load_pending_orders(self) -> Dict[str, Dict]:
        """
        加载所有未完成订单
        
        Returns:
            字典: {symbol: {order_id: order_info}}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT order_id, symbol, order_info 
                FROM orders 
                WHERE status = 'PENDING'
                ORDER BY timestamp DESC
            ''')
            
            orders = {}
            for row in cursor.fetchall():
                order_id, symbol, order_info_json = row
                try:
                    order_info = json.loads(order_info_json)
                    if symbol not in orders:
                        orders[symbol] = {}
                    orders[symbol][order_id] = order_info
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding order info for {order_id}: {e}")
            
            conn.close()
            
            return orders
            
        except Exception as e:
            logger.error(f"Error loading pending orders: {e}")
            return {}
    
    def update_order_status(self, order_id: int, status: str):
        """
        更新订单状态
        
        Args:
            order_id: 订单ID
            status: 订单状态 (PENDING, FILLED, CANCELLED, UNKNOWN)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute('''
                UPDATE orders 
                SET status = ?, updated_at = ?
                WHERE order_id = ?
            ''', (status, now, order_id))
            
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating order status for {order_id}: {e}")
            raise
    
    def delete_order(self, order_id: int):
        """
        删除订单
        
        Args:
            order_id: 订单ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM orders WHERE order_id = ?', (order_id,))
            
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            
        except Exception as e:
            logger.error(f"Error deleting order {order_id}: {e}")
            raise
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            订单信息字典，如果不存在返回None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT order_id, symbol, side, order_price, quantity, 
                       timestamp, status, order_info, created_at, updated_at
                FROM orders 
                WHERE order_id = ?
            ''', (order_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'order_id': row[0],
                    'symbol': row[1],
                    'side': row[2],
                    'order_price': row[3],
                    'quantity': row[4],
                    'timestamp': row[5],
                    'status': row[6],
                    'order_info': json.loads(row[7]),
                    'created_at': row[8],
                    'updated_at': row[9]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None
    
    def get_orders_by_symbol(self, symbol: str, status: Optional[str] = None) -> List[Dict]:
        """
        获取指定交易对的订单
        
        Args:
            symbol: 交易对
            status: 订单状态（可选）
            
        Returns:
            订单列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if status:
                cursor.execute('''
                    SELECT order_id, symbol, side, order_price, quantity, 
                           timestamp, status, order_info, created_at, updated_at
                    FROM orders 
                    WHERE symbol = ? AND status = ?
                    ORDER BY timestamp DESC
                ''', (symbol, status))
            else:
                cursor.execute('''
                    SELECT order_id, symbol, side, order_price, quantity, 
                           timestamp, status, order_info, created_at, updated_at
                    FROM orders 
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                ''', (symbol,))
            
            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'order_id': row[0],
                    'symbol': row[1],
                    'side': row[2],
                    'order_price': row[3],
                    'quantity': row[4],
                    'timestamp': row[5],
                    'status': row[6],
                    'order_info': json.loads(row[7]),
                    'created_at': row[8],
                    'updated_at': row[9]
                })
            
            conn.close()
            
            return orders
            
        except Exception as e:
            logger.error(f"Error getting orders for {symbol}: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """
        获取订单统计信息
        
        Returns:
            统计信息字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 总订单数
            cursor.execute('SELECT COUNT(*) FROM orders')
            total_orders = cursor.fetchone()[0]
            
            # 各状态订单数
            cursor.execute('''
                SELECT status, COUNT(*) 
                FROM orders 
                GROUP BY status
            ''')
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 各交易对订单数
            cursor.execute('''
                SELECT symbol, COUNT(*) 
                FROM orders 
                GROUP BY symbol
                ORDER BY COUNT(*) DESC
            ''')
            symbol_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_orders': total_orders,
                'status_counts': status_counts,
                'symbol_counts': symbol_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def cleanup_old_orders(self, days: int = 7):
        """
        清理旧订单（已完成或取消的订单）
        
        Args:
            days: 保留天数
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 删除指定天数前的已完成或取消订单
            cursor.execute('''
                DELETE FROM orders 
                WHERE status IN ('FILLED', 'CANCELLED', 'UNKNOWN')
                AND datetime(updated_at) < datetime('now', '-' || ? || ' days')
            ''', (days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error cleaning up old orders: {e}")