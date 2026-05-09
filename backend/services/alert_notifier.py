"""CityFlow 告警通知器。

接收告警事件并分发到多个通知渠道：
- 日志记录（默认启用）
- WebSocket 广播（推送到前端仪表盘）
- 事件总线发布（供其他模块订阅）

使用示例::

    from backend.services.alert_notifier import get_alert_notifier

    notifier = get_alert_notifier()

    # 注册为资源监控回调
    from backend.services.resource_monitor import get_resource_monitor
    monitor = get_resource_monitor()
    monitor.add_callback(notifier.handle_alert_event)

    # 或者直接发送消息
    await notifier.send_warning("磁盘空间不足")
"""

from __future__ import annotations

import logging
from typing import Any

from backend.services.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)

__all__ = [
    "AlertNotifier",
    "get_alert_notifier",
    "reset_alert_notifier",
]

# 告警事件类型（用于事件总线）
ALERT_EVENT_TYPE = "resource.alert"


# ---------------------------------------------------------------------------
# 通知器
# ---------------------------------------------------------------------------


class AlertNotifier:
    """告警通知器。

    职责：
    - 将告警事件记录到日志
    - 通过事件总线发布，供 WebSocket 等模块订阅
    - 提供便捷方法发送自定义告警消息
    """

    def __init__(self) -> None:
        self._notification_count: int = 0

    # ------------------------------------------------------------------
    # 告警回调入口
    # ------------------------------------------------------------------

    async def handle_alert(
        self,
        rule_name: str,
        current_value: float,
        threshold: float,
    ) -> None:
        """处理资源监控器触发的告警。

        适配 ``ResourceMonitor.add_callback`` 的签名：
        ``(rule_name: str, value: float, threshold: float) -> None``

        Args:
            rule_name: 告警规则名称。
            current_value: 当前指标值。
            threshold: 阈值。
        """
        self._notification_count += 1
        message = (
            f"[告警] {rule_name}: 当前值={current_value:.1f}, 阈值={threshold:.1f}"
        )

        # 日志记录
        logger.warning(message)

        # 事件总线发布
        await self._publish_event(
            event_type=ALERT_EVENT_TYPE,
            data={
                "rule_name": rule_name,
                "current_value": current_value,
                "threshold": threshold,
                "level": "warning",
                "message": message,
            },
        )

    async def handle_alert_event(self, event: Any) -> None:
        """处理 ``AlertEvent`` 对象。

        适配 ``ResourceMonitor`` 发出的结构化告警事件。

        Args:
            event: ``AlertEvent`` 实例，需具有 ``to_dict`` 方法。
        """
        self._notification_count += 1
        event_dict = event.to_dict() if hasattr(event, "to_dict") else {}

        message = event_dict.get("message", str(event))
        severity = event_dict.get("severity", "warning")

        # 日志记录（按严重程度选择级别）
        if severity == "critical":
            logger.critical(message)
        else:
            logger.warning(message)

        # 事件总线发布
        await self._publish_event(
            event_type=ALERT_EVENT_TYPE,
            data={
                **event_dict,
                "level": severity,
            },
        )

    # ------------------------------------------------------------------
    # 便捷通知方法
    # ------------------------------------------------------------------

    async def send_info(self, message: str, **extra: Any) -> None:
        """发送 INFO 级别通知。

        Args:
            message: 通知内容。
            **extra: 附加数据。
        """
        logger.info("[通知] %s", message)
        await self._publish_event(
            event_type=ALERT_EVENT_TYPE,
            data={"level": "info", "message": message, **extra},
        )

    async def send_warning(self, message: str, **extra: Any) -> None:
        """发送 WARNING 级别通知。

        Args:
            message: 通知内容。
            **extra: 附加数据。
        """
        logger.warning("[通知] %s", message)
        await self._publish_event(
            event_type=ALERT_EVENT_TYPE,
            data={"level": "warning", "message": message, **extra},
        )

    async def send_critical(self, message: str, **extra: Any) -> None:
        """发送 CRITICAL 级别通知。

        Args:
            message: 通知内容。
            **extra: 附加数据。
        """
        logger.critical("[通知] %s", message)
        await self._publish_event(
            event_type=ALERT_EVENT_TYPE,
            data={"level": "critical", "message": message, **extra},
        )

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    @property
    def notification_count(self) -> int:
        """累计通知次数。"""
        return self._notification_count

    def get_status(self) -> dict[str, Any]:
        """返回通知器状态。"""
        return {
            "notification_count": self._notification_count,
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    async def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        """通过事件总线发布通知事件。"""
        try:
            bus = get_event_bus()
            await bus.publish_async(
                Event(
                    event_type=event_type,
                    data=data,
                    source="alert_notifier",
                )
            )
        except Exception:
            logger.exception("事件总线发布失败")


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_notifier: AlertNotifier | None = None


def get_alert_notifier() -> AlertNotifier:
    """获取全局告警通知器单例。"""
    global _notifier
    if _notifier is None:
        _notifier = AlertNotifier()
    return _notifier


def reset_alert_notifier() -> None:
    """重置全局告警通知器（仅用于测试）。"""
    global _notifier
    _notifier = None
