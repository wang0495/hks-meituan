"""CityFlow 优雅停机管理器。

提供三阶段停机流程：
1. 信号捕获 -- 拦截 SIGINT/SIGTERM，触发停机事件
2. 请求排空 -- 等待正在处理的请求完成（带超时）
3. 资源清理 -- 按依赖顺序关闭数据库连接池、Redis、消息队列等

使用方式::

    from backend.services.graceful_shutdown import get_shutdown_manager

    manager = get_shutdown_manager()

    # 在中间件中注册请求
    manager.request_started(request_id)
    try:
        response = await handle(request)
    finally:
        manager.request_finished(request_id)

    # 在 startup 中注册信号
    manager.register_signal_handlers()

    # 在 shutdown 回调中执行清理
    await manager.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# 可注册的异步清理回调
CleanupCallback = Callable[[], Coroutine[Any, Any, None]]


@dataclass
class ShutdownStats:
    """停机统计信息。"""

    active_requests: int = 0
    total_requests: int = 0
    shutdown_started: bool = False
    shutdown_completed: bool = False
    timed_out: bool = False
    cleanup_errors: list[str] = field(default_factory=list)


class GracefulShutdown:
    """优雅停机管理器。

    职责：
    - 管理停机信号的捕获与分发
    - 跟踪活跃请求并在停机时等待排空
    - 按注册顺序依次执行资源清理回调

    Attributes:
        shutdown_timeout: 请求排空超时时间（秒），超时后强制关闭。
    """

    def __init__(self, shutdown_timeout: float = 30.0) -> None:
        self._shutdown_event = asyncio.Event()
        self._active_requests: set[str] = set()
        self._shutdown_timeout = shutdown_timeout
        self._cleanup_callbacks: list[tuple[str, CleanupCallback]] = []
        self._stats = ShutdownStats()
        self._handlers_registered = False

    # ------------------------------------------------------------------
    # 停机事件
    # ------------------------------------------------------------------

    @property
    def is_shutting_down(self) -> bool:
        """是否正在停机。"""
        return self._stats.shutdown_started

    async def wait_for_shutdown(self) -> None:
        """等待停机信号。

        在需要阻塞当前任务直到停机时使用，例如后台轮询循环。
        """
        await self._shutdown_event.wait()

    # ------------------------------------------------------------------
    # 请求跟踪
    # ------------------------------------------------------------------

    def request_started(self, request_id: str) -> None:
        """注册一个活跃请求。

        Args:
            request_id: 请求唯一标识。
        """
        if self._stats.shutdown_started:
            logger.debug("停机中，忽略新请求注册: %s", request_id)
            return
        self._active_requests.add(request_id)
        self._stats.active_requests = len(self._active_requests)
        self._stats.total_requests += 1

    def request_finished(self, request_id: str) -> None:
        """注销一个已完成的请求。

        Args:
            request_id: 请求唯一标识。
        """
        self._active_requests.discard(request_id)
        self._stats.active_requests = len(self._active_requests)

    @property
    def active_request_count(self) -> int:
        """当前活跃请求数。"""
        return len(self._active_requests)

    # ------------------------------------------------------------------
    # 清理回调注册
    # ------------------------------------------------------------------

    def register_cleanup(self, name: str, callback: CleanupCallback) -> None:
        """注册资源清理回调。

        回调按注册顺序依次执行（非并发），单个回调异常不影响后续执行。

        Args:
            name: 清理步骤名称（用于日志）。
            callback: 异步无参函数，执行资源释放。
        """
        self._cleanup_callbacks.append((name, callback))
        logger.debug("注册清理回调: %s", name)

    # ------------------------------------------------------------------
    # 信号处理
    # ------------------------------------------------------------------

    def register_signal_handlers(self) -> None:
        """注册操作系统信号处理器。

        - Linux/macOS: SIGINT 和 SIGTERM
        - Windows: 仅 SIGINT（SIGTERM 不被 loop.add_signal_handler 支持）

        幂等，重复调用无副作用。
        """
        if self._handlers_registered:
            return

        loop = asyncio.get_running_loop()

        if sys.platform == "win32":
            # Windows: loop.add_signal_handler 不支持 SIGTERM
            # 使用 signal.signal 作为备选
            def _on_sigint(signum: int, frame: Any) -> None:
                logger.info("收到 SIGINT 信号，触发优雅停机")
                asyncio.ensure_future(self.shutdown())  # noqa: RUF006

            signal.signal(signal.SIGINT, _on_sigint)
            logger.info("已注册 SIGINT 信号处理器（Windows）")
        else:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(self._handle_signal(s)),
                )
            logger.info("已注册 SIGINT/SIGTERM 信号处理器")

        self._handlers_registered = True

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """处理信号事件。"""
        logger.info("收到信号 %s，触发优雅停机", sig.name)
        await self.shutdown()

    # ------------------------------------------------------------------
    # 停机执行
    # ------------------------------------------------------------------

    async def shutdown(self) -> ShutdownStats:
        """执行三阶段优雅停机。

        1. 设置停机事件，拒绝新请求
        2. 等待活跃请求完成（超时则强制继续）
        3. 按注册顺序执行清理回调

        Returns:
            停机统计信息。
        """
        if self._stats.shutdown_started:
            logger.warning("停机已在进行中，忽略重复调用")
            return self._stats

        self._stats.shutdown_started = True
        self._shutdown_event.set()
        logger.info("===== 开始优雅停机 =====")

        # 阶段 1: 等待活跃请求排空
        await self._drain_requests()

        # 阶段 2: 执行资源清理
        await self._run_cleanup()

        self._stats.shutdown_completed = True
        logger.info(
            "===== 停机完成 | 总请求=%d, 清理错误=%d =====",
            self._stats.total_requests,
            len(self._stats.cleanup_errors),
        )
        return self._stats

    async def _drain_requests(self) -> None:
        """等待活跃请求完成。"""
        if not self._active_requests:
            logger.info("无活跃请求，跳过排空")
            return

        logger.info(
            "等待 %d 个活跃请求完成（超时 %.1fs）...",
            len(self._active_requests),
            self._shutdown_timeout,
        )

        try:
            await asyncio.wait_for(
                self._wait_until_idle(),
                timeout=self._shutdown_timeout,
            )
            logger.info("所有活跃请求已完成")
        except TimeoutError:
            self._stats.timed_out = True
            remaining = len(self._active_requests)
            logger.warning(
                "请求排空超时（%.1fs），仍有 %d 个请求未完成，强制继续停机",
                self._shutdown_timeout,
                remaining,
            )

    async def _wait_until_idle(self) -> None:
        """轮询等待直到无活跃请求。"""
        while self._active_requests:
            await asyncio.sleep(0.1)

    async def _run_cleanup(self) -> None:
        """按注册顺序执行清理回调。"""
        if not self._cleanup_callbacks:
            logger.info("无注册清理回调")
            return

        logger.info("开始执行 %d 个清理步骤...", len(self._cleanup_callbacks))
        for name, callback in self._cleanup_callbacks:
            try:
                logger.info("清理步骤: %s", name)
                await callback()
                logger.info("清理步骤完成: %s", name)
            except Exception:
                error_msg = f"清理步骤失败: {name}"
                logger.exception(error_msg)
                self._stats.cleanup_errors.append(error_msg)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """返回当前状态字典。"""
        return {
            "is_shutting_down": self._stats.shutdown_started,
            "active_requests": self.active_request_count,
            "total_requests": self._stats.total_requests,
            "shutdown_completed": self._stats.shutdown_completed,
            "timed_out": self._stats.timed_out,
            "cleanup_errors": self._stats.cleanup_errors,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_shutdown_manager: GracefulShutdown | None = None


def get_shutdown_manager() -> GracefulShutdown:
    """获取全局优雅停机管理器单例。"""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdown()
    return _shutdown_manager


def reset_shutdown_manager() -> None:
    """重置全局停机管理器（仅用于测试）。"""
    global _shutdown_manager
    _shutdown_manager = None
