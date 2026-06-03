"""CityFlow 数据库模块。"""

from __future__ import annotations

from backend.database.base import async_session_factory, engine, get_db
from backend.database.models import (
    POI,
    AuditLog,
    Base,
    Dialogue,
    Route,
    RouteStep,
    User,
    UserPreference,
)
from backend.database.poi_repository import POIRepository
from backend.database.pool import DatabasePool, PoolStats, get_database_pool
from backend.database.repository import DialogueRepository, RouteRepository, UserRepository

__all__ = [
    "POI",
    "AuditLog",
    "Base",
    "DatabasePool",
    "Dialogue",
    "DialogueRepository",
    "POIRepository",
    "PoolStats",
    "Route",
    "RouteRepository",
    "RouteStep",
    "User",
    "UserPreference",
    "UserRepository",
    "async_session_factory",
    "engine",
    "get_database_pool",
    "get_db",
]
