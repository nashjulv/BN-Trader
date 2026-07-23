"""
交易模型

定义交易记录相关的数据模型。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, Boolean
from core.database import Base


class Trade(Base):
    """交易记录模型"""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)  # 交易对
    side = Column(String(10), nullable=False)  # BUY/SELL
    quantity = Column(Float, nullable=False)  # 数量
    entry_price = Column(Float, nullable=False)  # 入场价格
    exit_price = Column(Float)  # 出场价格
    stop_loss = Column(Float)  # 止损价格
    take_profit = Column(Float)  # 止盈价格
    pnl = Column(Float, default=0.0)  # 盈亏金额
    pnl_ratio = Column(Float, default=0.0)  # 盈亏比例
    fee = Column(Float, default=0.0)  # 手续费
    scene = Column(String(20))  # 交易时的场景
    strategy = Column(String(50))  # 使用的策略
    status = Column(String(20), default="OPEN")  # OPEN/CLOSED
    is_auto = Column(Boolean, default=False)  # 是否自动交易
    opened_at = Column(DateTime, default=datetime.utcnow)  # 开仓时间
    closed_at = Column(DateTime)  # 平仓时间
    hold_time = Column(Integer, default=0)  # 持仓时间(秒)

    def __repr__(self):
        return f"<Trade({self.symbol} {self.side} {self.status})>"


class Order(Base):
    """订单记录模型"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer)  # 关联的交易ID
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False)  # MARKET/LIMIT/STOP
    quantity = Column(Float, nullable=False)
    price = Column(Float)  # 限价单价格
    stop_price = Column(Float)  # 止损触发价格
    filled_quantity = Column(Float, default=0.0)  # 已成交数量
    filled_price = Column(Float)  # 成交均价
    fee = Column(Float, default=0.0)
    status = Column(String(20), default="PENDING")  # PENDING/FILLED/CANCELLED
    binance_order_id = Column(String(50))  # 币安订单ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)
