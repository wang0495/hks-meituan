"""CityFlow 应用配置。

通过环境变量 / .env 文件加载配置，使用 pydantic-settings 进行校验。
支持多环境（dev / test / prod）配置，子配置按模块拆分。
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """运行环境枚举。"""

    DEV = "dev"
    TEST = "test"
    PROD = "prod"


# ---------------------------------------------------------------------------
# 子配置
# ---------------------------------------------------------------------------


class DatabaseSettings(BaseSettings):
    """数据库配置。"""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    user: str = "cityflow"
    password: str = ""
    database: str = "cityflow"


class RedisSettings(BaseSettings):
    """Redis 配置。"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0


class LLMSettings(BaseSettings):
    """LLM 服务配置。"""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout: int = 5
    max_retries: int = 3


class SecuritySettings(BaseSettings):
    """安全配置。"""

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    rate_limit_per_minute: int = 60
    max_request_size: int = 10 * 1024 * 1024  # 10 MB
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    api_key: str = ""
    encryption_key: str = ""  # 数据加密主密钥，留空则从 ENCRYPTION_KEY 环境变量读取


class AgentSettings(BaseSettings):
    """多智能体配置。"""

    model_config = SettingsConfigDict(env_prefix="AGENT_")

    enabled: bool = False  # 特性开关: 启用新LangGraph管线
    validation_timeout: float = 10.0  # 校验器超时(秒)
    max_validation_rounds: int = 2  # 最大校验循环次数
    local_expert_temperature: float = 0.3  # LocalExpert LLM温度


# ---------------------------------------------------------------------------
# 主配置
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """CityFlow 主配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ---- 环境 ----
    environment: Environment = Environment.DEV
    debug: bool = False

    # ---- 服务 ----
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # ---- 日志 ----
    log_level: str = "INFO"
    log_file: str | None = None

    # ---- 数据 ----
    data_dir: str = "backend/data"
    cache_ttl: int = 300
    use_db: bool = Field(default=False, description="启用数据库模式：POI 数据优先从 PostgreSQL 查询，不可用时回退 JSON")

    # ---- 子配置（嵌套环境变量前缀由各子类自行定义） ----
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)

    # ------------------------------------------------------------------
    # 自动推导字段
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _apply_env_defaults(self) -> Settings:
        """根据 environment 自动调整 debug / log_level。"""
        if self.environment == Environment.DEV and not self.debug:
            # 开发环境默认开启 debug
            object.__setattr__(self, "debug", True)
        if self.environment == Environment.PROD and self.log_level == "INFO":
            # 生产环境默认 WARNING
            object.__setattr__(self, "log_level", "WARNING")
        return self


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

settings = Settings()


def get_settings() -> Settings:
    """获取全局配置实例。"""
    return settings
