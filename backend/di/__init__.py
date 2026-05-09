"""CityFlow 依赖注入模块。

提供轻量级 DI 容器，用于集中管理服务实例与工厂函数。
"""

from __future__ import annotations

from backend.di.container import DIContainer, get_container, inject
from backend.di.registry import register_services

__all__ = [
    "DIContainer",
    "get_container",
    "inject",
    "register_services",
]
