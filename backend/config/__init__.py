"""CityFlow 配置包。

向后兼容：``from backend.config import settings`` 仍然可用。
新增：
- ``from backend.config.pool_config import pool_settings``
- ``from backend.config.hot_reload import ConfigHotReloader``
- ``from backend.config.manager import ConfigManager``
"""

from __future__ import annotations

from backend.config.hot_reload import (
    ConfigHotReloader,
    ConfigReloadError,
    ConfigRollbackError,
    ConfigSnapshot,
)
from backend.config.manager import ConfigManager, ConfigManagerError
from backend.config.pool_config import PoolSettings, pool_settings
from backend.config.settings import (
    DatabaseSettings,
    Environment,
    IntentLLMSettings,
    LLMSettings,
    RedisSettings,
    SecuritySettings,
    Settings,
    get_settings,
    settings,
)
from backend.config.validator import ConfigValidationError, ConfigValidator, ValidationResult

__all__ = [
    # hot_reload
    "ConfigHotReloader",
    # manager
    "ConfigManager",
    "ConfigManagerError",
    "ConfigReloadError",
    "ConfigRollbackError",
    "ConfigSnapshot",
    # validator
    "ConfigValidationError",
    "ConfigValidator",
    # 原 config.py 导出
    "DatabaseSettings",
    "Environment",
    "IntentLLMSettings",
    "LLMSettings",
    # pool_config
    "PoolSettings",
    "RedisSettings",
    "SecuritySettings",
    "Settings",
    "ValidationResult",
    "get_settings",
    "pool_settings",
    "settings",
]
