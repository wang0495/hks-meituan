"""CityFlow 配置变更监视器。

监视 Settings 中的关键字段，当值发生变化时触发已注册的回调。
与 config_hot_reload 配合使用：hot_reload 负责文件监听，
config_watcher 负责语义层面的配置变更检测与通知。

典型用法：
    watcher = ConfigWatcher()
    watcher.watch("log_level", on_log_level_change)
    watcher.watch("rate_limit", on_rate_limit_change)

    # 在定时任务或热更新回调中调用
    await watcher.check_changes()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from backend.config import Settings, get_settings

logger = logging.getLogger(__name__)

# 回调类型：接收 (key, old_value, new_value)
ConfigChangeCallback = Callable[[str, Any, Any], Coroutine[Any, Any, None]]


@dataclass(slots=True)
class ConfigDiff:
    """单条配置变更记录。"""

    key: str
    old_value: Any
    new_value: Any


class ConfigWatcher:
    """配置变更监视器。

    通过轮询 Settings 实例检测字段变化，
    并调用已注册的异步回调通知下游。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._watchers: dict[str, ConfigChangeCallback] = {}
        self._snapshot: dict[str, Any] = {}
        self._change_log: list[ConfigDiff] = []
        self._max_log_size: int = 100

        # 初始化快照
        self._take_snapshot()

    # ------------------------------------------------------------------
    # 监视注册
    # ------------------------------------------------------------------

    def watch(self, key: str, callback: ConfigChangeCallback) -> None:
        """注册配置变更回调。

        Args:
            key: 配置字段名（支持点分路径，如 "security.rate_limit_per_minute"）。
            callback: 异步回调，签名 async def cb(key, old_value, new_value)。
        """
        self._watchers[key] = callback
        logger.debug("已注册配置监视: %s", key)

    def unwatch(self, key: str) -> None:
        """取消监视。"""
        self._watchers.pop(key, None)

    @property
    def watched_keys(self) -> list[str]:
        """当前监视的配置键列表。"""
        return list(self._watchers.keys())

    # ------------------------------------------------------------------
    # 变更检测
    # ------------------------------------------------------------------

    async def check_changes(self) -> list[ConfigDiff]:
        """检查配置变更并触发回调。

        Returns:
            本次检测到的变更列表。
        """
        new_snapshot = self._read_current_values()
        diffs: list[ConfigDiff] = []

        for key in self._watchers:
            old_val = self._snapshot.get(key)
            new_val = new_snapshot.get(key)

            if old_val != new_val:
                diff = ConfigDiff(key=key, old_value=old_val, new_value=new_val)
                diffs.append(diff)

                logger.info("配置变更检测: %s  %r -> %r", key, old_val, new_val)

                # 调用回调
                callback = self._watchers[key]
                try:
                    await callback(key, old_val, new_val)
                except Exception:
                    logger.exception("配置变更回调执行失败: %s", key)

        # 更新快照
        self._snapshot = new_snapshot

        # 记录变更日志
        self._change_log.extend(diffs)
        self._trim_change_log()

        return diffs

    # ------------------------------------------------------------------
    # 变更日志
    # ------------------------------------------------------------------

    @property
    def change_log(self) -> list[ConfigDiff]:
        """获取最近的变更日志。"""
        return list(self._change_log)

    def clear_change_log(self) -> None:
        """清空变更日志。"""
        self._change_log.clear()

    # ------------------------------------------------------------------
    # 快照管理
    # ------------------------------------------------------------------

    def refresh_snapshot(self) -> None:
        """强制刷新快照（不触发回调）。"""
        self._take_snapshot()
        logger.debug("配置快照已刷新")

    def _take_snapshot(self) -> None:
        """读取当前配置值作为快照。"""
        self._snapshot = self._read_current_values()

    def _read_current_values(self) -> dict[str, Any]:
        """从 Settings 实例读取所有被监视字段的当前值。"""
        values: dict[str, Any] = {}
        for key in self._watchers:
            values[key] = self._resolve_key(key)
        return values

    def _resolve_key(self, key: str) -> Any:
        """按点分路径解析配置值。

        例: "security.rate_limit_per_minute" -> settings.security.rate_limit_per_minute
        """
        obj: Any = self._settings
        for part in key.split("."):
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                logger.warning("配置路径不存在: %s (停在 %s)", key, part)
                return None
        return obj

    def _trim_change_log(self) -> None:
        """保持变更日志在最大长度以内。"""
        if len(self._change_log) > self._max_log_size:
            self._change_log = self._change_log[-self._max_log_size :]


# ---------------------------------------------------------------------------
# 内置回调工厂
# ---------------------------------------------------------------------------


async def log_level_change_callback(key: str, old_value: Any, new_value: Any) -> None:
    """日志级别变更回调：动态调整 root logger 级别。"""
    root_logger = logging.getLogger()
    try:
        level = logging.getLevelName(str(new_value).upper())
        if isinstance(level, int):
            root_logger.setLevel(level)
            logger.info("日志级别已动态调整: %s -> %s", old_value, new_value)
        else:
            logger.warning("无效的日志级别: %s", new_value)
    except Exception:
        logger.exception("调整日志级别失败")


async def rate_limit_change_callback(key: str, old_value: Any, new_value: Any) -> None:
    """限流配置变更回调：记录变更（实际限流组件需自行监听）。"""
    logger.info(
        "限流配置已变更: %s  %r -> %r（需重启限流中间件生效）",
        key,
        old_value,
        new_value,
    )


# ---------------------------------------------------------------------------
# 便捷初始化
# ---------------------------------------------------------------------------


def create_default_watcher(settings: Settings | None = None) -> ConfigWatcher:
    """创建带有默认监视项的 ConfigWatcher。

    默认监视:
    - log_level -> 动态调整日志级别
    - security.rate_limit_per_minute -> 记录变更

    Args:
        settings: Settings 实例，为 None 时使用全局单例。

    Returns:
        配置好的 ConfigWatcher 实例。
    """
    watcher = ConfigWatcher(settings=settings)
    watcher.watch("log_level", log_level_change_callback)
    watcher.watch("security.rate_limit_per_minute", rate_limit_change_callback)
    return watcher
