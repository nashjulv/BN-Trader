"""
场景模型

定义行情场景识别相关的数据模型。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String
from core.database import Base


class SceneLog(Base):
    """场景识别记录模型"""
    __tablename__ = "scene_logs"

    id = Column(Integer, primary_key=True)
    scene_type = Column(String(20), nullable=False)  # 场景类型
    confidence = Column(Float, nullable=False)  # 置信度
    trend_strength = Column(Float)  # 趋势强度
    volatility = Column(Float)  # 波动率
    volume_change = Column(Float)  # 成交量变化
    price_position = Column(Float)  # 价格位置
    is_breakout = Column(Integer, default=0)  # 是否突破
    is_divergence = Column(Integer, default=0)  # 是否背离
    indicators = Column(String(2000))  # JSON格式的指标数据
    detected_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SceneLog({self.scene_type}: {self.confidence:.2f})>"


class KlineData(Base):
    """K线数据缓存"""
    __tablename__ = "kline_data"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    quote_volume = Column(Float)
    trade_count = Column(Integer)
    taker_buy_volume = Column(Float)
    taker_buy_quote_volume = Column(Float)

    def __repr__(self):
        return f"<KlineData({self.symbol} {self.timeframe} {self.open_time})>"
