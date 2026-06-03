"""CityFlow 数据库引擎与会话管理。

使用 SQLAlchemy 2.0 异步引擎 + AsyncSession。
数据库连接参数从 backend.config.settings.database 读取。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

# ---------------------------------------------------------------------------
# 异步引擎
# ---------------------------------------------------------------------------

_db = settings.database
DATABASE_URL = (
    f"postgresql+asyncpg://{_db.user}:{_db.password}" f"@{_db.host}:{_db.port}/{_db.database}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# ---------------------------------------------------------------------------
# 会话工厂
# ---------------------------------------------------------------------------

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# 声明式基类
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    pass


# ---------------------------------------------------------------------------
# FastAPI 依赖注入
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：为每个请求提供一个 AsyncSession。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
