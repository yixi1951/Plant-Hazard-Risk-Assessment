"""数据库初始化与会话管理。"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL

logger = logging.getLogger("zhinong.db")


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """创建所有表。"""
    import app.models  # noqa: F401 — 确保所有模型被导入
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created (url=%s)", DATABASE_URL)


def get_session() -> Session:
    return SessionLocal()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """上下文管理器方式获取 session，自动提交/回滚。"""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
