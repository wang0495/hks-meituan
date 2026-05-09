"""故障检测器。

基于滑动窗口的失败计数，当某个服务在指定时间窗口内的失败次数
超过阈值时，将其标记为故障状态。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FaultDetector:
    """故障检测器。

    通过滑动窗口机制跟踪各服务的失败次数：
    - 在窗口内累计失败次数
    - 超过窗口时间自动重置计数
    - 达到阈值即判定为故障

    Args:
        threshold: 触发故障判定的失败次数阈值。
        window: 滑动窗口的时间跨度。
    """

    def __init__(
        self,
        threshold: int = 5,
        window: timedelta = timedelta(minutes=5),
    ) -> None:
        self._failure_counts: dict[str, int] = {}
        self._last_failure: dict[str, datetime] = {}
        self._threshold = threshold
        self._window = window

    def record_failure(self, service: str) -> bool:
        """记录一次失败，并判断是否已达到故障阈值。

        Args:
            service: 服务名称。

        Returns:
            True 表示该服务已达到故障阈值，False 表示尚未达到。
        """
        now = datetime.now()

        # 超出窗口则重置计数
        if service in self._last_failure:
            if now - self._last_failure[service] > self._window:
                self._failure_counts[service] = 0

        self._failure_counts[service] = self._failure_counts.get(service, 0) + 1
        self._last_failure[service] = now

        if self._failure_counts[service] >= self._threshold:
            logger.error(
                "服务 %s 故障次数 (%d) 超过阈值 (%d)",
                service,
                self._failure_counts[service],
                self._threshold,
            )
            return True

        logger.warning(
            "服务 %s 失败 %d/%d",
            service,
            self._failure_counts[service],
            self._threshold,
        )
        return False

    def record_success(self, service: str) -> None:
        """记录一次成功，重置失败计数。

        Args:
            service: 服务名称。
        """
        self._failure_counts[service] = 0

    def is_faulty(self, service: str) -> bool:
        """判断指定服务是否处于故障状态。

        Args:
            service: 服务名称。

        Returns:
            True 表示故障状态。
        """
        return self._failure_counts.get(service, 0) >= self._threshold

    def get_failure_count(self, service: str) -> int:
        """获取当前失败计数。

        Args:
            service: 服务名称。

        Returns:
            当前失败次数。
        """
        return self._failure_counts.get(service, 0)

    def reset(self, service: str) -> None:
        """手动重置指定服务的状态。

        Args:
            service: 服务名称。
        """
        self._failure_counts.pop(service, None)
        self._last_failure.pop(service, None)

    def reset_all(self) -> None:
        """重置所有服务的故障状态。"""
        self._failure_counts.clear()
        self._last_failure.clear()
