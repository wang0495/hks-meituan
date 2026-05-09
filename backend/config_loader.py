"""配置加载与验证。

根据 ENVIRONMENT 环境变量自动选择 .env 文件，
并在创建 Settings 实例后执行额外的业务验证。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from backend.config import Environment, Settings

logger = logging.getLogger(__name__)


def load_config(env: Environment | None = None) -> Settings:
    """加载并验证配置。

    Args:
        env: 指定环境。为 None 时从 ENVIRONMENT 环境变量读取，默认 dev。

    Returns:
        经过验证的 Settings 实例。
    """
    if env is None:
        env = Environment(os.getenv("ENVIRONMENT", "dev"))

    # 按优先级加载 .env 文件：.env.{env} > .env
    env_file = Path(f".env.{env.value}")
    if env_file.exists():
        load_dotenv(env_file, override=True)
        logger.info("已加载环境配置: %s", env_file)
    else:
        load_dotenv(".env", override=True)
        logger.info("未找到 %s，已加载 .env", env_file)

    config = Settings()
    validate_config(config)
    return config


def validate_config(config: Settings) -> None:
    """业务层面的配置校验。

    Raises:
        ValueError: 配置不合法时抛出。
    """
    # 生产环境必须配置 LLM API Key
    if config.environment == Environment.PROD and not config.llm.api_key:
        raise ValueError("生产环境必须配置 LLM_API_KEY")

    # 端口范围
    if not (1024 <= config.port <= 65535):
        raise ValueError(f"端口必须在 1024-65535 之间，当前值: {config.port}")

    # worker 数量
    if config.workers < 1:
        raise ValueError(f"worker 数必须大于 0，当前值: {config.workers}")


def get_config_summary(config: Settings) -> dict[str, str | int | bool]:
    """获取配置摘要（隐藏敏感信息）。"""
    return {
        "environment": config.environment.value,
        "debug": config.debug,
        "host": config.host,
        "port": config.port,
        "workers": config.workers,
        "log_level": config.log_level,
        "llm_model": config.llm.model,
        "llm_timeout": config.llm.timeout,
        "rate_limit": config.security.rate_limit_per_minute,
    }
