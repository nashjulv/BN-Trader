"""
数据库管理模块

使用SQLAlchemy管理SQLite数据库，提供数据持久化功能。
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

from config import Config

# 创建引擎
engine = create_engine(
    Config.DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 模型基类
Base = declarative_base()


def get_db():
    """获取数据库会话（上下文管理器）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """初始化数据库，创建所有表"""
    # 导入所有模型以确保表被创建
    from models import capital, trade, risk, scene

    Base.metadata.create_all(bind=engine)
