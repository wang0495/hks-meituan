"""CityFlow 深度健康检查包。

提供比基础 /health 更细粒度的健康状态探测：
- 系统资源检查（CPU、内存、磁盘）
- 依赖服务检查（数据库、Redis、LLM）
- 健康状态聚合与报告

核心类 DeepHealthCheck 封装了上述能力，
路由层通过 backend.routers.health 暴露 HTTP 端点。
"""

from __future__ import annotations

from backend.health.deep_check import DeepHealthCheck

__all__ = ["DeepHealthCheck"]
