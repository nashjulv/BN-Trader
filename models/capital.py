"""
资金模型

定义资金池相关的数据模型。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String
from core.database import Base


class CapitalPool(Base):
    """资金池模型"""
    __tablename__ = "capital_pool"

    id = Column(Integer, primary_key=True)
    total = Column(Float, nullable=False, default=0.0)  # 总资金
    available = Column(Float, nullable=False, default=0.0)  # 可用资金
    locked = Column(Float, nullable=False, default=0.0)  # 冻结资金
    margin = Column(Float, nullable=False, default=0.0)  # 持仓保证金
    reserve = Column(Float, nullable=False, default=0.0)  # 风险准备金
    daily_pnl = Column(Float, default=0.0)  # 今日盈亏
    daily_pnl_ratio = Column(Float, default=0.0)  # 今日盈亏比例
    total_trades = Column(Integer, default=0)  # 总交易次数
    win_count = Column(Integer, default=0)  # 盈利次数
    loss_count = Column(Integer, default=0)  # 亏损次数
    consecutive_loss = Column(Integer, default=0)  # 连续亏损次数
    max_drawdown = Column(Float, default=0.0)  # 最大回撤
    current_drawdown = Column(Float, default=0.0)  # 当前回撤
    peak_capital = Column(Float, default=0.0)  # 资金峰值
    updated_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CapitalPool(total={self.total}, available={self.available})>"


class CapitalHistory(Base):
    """资金变动历史"""
    __tablename__ = "capital_history"

    id = Column(Integer, primary_key=True)
    type = Column(String(20), nullable=False)  # DEPOSIT, WITHDRAW, TRADE, FEE
    amount = Column(Float, nullable=False)  # 变动金额
    balance_before = Column(Float, nullable=False)  # 变动前余额
    balance_after = Column(Float, nullable=False)  # 变动后余额
    description = Column(String(200))  # 描述
    created_at = Column(DateTime, default=datetime.utcnow)
