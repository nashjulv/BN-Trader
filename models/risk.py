"""
风控模型

定义风控记录相关的数据模型。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, Boolean
from core.database import Base


class RiskLog(Base):
    """风控记录模型"""
    __tablename__ = "risk_logs"

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)  # 风控类型
    level = Column(String(20), nullable=False)  # WARNING/CRITICAL/STOP
    message = Column(String(500), nullable=False)  # 风控信息
    detail = Column(String(1000))  # 详细信息
    triggered_value = Column(Float)  # 触发值
    limit_value = Column(Float)  # 限制值
    is_resolved = Column(Boolean, default=False)  # 是否已解决
    resolved_at = Column(DateTime)  # 解决时间
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<RiskLog({self.type}: {self.level})>"


class ReviewRecord(Base):
    """复盘记录模型"""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    trigger_reason = Column(String(200), nullable=False)  # 触发原因
    trigger_type = Column(String(50), nullable=False)  # 触发类型
    mistake_analysis = Column(String(2000))  # 错误分析
    improvement_plan = Column(String(2000))  # 改进计划
    emotion_state = Column(String(50))  # 情绪状态
    market_analysis = Column(String(2000))  # 市场分析
    lesson_learned = Column(String(1000))  # 经验教训
    is_qualified = Column(Boolean, default=False)  # 复盘是否合格
    approved_at = Column(DateTime)  # 批准时间
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ReviewRecord({self.trigger_reason})>"
