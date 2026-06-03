"""CityFlow 数据库 ORM 模型。

对应 PostgreSQL 表：
    users, routes, route_steps, dialogues, user_preferences

使用 SQLAlchemy 2.0 mapped_column 风格。
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base

if TYPE_CHECKING:
    from datetime import datetime

# JSON 类型：PostgreSQL 用 JSONB，其他数据库（SQLite 等）用普通 JSON
_JSONCol = JSON().with_variant(JSONB(), "postgresql")

# ---------------------------------------------------------------------------
# 用户表
# ---------------------------------------------------------------------------


class User(Base):
    """用户。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    # 关系
    routes: Mapped[list[Route]] = relationship("Route", back_populates="user")
    preference_list: Mapped[list[UserPreference]] = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 路线表
# ---------------------------------------------------------------------------


class Route(Base):
    """规划路线。"""

    __tablename__ = "routes"
    __table_args__ = (
        Index("idx_routes_user_id", "user_id"),
        Index("idx_routes_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    route_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    narrative: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped[User | None] = relationship("User", back_populates="routes")
    steps: Mapped[list[RouteStep]] = relationship(
        "RouteStep",
        back_populates="route",
        order_by="RouteStep.step_index",
        cascade="all, delete-orphan",
    )
    dialogues: Mapped[list[Dialogue]] = relationship(
        "Dialogue", back_populates="route", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 路线步骤表
# ---------------------------------------------------------------------------


class RouteStep(Base):
    """路线中的单个步骤。"""

    __tablename__ = "route_steps"
    __table_args__ = (Index("idx_route_steps_route_id", "route_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    poi_id: Mapped[str] = mapped_column(String(50), nullable=False)
    poi_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    arrival_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    departure_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    travel_from_prev: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    route: Mapped[Route] = relationship("Route", back_populates="steps")


# ---------------------------------------------------------------------------
# 对话历史表
# ---------------------------------------------------------------------------


class Dialogue(Base):
    """对话消息。"""

    __tablename__ = "dialogues"
    __table_args__ = (Index("idx_dialogues_session_id", "session_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    route: Mapped[Route] = relationship("Route", back_populates="dialogues")


# ---------------------------------------------------------------------------
# 用户偏好表
# ---------------------------------------------------------------------------


class UserPreference(Base):
    """用户偏好设置（按类型存储）。"""

    __tablename__ = "user_preferences"
    __table_args__ = (
        Index("idx_user_preferences_user_id", "user_id"),
        UniqueConstraint("user_id", "preference_type", name="uq_user_pref_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    preference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    preference_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关系
    user: Mapped[User] = relationship("User", back_populates="preference_list")


# ---------------------------------------------------------------------------
# POI 兴趣点表
# ---------------------------------------------------------------------------


class POI(Base):
    """兴趣点（Point of Interest）。"""

    __tablename__ = "pois"
    __table_args__ = (
        Index("idx_pois_city", "city"),
        Index("idx_pois_category", "category"),
        Index("idx_pois_rating", "rating"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    avg_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    business_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[Any] = mapped_column(_JSONCol, default=list)
    queue_prone: Mapped[bool] = mapped_column(default=False)
    avg_stay_min: Mapped[int] = mapped_column(Integer, default=60)
    emotion_tags: Mapped[Any] = mapped_column(_JSONCol, default=dict)
    experience_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_elasticity: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_leverage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    spend_emotion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict[str, Any]:
        """将 POI 对象转换为字典（匹配 JSON 结构，不含 ugc_comments）。"""
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "category": self.category,
            "rating": self.rating,
            "avg_price": self.avg_price or 0,
            "lat": self.lat,
            "lng": self.lng,
            "business_hours": self.business_hours or "",
            "tags": self.tags or [],
            "queue_prone": self.queue_prone,
            "avg_stay_min": self.avg_stay_min,
            "emotion_tags": self.emotion_tags or {},
            "experience_value": self.experience_value,
            "price_elasticity": self.price_elasticity,
            "experience_leverage": self.experience_leverage,
            "spend_emotion": self.spend_emotion,
        }


# ---------------------------------------------------------------------------
# 审计日志表
# ---------------------------------------------------------------------------


class AuditLog(Base):
    """审计日志。"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_resource_type", "resource_type"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_user_action", "user_id", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
