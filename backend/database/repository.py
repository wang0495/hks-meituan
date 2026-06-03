"""CityFlow 数据访问层（Repository 模式）。

所有方法使用 AsyncSession，配合 FastAPI 的依赖注入使用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.database.models import Dialogue, Route, RouteStep, User, UserPreference

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# 用户 Repository
# ---------------------------------------------------------------------------


class UserRepository:
    """用户数据访问。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, preferences: dict | None = None) -> User:
        """创建用户，返回 User 对象。"""
        user = User(preferences=preferences or {})
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        """按 ID 获取用户。"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def update_preferences(self, user_id: uuid.UUID, preferences: dict) -> User | None:
        """更新用户偏好。"""
        user = await self.get(user_id)
        if user is not None:
            user.preferences = preferences
            await self.db.flush()
            await self.db.refresh(user)
        return user


# ---------------------------------------------------------------------------
# 路线 Repository
# ---------------------------------------------------------------------------


class RouteRepository:
    """路线数据访问。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_input: str,
        route_data: dict,
        user_id: uuid.UUID | None = None,
        narrative: dict | None = None,
    ) -> Route:
        """创建路线。"""
        route = Route(
            user_id=user_id,
            user_input=user_input,
            route_data=route_data,
            narrative=narrative,
        )
        self.db.add(route)
        await self.db.flush()
        await self.db.refresh(route)
        return route

    async def get(self, route_id: uuid.UUID) -> Route | None:
        """按 ID 获取路线（含步骤和对话）。"""
        result = await self.db.execute(select(Route).where(Route.id == route_id))
        return result.scalar_one_or_none()

    async def get_by_user(
        self, user_id: uuid.UUID, limit: int = 10, offset: int = 0
    ) -> Sequence[Route]:
        """获取用户的路线列表（按创建时间倒序）。"""
        result = await self.db.execute(
            select(Route)
            .where(Route.user_id == user_id)
            .order_by(Route.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def update(
        self, route_id: uuid.UUID, route_data: dict, narrative: dict | None = None
    ) -> Route | None:
        """更新路线数据。"""
        route = await self.get(route_id)
        if route is not None:
            route.route_data = route_data
            if narrative is not None:
                route.narrative = narrative
            await self.db.flush()
            await self.db.refresh(route)
        return route

    async def update_status(self, route_id: uuid.UUID, status: str) -> Route | None:
        """更新路线状态（active/archived/deleted）。"""
        route = await self.get(route_id)
        if route is not None:
            route.status = status
            await self.db.flush()
            await self.db.refresh(route)
        return route

    async def delete(self, route_id: uuid.UUID) -> bool:
        """删除路线（级联删除步骤和对话）。"""
        route = await self.get(route_id)
        if route is not None:
            await self.db.delete(route)
            await self.db.flush()
            return True
        return False


# ---------------------------------------------------------------------------
# 路线步骤 Repository
# ---------------------------------------------------------------------------


class RouteStepRepository:
    """路线步骤数据访问。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def bulk_create(self, route_id: uuid.UUID, steps: list[dict]) -> list[RouteStep]:
        """批量创建路线步骤。

        steps 中每个 dict 应包含：
            step_index, poi_id, poi_name, arrival_time,
            departure_time, travel_from_prev
        """
        objects = [RouteStep(route_id=route_id, **step) for step in steps]
        self.db.add_all(objects)
        await self.db.flush()
        for obj in objects:
            await self.db.refresh(obj)
        return objects

    async def get_by_route(self, route_id: uuid.UUID) -> Sequence[RouteStep]:
        """获取路线的所有步骤（按 step_index 排序）。"""
        result = await self.db.execute(
            select(RouteStep).where(RouteStep.route_id == route_id).order_by(RouteStep.step_index)
        )
        return result.scalars().all()

    async def replace_all(self, route_id: uuid.UUID, steps: list[dict]) -> list[RouteStep]:
        """替换路线的全部步骤（先删后插）。"""
        old_steps = await self.get_by_route(route_id)
        for s in old_steps:
            await self.db.delete(s)
        await self.db.flush()
        return await self.bulk_create(route_id, steps)


# ---------------------------------------------------------------------------
# 对话 Repository
# ---------------------------------------------------------------------------


class DialogueRepository:
    """对话数据访问。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add_message(
        self,
        route_id: uuid.UUID,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> Dialogue:
        """添加一条对话消息。"""
        dialogue = Dialogue(
            route_id=route_id,
            session_id=session_id,
            role=role,
            content=content,
            metadata_=metadata or {},
        )
        self.db.add(dialogue)
        await self.db.flush()
        await self.db.refresh(dialogue)
        return dialogue

    async def get_session_messages(self, session_id: str, limit: int = 100) -> Sequence[Dialogue]:
        """获取会话的全部消息（按时间排序）。"""
        result = await self.db.execute(
            select(Dialogue)
            .where(Dialogue.session_id == session_id)
            .order_by(Dialogue.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_route_dialogues(self, route_id: uuid.UUID) -> Sequence[Dialogue]:
        """获取路线关联的所有对话。"""
        result = await self.db.execute(
            select(Dialogue).where(Dialogue.route_id == route_id).order_by(Dialogue.created_at)
        )
        return result.scalars().all()


# ---------------------------------------------------------------------------
# 用户偏好 Repository
# ---------------------------------------------------------------------------


class UserPreferenceRepository:
    """用户偏好数据访问。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(
        self,
        user_id: uuid.UUID,
        preference_type: str,
        preference_value: dict,
    ) -> UserPreference:
        """插入或更新用户偏好。"""
        result = await self.db.execute(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.preference_type == preference_type,
            )
        )
        pref = result.scalar_one_or_none()

        if pref is not None:
            pref.preference_value = preference_value
        else:
            pref = UserPreference(
                user_id=user_id,
                preference_type=preference_type,
                preference_value=preference_value,
            )
            self.db.add(pref)

        await self.db.flush()
        await self.db.refresh(pref)
        return pref

    async def get(self, user_id: uuid.UUID, preference_type: str) -> UserPreference | None:
        """获取指定类型的偏好。"""
        result = await self.db.execute(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.preference_type == preference_type,
            )
        )
        return result.scalar_one_or_none()

    async def get_all(self, user_id: uuid.UUID) -> Sequence[UserPreference]:
        """获取用户的全部偏好。"""
        result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        return result.scalars().all()
