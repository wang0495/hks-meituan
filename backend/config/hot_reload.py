"""CityFlow 配置热更新。

基于 watchdog 监听配置文件变更，支持：
- YAML / JSON 配置文件监听
- 变更回调通知（同步 + 异步）
- 防抖处理（避免重复触发）
- 配置版本历史与回滚

用法::

    from backend.config.hot_reload import ConfigHotReloader

    reloader = ConfigHotReloader(config_dir="config")
    reloader.start()

    async def on_change(config: dict) -> None:
        logger.info("配置已更新: %s", config)

    reloader.watch("app", on_change)

    # 回滚到上一版本
    reloader.rollback("app")

    reloader.stop()
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Coroutine

import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

# 配置变更回调类型：接受 config dict，可为同步或异步
ConfigCallback = Callable[[dict[str, Any]], Any]
AsyncConfigCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class ConfigReloadError(CityFlowException):
    """配置重载失败。"""

    def __init__(
        self,
        message: str = "配置重载失败",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            details=details,
        )


class ConfigRollbackError(CityFlowException):
    """配置回滚失败。"""

    def __init__(
        self,
        message: str = "配置回滚失败",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 版本快照
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """配置版本快照。"""

    config: dict[str, Any]
    timestamp: float
    source: str  # 文件路径

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "timestamp": self.timestamp,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# 文件事件处理器（内部）
# ---------------------------------------------------------------------------

# 支持的配置文件后缀
_CONFIG_EXTENSIONS = frozenset({".yaml", ".yml", ".json"})


class _ConfigFileHandler(FileSystemEventHandler):
    """watchdog 文件事件处理器。

    检测配置文件变更后触发去抖回调。
    """

    def __init__(
        self,
        on_change: Callable[[str], None],
        debounce_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        self._on_change = on_change
        self._debounce_seconds = debounce_seconds
        self._last_trigger: dict[str, float] = {}

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = str(event.src_path)
        if not any(src.endswith(ext) for ext in _CONFIG_EXTENSIONS):
            return

        # 防抖：同一文件短时间内只触发一次
        now = time.monotonic()
        last = self._last_trigger.get(src, 0.0)
        if now - last < self._debounce_seconds:
            logger.debug("防抖跳过: %s (间隔 %.2fs)", src, now - last)
            return
        self._last_trigger[src] = now

        logger.info("检测到配置文件变更: %s", src)
        self._on_change(src)

    def on_created(self, event: FileSystemEvent) -> None:
        """新增文件也视为变更。"""
        self.on_modified(event)


# ---------------------------------------------------------------------------
# 配置热更新器
# ---------------------------------------------------------------------------


class ConfigHotReloader:
    """配置热更新器。

    监听指定目录下的 YAML / JSON 配置文件，
    变更时自动重载并通知所有注册的观察者。

    Args:
        config_dir: 配置文件目录路径。
        max_history: 每个配置保留的历史版本数（用于回滚）。
        debounce_seconds: 防抖间隔（秒）。
    """

    def __init__(
        self,
        config_dir: str | Path = "config",
        max_history: int = 10,
        debounce_seconds: float = 0.5,
    ) -> None:
        self._config_dir = Path(config_dir)
        self._max_history = max_history
        self._debounce_seconds = debounce_seconds

        self._observer = Observer()
        self._running = False

        # 配置名 -> 当前配置
        self._configs: dict[str, dict[str, Any]] = {}
        # 配置名 -> 版本历史（最近 N 个快照）
        self._history: dict[str, deque[ConfigSnapshot]] = defaultdict(
            lambda: deque(maxlen=max_history)
        )
        # 配置名 -> 回调列表
        self._watchers: dict[str, list[ConfigCallback]] = defaultdict(list)

        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    # ---- 生命周期 ----

    def start(self) -> None:
        """启动文件监听。

        Raises:
            RuntimeError: 目录不存在时抛出。
        """
        if self._running:
            logger.warning("ConfigHotReloader 已在运行")
            return

        if not self._config_dir.is_dir():
            raise RuntimeError(f"配置目录不存在: {self._config_dir}")

        handler = _ConfigFileHandler(
            on_change=self._handle_file_change,
            debounce_seconds=self._debounce_seconds,
        )
        self._observer.schedule(handler, str(self._config_dir), recursive=False)
        self._observer.start()
        self._running = True

        # 尝试获取当前事件循环（用于跨线程调度异步回调）
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

        logger.info("配置热更新已启动，监听目录: %s", self._config_dir)

    def stop(self) -> None:
        """停止文件监听并等待线程退出。"""
        if not self._running:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._running = False
        logger.info("配置热更新已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- 观察者注册 ----

    def watch(
        self,
        config_name: str,
        callback: ConfigCallback | AsyncConfigCallback,
    ) -> None:
        """注册配置变更回调。

        Args:
            config_name: 配置文件名（不含扩展名）。
            callback: 同步或异步回调函数，接收 ``dict[str, Any]`` 参数。
        """
        self._watchers[config_name].append(callback)
        logger.debug("注册观察者: %s -> %s", config_name, callback.__qualname__)

    def unwatch(self, config_name: str, callback: ConfigCallback) -> None:
        """移除指定回调。"""
        try:
            self._watchers[config_name].remove(callback)
        except ValueError:
            logger.warning("尝试移除未注册的回调: %s", callback.__qualname__)

    # ---- 配置读取 ----

    def get(self, config_name: str, key: str | None = None) -> Any:
        """获取当前配置值。

        Args:
            config_name: 配置名。
            key: 可选的键路径（点分隔，如 ``"database.host"``）。
                 为 None 时返回整个配置。

        Returns:
            配置值或 None。
        """
        config = self._configs.get(config_name)
        if config is None:
            return None
        if key is None:
            return config

        # 支持点分隔的嵌套键
        parts = key.split(".")
        current: Any = config
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def get_all(self) -> dict[str, dict[str, Any]]:
        """获取所有已加载的配置（深拷贝）。"""
        return copy.deepcopy(self._configs)

    # ---- 版本历史与回滚 ----

    def get_history(self, config_name: str) -> list[ConfigSnapshot]:
        """获取指定配置的版本历史。"""
        return list(self._history.get(config_name, []))

    def rollback(self, config_name: str, steps: int = 1) -> dict[str, Any]:
        """回滚配置到历史版本。

        Args:
            config_name: 配置名。
            steps: 回滚步数（1 = 上一版本）。

        Returns:
            回滚后的配置。

        Raises:
            ConfigRollbackError: 没有可回滚的版本时抛出。
        """
        history = self._history.get(config_name)
        if not history or len(history) < steps:
            raise ConfigRollbackError(
                message=f"配置 {config_name} 没有足够的历史版本可回滚",
                details={
                    "config_name": config_name,
                    "requested_steps": steps,
                    "available_versions": len(history) if history else 0,
                },
            )

        # history[-1] 是最近一次保存的旧版本，history[-steps] 是目标版本
        target = history[-steps]
        rolled_back = copy.deepcopy(target.config)

        # 截断历史：回滚后，目标版本及之后的快照已无意义
        with self._lock:
            self._configs[config_name] = rolled_back
            for _ in range(steps):
                history.pop()

        logger.info(
            "配置已回滚: %s (步数=%d, 来源=%s)",
            config_name,
            steps,
            target.source,
        )

        # 通知观察者
        self._notify_watchers(config_name, rolled_back)

        return rolled_back

    # ---- 手动重载 ----

    def reload(self, config_name: str) -> dict[str, Any]:
        """手动触发单个配置重载。

        Args:
            config_name: 配置名。

        Returns:
            重载后的配置。

        Raises:
            ConfigReloadError: 文件不存在或解析失败时抛出。
        """
        file_path = self._find_config_file(config_name)
        if file_path is None:
            raise ConfigReloadError(
                message=f"找不到配置文件: {config_name}",
                details={"config_name": config_name, "dir": str(self._config_dir)},
            )
        return self._load_and_notify(config_name, str(file_path))

    def reload_all(self) -> dict[str, dict[str, Any]]:
        """手动触发所有配置重载。"""
        results: dict[str, dict[str, Any]] = {}
        for config_file in self._iter_config_files():
            name = config_file.stem
            results[name] = self._load_and_notify(name, str(config_file))
        return results

    # ---- 内部方法 ----

    def _find_config_file(self, config_name: str) -> Path | None:
        """查找配置文件。"""
        for ext in _CONFIG_EXTENSIONS:
            candidate = self._config_dir / f"{config_name}{ext}"
            if candidate.is_file():
                return candidate
        return None

    def _iter_config_files(self) -> list[Path]:
        """列出所有配置文件。"""
        files: list[Path] = []
        for ext in _CONFIG_EXTENSIONS:
            files.extend(self._config_dir.glob(f"*{ext}"))
        return sorted(files)

    def _handle_file_change(self, file_path: str) -> None:
        """文件变更回调（同步，在 watchdog 线程中调用）。"""
        name = Path(file_path).stem
        try:
            self._load_and_notify(name, file_path)
        except Exception:
            logger.exception("处理配置变更失败: %s", file_path)

    def _load_and_notify(self, config_name: str, file_path: str) -> dict[str, Any]:
        """加载配置并通知观察者。"""
        config = self._load_config_file(file_path)

        # 保存当前版本到历史
        with self._lock:
            if config_name in self._configs:
                old = self._configs[config_name]
                snapshot = ConfigSnapshot(
                    config=copy.deepcopy(old),
                    timestamp=time.time(),
                    source=file_path,
                )
                self._history[config_name].append(snapshot)

            self._configs[config_name] = config

        logger.info("配置已重载: %s (%s)", config_name, file_path)

        # 通知观察者
        self._notify_watchers(config_name, config)

        return config

    def _notify_watchers(self, config_name: str, config: dict[str, Any]) -> None:
        """通知所有注册的观察者。"""
        callbacks = self._watchers.get(config_name, [])
        if not callbacks:
            return

        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    self._schedule_async(cb, config)
                else:
                    cb(config)
            except Exception:
                logger.exception(
                    "观察者回调异常: %s -> %s", config_name, cb.__qualname__
                )

    def _schedule_async(
        self,
        cb: AsyncConfigCallback,
        config: dict[str, Any],
    ) -> None:
        """跨线程调度异步回调。"""
        loop = self._loop
        if loop is None or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning(
                    "无法调度异步回调（无运行中的事件循环）: %s", cb.__qualname__
                )
                return

        asyncio.run_coroutine_threadsafe(cb(config), loop)

    @staticmethod
    def _load_config_file(file_path: str) -> dict[str, Any]:
        """解析配置文件（YAML 或 JSON）。

        Raises:
            ConfigReloadError: 解析失败时抛出。
        """
        path = Path(file_path)
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix in (".yaml", ".yml"):
                result = yaml.safe_load(text)
            elif path.suffix == ".json":
                result = json.loads(text)
            else:
                raise ConfigReloadError(
                    message=f"不支持的配置文件格式: {path.suffix}",
                    details={"file": file_path},
                )
        except (yaml.YAMLError, json.JSONDecodeError, OSError) as exc:
            raise ConfigReloadError(
                message=f"配置文件解析失败: {path.name}",
                details={"file": file_path, "error": str(exc)},
            ) from exc

        if not isinstance(result, dict):
            raise ConfigReloadError(
                message=f"配置文件顶层必须是对象: {path.name}",
                details={"file": file_path, "got_type": type(result).__name__},
            )

        return result
