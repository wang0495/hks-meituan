"""数据库测试 fixtures。

使用 aiosqlite 内存数据库，无需真实 PostgreSQL。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.base import Base
from backend.database.models import Route, User
from backend.database.poi_repository import POIRepository
from backend.database.repository import (
    DialogueRepository,
    RouteRepository,
    RouteStepRepository,
    UserPreferenceRepository,
    UserRepository,
)


@pytest.fixture
async def db_engine():
    """创建内存 SQLite 异步引擎。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """每个测试一个独立事务，测试结束回滚。"""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def user_repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


@pytest.fixture
async def route_repo(db_session: AsyncSession) -> RouteRepository:
    return RouteRepository(db_session)


@pytest.fixture
async def step_repo(db_session: AsyncSession) -> RouteStepRepository:
    return RouteStepRepository(db_session)


@pytest.fixture
async def dialogue_repo(db_session: AsyncSession) -> DialogueRepository:
    return DialogueRepository(db_session)


@pytest.fixture
async def pref_repo(db_session: AsyncSession) -> UserPreferenceRepository:
    return UserPreferenceRepository(db_session)


@pytest.fixture
async def poi_repo(db_session: AsyncSession) -> POIRepository:
    return POIRepository(db_session)


# ---------------------------------------------------------------------------
# 预制数据 fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sample_user(user_repo: UserRepository) -> User:
    """创建一个测试用户。"""
    return await user_repo.create(preferences={"pace": "balanced"})


@pytest.fixture
async def sample_route(route_repo: RouteRepository, sample_user: User) -> Route:
    """创建一条测试路线。"""
    return await route_repo.create(
        user_input="周末想一个人安静走走",
        route_data={
            "route": [
                {"poi": {"id": "poi_001", "name": "故宫"}, "arrival_time": "09:00"},
            ],
            "total_cost": {"time_min": 180},
        },
        user_id=sample_user.id,
        narrative={
            "opening": "出发吧",
            "steps": ["故宫值得一看"],
            "closing": "愉快的一天",
        },
    )
