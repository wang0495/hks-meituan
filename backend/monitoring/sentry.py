"""Sentry 初始化与辅助函数。

使用方式：
    在应用启动时调用 init_sentry()，之后可直接使用
    capture_exception / capture_message 上报事件。

    环境变量：
      SENTRY_DSN      — Sentry DSN（为空则不初始化）
      ENVIRONMENT      — 环境名，默认 development
      APP_VERSION      — 应用版本号，默认 1.0.0
"""

from __future__ import annotations

import logging
import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from backend.monitoring.error_filter import (before_send,
                                             before_send_transaction)

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    """初始化 Sentry SDK。

    Returns:
        True 表示初始化成功，False 表示未配置 DSN 而跳过。
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("SENTRY_DSN 未配置，跳过 Sentry 初始化")
        return False

    environment = os.getenv("ENVIRONMENT", "development")
    release = os.getenv("APP_VERSION", "1.0.0")

    # 根据环境调整采样率：生产环境低采样，开发/测试全采样
    traces_sample_rate = _get_traces_sample_rate(environment)
    profiles_sample_rate = _get_profiles_sample_rate(environment)

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        environment=environment,
        release=f"cityflow@{release}",
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        # 发送默认 PII（用户 IP 等），按需关闭
        send_default_pii=True,
        # 最大面包屑数量
        max_breadcrumbs=50,
    )

    logger.info(
        "Sentry 已初始化: environment=%s, release=%s, traces_sample_rate=%s",
        environment,
        release,
        traces_sample_rate,
    )
    return True


def capture_exception(
    error: Exception,
    context: dict[str, Any] | None = None,
) -> str | None:
    """上报异常到 Sentry。

    Args:
        error: 要上报的异常实例。
        context: 附加上下文信息，会写入 Sentry extra 字段。

    Returns:
        Sentry event_id，未初始化时返回 None。
    """
    if context:
        with sentry_sdk.new_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_exception(error)

    return sentry_sdk.capture_exception(error)


def capture_message(
    message: str,
    level: str = "info",
    context: dict[str, Any] | None = None,
) -> str | None:
    """上报消息到 Sentry。

    Args:
        message: 消息内容。
        level: 日志级别 (debug/info/warning/error/fatal)。
        context: 附加上下文信息。

    Returns:
        Sentry event_id，未初始化时返回 None。
    """
    if context:
        with sentry_sdk.new_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            return sentry_sdk.capture_message(message, level=level)

    return sentry_sdk.capture_message(message, level=level)


def set_user_context(
    user_id: str,
    email: str | None = None,
    username: str | None = None,
    **extra: Any,
) -> None:
    """设置当前请求的用户上下文。"""
    sentry_sdk.set_user(
        {
            "id": user_id,
            "email": email,
            "username": username,
            **extra,
        }
    )


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """添加面包屑（调试线索）。"""
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data,
    )


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _get_traces_sample_rate(environment: str) -> float:
    """按环境返回事务采样率。"""
    rate_map = {
        "development": 1.0,
        "dev": 1.0,
        "test": 1.0,
        "staging": 0.5,
        "production": 0.1,
        "prod": 0.1,
    }
    return rate_map.get(environment, 0.1)


def _get_profiles_sample_rate(environment: str) -> float:
    """按环境返回性能分析采样率。"""
    rate_map = {
        "development": 1.0,
        "dev": 1.0,
        "test": 0.0,
        "staging": 0.1,
        "production": 0.05,
        "prod": 0.05,
    }
    return rate_map.get(environment, 0.05)
