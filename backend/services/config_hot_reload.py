"""CityFlow 配置热更新。

基于 watchdog 监听配置文件变更，支持：
- .env / .yaml / .json 文件变更检测
- 变更回调注册与自动触发
- 配置快照与回滚（最多保留 N 个历史版本）
- 防抖处理（避免编辑器保存产生多次事件）
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# 支持监听的配置文件后缀
_CONFIG_EXTENSIONS = {".env", ".yaml", ".yml", ".json"}

# 防抖间隔（秒）：同一文件在此时间内的多次变更只触发一次
_DEBOUNCE_INTERVAL = 0.5


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------


class ConfigReloadError(Exception):
    """配置热更新相关错误。"""


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ConfigSnapshot:
    """配置快照，用于回滚。"""

    file_path: str
    content: str
    timestamp: float
    version: int


@dataclass(slots=True)
class _DebounceState:
    """防抖状态追踪。"""

    last_trigger: float = 0.0
    pending_task: asyncio.Task[None] | None = None


# ---------------------------------------------------------------------------
# 文件事件处理器
# ---------------------------------------------------------------------------


class _ConfigFileHandler(FileSystemEventHandler):
    """watchdog 文件事件处理器，桥接到 asyncio 回调。"""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[str], Coroutine[Any, Any, None]],
        watched_extensions: set[str],
    ) -> None:
        super().__init__()
        self._loop = loop
        self._callback = callback
        self._watched_extensions = watched_extensions
        self._debounce: dict[str, _DebounceState] = {}

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix not in self._watched_extensions:
            return

        logger.info("检测到配置文件变更: %s", event.src_path)
        self._schedule_callback(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        """新建配置文件也触发更新。"""
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix not in self._watched_extensions:
            return

        logger.info("检测到新配置文件: %s", event.src_path)
        self._schedule_callback(event.src_path)

    def _schedule_callback(self, file_path: str) -> None:
        """带防抖的回调调度。"""
        now = time.monotonic()
        state = self._debounce.get(file_path, _DebounceState())

        # 取消上一次还未执行的延迟任务
        if state.pending_task is not None and not state.pending_task.done():
            state.pending_task.cancel()

        elapsed = now - state.last_trigger
        delay = max(0.0, _DEBOUNCE_INTERVAL - elapsed)

        state.pending_task = self._loop.call_later(
            delay,
            lambda: asyncio.ensure_future(self._run_callback(file_path, state)),
        )
        self._debounce[file_path] = state

    async def _run_callback(self, file_path: str, state: _DebounceState) -> None:
        try:
            state.last_trigger = time.monotonic()
            await self._callback(file_path)
        except Exception:
            logger.exception("配置变更回调执行失败: %s", file_path)


# ---------------------------------------------------------------------------
# 配置热更新器
# ---------------------------------------------------------------------------


class ConfigHotReloader:
    """配置热更新器。

    Args:
        config_dir: 要监听的配置文件目录。
        max_snapshots: 每个文件保留的最大快照数（用于回滚）。
        watched_extensions: 要监听的文件后缀集合，默认 .env/.yaml/.yml/.json。
    """

    def __init__(
        self,
        config_dir: str = ".",
        max_snapshots: int = 10,
        watched_extensions: set[str] | None = None,
    ) -> None:
        self._config_dir = Path(config_dir).resolve()
        self._max_snapshots = max_snapshots
        self._watched_extensions = watched_extensions or _CONFIG_EXTENSIONS

        self._observer: Observer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # config_type -> handler
        self._handlers: dict[str, Callable[[str], Coroutine[Any, Any, None]]] = {}

        # file_path -> snapshot history (newest first)
        self._snapshots: dict[str, deque[ConfigSnapshot]] = {}
        self._version_counter: dict[str, int] = {}

        self._running = False

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> None:
        """启动文件监听。"""
        if self._running:
            logger.warning("配置热更新已在运行中")
            return

        self._loop = asyncio.get_running_loop()
        handler = _ConfigFileHandler(
            loop=self._loop,
            callback=self._on_config_change,
            watched_extensions=self._watched_extensions,
        )

        self._observer = Observer()
        self._observer.schedule(handler, str(self._config_dir), recursive=False)
        self._observer.daemon = True
        self._observer.start()
        self._running = True
        logger.info(
            "配置热更新已启动，监听目录: %s，文件类型: %s",
            self._config_dir,
            self._watched_extensions,
        )

    def stop(self) -> None:
        """停止文件监听。"""
        if not self._running or self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._running = False
        logger.info("配置热更新已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # 处理器注册
    # ------------------------------------------------------------------

    def register_handler(
        self,
        config_type: str,
        handler: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        """注册配置变更处理器。

        Args:
            config_type: 配置类型标识（env / yaml / json / 自定义）。
            handler: 异步回调，接收文件路径参数。
        """
        self._handlers[config_type] = handler
        logger.debug("已注册配置处理器: %s", config_type)

    def unregister_handler(self, config_type: str) -> None:
        """移除配置变更处理器。"""
        self._handlers.pop(config_type, None)

    # ------------------------------------------------------------------
    # 内部回调
    # ------------------------------------------------------------------

    async def _on_config_change(self, file_path: str) -> None:
        """处理配置文件变更：快照 -> 调用处理器。"""
        try:
            path = Path(file_path)

            # 保存快照
            self._save_snapshot(file_path)

            # 确定配置类型并调用对应处理器
            config_type = self._detect_config_type(path)
            handler = self._handlers.get(config_type)
            if handler is not None:
                await handler(file_path)
                logger.info("配置已热更新: [%s] %s", config_type, file_path)
            else:
                logger.debug("未注册处理器，跳过: [%s] %s", config_type, file_path)

        except Exception:
            logger.exception("配置热更新失败: %s", file_path)

    @staticmethod
    def _detect_config_type(path: Path) -> str:
        """根据文件名/后缀推断配置类型。"""
        name = path.name.lower()
        if name.startswith(".env"):
            return "env"
        if path.suffix in (".yaml", ".yml"):
            return "yaml"
        if path.suffix == ".json":
            return "json"
        return "unknown"

    # ------------------------------------------------------------------
    # 快照与回滚
    # ------------------------------------------------------------------

    def _save_snapshot(self, file_path: str) -> None:
        """为文件创建快照。"""
        path = Path(file_path)
        if not path.exists():
            return

        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("读取配置文件失败，跳过快照: %s", file_path)
            return

        # 递增版本号
        version = self._version_counter.get(file_path, 0) + 1
        self._version_counter[file_path] = version

        snapshot = ConfigSnapshot(
            file_path=file_path,
            content=content,
            timestamp=time.time(),
            version=version,
        )

        history = self._snapshots.setdefault(file_path, deque())
        history.appendleft(snapshot)

        # 保留最近 N 个版本
        while len(history) > self._max_snapshots:
            history.pop()

        logger.debug(
            "已保存配置快照 v%d: %s (历史数: %d)",
            version,
            file_path,
            len(history),
        )

    def rollback(self, file_path: str, steps: int = 1) -> bool:
        """回滚配置文件到指定历史版本。

        Args:
            file_path: 要回滚的文件路径。
            steps: 回滚步数（1 = 上一个版本）。

        Returns:
            是否回滚成功。

        Raises:
            ConfigReloadError: 无可用快照或步数超出范围。
        """
        history = self._snapshots.get(file_path)
        if not history:
            raise ConfigReloadError(f"无可用快照: {file_path}")

        if steps < 1 or steps >= len(history):
            raise ConfigReloadError(f"回滚步数 {steps} 超出范围（可用: 1-{len(history) - 1}）")

        target = history[steps]
        path = Path(file_path)

        try:
            path.write_text(target.content, encoding="utf-8")
            logger.info("配置已回滚到 v%d: %s", target.version, file_path)
            return True
        except Exception as exc:
            raise ConfigReloadError(f"回滚写入失败: {file_path}") from exc

    def get_snapshot_history(self, file_path: str) -> list[ConfigSnapshot]:
        """获取文件的快照历史（从新到旧）。"""
        history = self._snapshots.get(file_path)
        return list(history) if history else []

    def get_latest_snapshot(self, file_path: str) -> ConfigSnapshot | None:
        """获取文件的最新快照。"""
        history = self._snapshots.get(file_path)
        return history[0] if history else None

    def clear_snapshots(self, file_path: str | None = None) -> None:
        """清空快照。file_path 为 None 时清空全部。"""
        if file_path is None:
            self._snapshots.clear()
            self._version_counter.clear()
            logger.info("已清空全部配置快照")
        else:
            self._snapshots.pop(file_path, None)
            self._version_counter.pop(file_path, None)
            logger.info("已清空配置快照: %s", file_path)

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    def __enter__(self) -> ConfigHotReloader:
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_reloader: ConfigHotReloader | None = None


def get_config_reloader() -> ConfigHotReloader:
    """获取全局配置热更新器（懒初始化）。"""
    global _reloader
    if _reloader is None:
        _reloader = ConfigHotReloader(config_dir=".")
    return _reloader
