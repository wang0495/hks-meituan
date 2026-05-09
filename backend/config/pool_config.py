"""CityFlow 连接池配置。

集中管理数据库、HTTP、Redis 连接池参数。
通过环境变量覆盖（前缀 ``POOL_``），也可在 .env 文件中设置。

用法::

    from backend.config.pool_config import pool_settings

    pool_settings.db_pool_size          # 10
    pool_settings.http_max_connections  # 100
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PoolSettings(BaseSettings):
    """连接池配置。

    所有字段均可通过 ``POOL_`` 前缀的环境变量覆盖，
    例如 ``POOL_DB_POOL_SIZE=20``。
    """

    model_config = SettingsConfigDict(
        env_prefix="POOL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ---- 数据库连接池 ----
    db_pool_size: int = Field(
        default=10,
        description="核心连接数（SQLAlchemy pool_size）",
    )
    db_max_overflow: int = Field(
        default=20,
        description="超出 pool_size 后的最大临时连接数",
    )
    db_pool_timeout: int = Field(
        default=30,
        description="获取连接的超时秒数",
    )
    db_pool_recycle: int = Field(
        default=3600,
        description="连接回收周期（秒），避免数据库端超时断开",
    )
    db_pool_pre_ping: bool = Field(
        default=True,
        description="使用前检测连接是否存活",
    )

    # ---- HTTP 连接池 ----
    http_max_connections: int = Field(
        default=100,
        description="最大并发连接数",
    )
    http_max_keepalive: int = Field(
        default=20,
        description="最大 keep-alive 连接数",
    )
    http_timeout: float = Field(
        default=30.0,
        description="默认请求超时（秒）",
    )

    # ---- Redis 连接池 ----
    redis_max_connections: int = Field(
        default=50,
        description="Redis 连接池最大连接数",
    )
    redis_socket_timeout: float = Field(
        default=3.0,
        description="Redis socket 超时（秒）",
    )
    redis_socket_connect_timeout: float = Field(
        default=3.0,
        description="Redis 连接超时（秒）",
    )

    # ---- 监控 ----
    utilization_warn_threshold: float = Field(
        default=0.8,
        description="连接池使用率告警阈值（0.0 ~ 1.0）",
    )
    health_check_interval: int = Field(
        default=60,
        description="健康检查间隔（秒）",
    )


# 全局单例
pool_settings = PoolSettings()
