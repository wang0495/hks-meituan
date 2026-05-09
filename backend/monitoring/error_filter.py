"""Sentry 事件过滤器。

在事件发送到 Sentry 之前进行过滤，减少噪音、降低成本。
过滤逻辑：
  - 静默 KeyboardInterrupt / SystemExit 等非业务异常
  - 静默速率限制等预期可恢复错误
  - 过滤健康检查等高频低价值事务
  - 脱敏请求头中的敏感信息
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 不需要上报的异常类型名
_IGNORED_EXCEPTIONS: frozenset[str] = frozenset(
    {
        "KeyboardInterrupt",
        "SystemExit",
        "GeneratorExit",
        "CancelledError",
    }
)

# 消息中包含这些关键词的异常不上报
_IGNORED_MESSAGE_KEYWORDS: tuple[str, ...] = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "connection reset",
    "broken pipe",
)

# 不需要采集事务的路径前缀
_IGNORED_TRANSACTION_PREFIXES: tuple[str, ...] = (
    "/health",
    "/healthz",
    "/readyz",
    "/livez",
    "/metrics",
)


def before_send(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any] | None:
    """Sentry before_send 回调 — 过滤异常事件。

    返回 None 表示丢弃该事件，返回 event 表示正常上报。
    """
    if "exc_info" not in hint:
        return event

    exc_type, exc_value, _ = hint["exc_info"]

    # 1) 静默非业务异常
    if exc_type.__name__ in _IGNORED_EXCEPTIONS:
        logger.debug("Sentry: 忽略异常类型 %s", exc_type.__name__)
        return None

    # 2) 按消息关键词过滤
    exc_msg = str(exc_value).lower()
    for keyword in _IGNORED_MESSAGE_KEYWORDS:
        if keyword in exc_msg:
            logger.debug("Sentry: 忽略含关键词 '%s' 的异常", keyword)
            return None

    # 3) 清理请求头中的敏感字段
    _sanitize_request_headers(event)

    return event


def before_send_transaction(
    event: dict[str, Any],
    hint: dict[str, Any],
) -> dict[str, Any] | None:
    """Sentry before_send_transaction 回调 — 过滤事务事件。

    过滤健康检查等高频低价值路径。
    """
    transaction_name = event.get("transaction", "")

    for prefix in _IGNORED_TRANSACTION_PREFIXES:
        if transaction_name.startswith(prefix):
            logger.debug("Sentry: 忽略事务 %s", transaction_name)
            return None

    return event


def _sanitize_request_headers(event: dict[str, Any]) -> None:
    """脱敏请求头中的 Authorization / Cookie 等字段。"""
    request = event.get("request", {})
    headers: dict[str, str] = request.get("headers", {})

    sensitive_keys = {"authorization", "cookie", "x-api-key", "x-auth-token"}
    for key in headers:
        if key.lower() in sensitive_keys:
            headers[key] = "[Filtered]"
