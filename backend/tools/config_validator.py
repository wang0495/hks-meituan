"""CityFlow 配置验证工具。

验证 .env 文件格式、必需环境变量、配置一致性。
可独立运行，也可作为模块导入。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Severity(StrEnum):
    """问题严重等级。"""

    ERROR = "error"
    WARNING = "warning"


@dataclass
class Issue:
    """单条验证问题。"""

    severity: Severity
    message: str
    source: str = ""


@dataclass
class ValidationResult:
    """验证结果汇总。"""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ---------------------------------------------------------------------------
# .env 文件中建议配置的变量（与 backend/config.py 保持一致）
# ---------------------------------------------------------------------------
REQUIRED_ENV_VARS: dict[str, str] = {
    "LLM_API_KEY": "LLM 服务 API 密钥",
    "LLM_BASE_URL": "LLM 服务地址",
    "SECURITY_ENCRYPTION_KEY": "数据加密主密钥",
}

OPTIONAL_ENV_VARS: dict[str, str] = {
    "DB_HOST": "数据库主机",
    "DB_PORT": "数据库端口",
    "DB_USER": "数据库用户名",
    "DB_PASSWORD": "数据库密码",
    "DB_DATABASE": "数据库名称",
    "REDIS_HOST": "Redis 主机",
    "REDIS_PORT": "Redis 端口",
    "SENTRY_DSN": "Sentry 错误追踪 DSN",
}

VALID_LOG_LEVELS: frozenset[str] = frozenset(
    {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
)

VALID_ENVIRONMENTS: frozenset[str] = frozenset({"dev", "test", "prod"})


class ConfigValidator:
    """CityFlow 配置验证器。

    支持三种验证：
    1. .env 文件格式与内容验证
    2. 运行时环境变量验证
    3. 配置项一致性 / 合法性验证
    """

    def __init__(self) -> None:
        self._errors: list[str] = []
        self._warnings: list[str] = []

    def reset(self) -> None:
        """清除累积的问题，以便复用实例。"""
        self._errors.clear()
        self._warnings.clear()

    # ------------------------------------------------------------------
    # 1. .env 文件验证
    # ------------------------------------------------------------------

    def validate_env_file(
        self,
        env_file: str | Path = ".env",
    ) -> ValidationResult:
        """验证 .env 文件是否存在、格式是否合法。

        检查项：
        - 文件是否存在
        - 每行是否为注释 / 空行 / KEY=VALUE 格式
        - 是否包含建议配置的必需变量
        """
        result = ValidationResult()
        path = Path(env_file)

        if not path.exists():
            result.add_error(f"配置文件不存在: {path}")
            return result

        content = path.read_text(encoding="utf-8")
        defined_keys: set[str] = set()

        for lineno, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.strip()

            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue

            # 解析 KEY=VALUE
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
            if match is None:
                result.add_error(f"第 {lineno} 行格式错误（应为 KEY=VALUE）: {line}")
                continue

            key = match.group(1)
            value = match.group(2).strip()

            defined_keys.add(key)

            # 值为空且是必需变量 -> 警告
            if not value and key in REQUIRED_ENV_VARS:
                result.add_warning(f"{key} 值为空（{REQUIRED_ENV_VARS[key]}）")

        # 检查必需变量是否出现
        for var, desc in REQUIRED_ENV_VARS.items():
            if var not in defined_keys:
                result.add_warning(f"建议配置: {var} — {desc}")

        result.details["defined_keys"] = sorted(defined_keys)
        return result

    # ------------------------------------------------------------------
    # 2. 环境变量验证
    # ------------------------------------------------------------------

    def validate_required_vars(self) -> ValidationResult:
        """验证当前环境中必需的环境变量是否已设置。

        只检查变量是否存在，不校验值的合法性。
        """
        result = ValidationResult()
        missing: list[str] = []

        for var, description in REQUIRED_ENV_VARS.items():
            value = os.getenv(var)
            if not value:
                missing.append(f"{var} ({description})")

        if missing:
            result.add_error(f"缺少必需环境变量: {', '.join(missing)}")
            result.details["missing"] = missing

        return result

    # ------------------------------------------------------------------
    # 3. 配置一致性检查
    # ------------------------------------------------------------------

    def validate_config_consistency(self) -> ValidationResult:
        """验证配置项的值是否合法且一致。

        检查项：
        - ENVIRONMENT 枚举值
        - PORT 范围
        - LOG_LEVEL 合法性
        - DB_PORT / REDIS_PORT 范围
        - LLM_TIMEOUT 正整数
        - SECURITY_RATE_LIMIT_PER_MINUTE 正整数
        """
        result = ValidationResult()

        self._check_environment(result)
        self._check_port(result, "PORT", default="8000")
        self._check_log_level(result)
        self._check_port(result, "DB_PORT", default="5432")
        self._check_port(result, "REDIS_PORT", default="6379")
        self._check_positive_int(result, "LLM_TIMEOUT", default="5")
        self._check_positive_int(result, "SECURITY_RATE_LIMIT_PER_MINUTE", default="60")
        self._check_data_dir(result)

        return result

    # ------------------------------------------------------------------
    # 内部检查方法
    # ------------------------------------------------------------------

    @staticmethod
    def _check_environment(result: ValidationResult) -> None:
        env = os.getenv("ENVIRONMENT", "dev").lower()
        if env not in VALID_ENVIRONMENTS:
            result.add_error(
                f"ENVIRONMENT 值无效: {env!r}，"
                f"可选值: {', '.join(sorted(VALID_ENVIRONMENTS))}"
            )

    @staticmethod
    def _check_port(
        result: ValidationResult,
        var_name: str,
        default: str = "8000",
    ) -> None:
        value = os.getenv(var_name, default)
        if not value.isdigit() or not (1 <= int(value) <= 65535):
            result.add_error(f"{var_name} 不是合法端口: {value!r}")
        elif int(value) < 1024:
            result.add_warning(
                f"{var_name}={value} 使用了特权端口（<1024），可能需要 root 权限"
            )

    @staticmethod
    def _check_log_level(result: ValidationResult) -> None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        if level not in VALID_LOG_LEVELS:
            result.add_error(
                f"LOG_LEVEL 值无效: {level!r}，"
                f"可选值: {', '.join(sorted(VALID_LOG_LEVELS))}"
            )

    @staticmethod
    def _check_positive_int(
        result: ValidationResult,
        var_name: str,
        default: str = "1",
    ) -> None:
        value = os.getenv(var_name, default)
        if not value.isdigit() or int(value) <= 0:
            result.add_error(f"{var_name} 应为正整数，当前值: {value!r}")

    @staticmethod
    def _check_data_dir(result: ValidationResult) -> None:
        data_dir = os.getenv("DATA_DIR", "backend/data")
        path = Path(data_dir)
        if path.exists() and not path.is_dir():
            result.add_error(f"DATA_DIR 指向的路径不是目录: {data_dir}")

    # ------------------------------------------------------------------
    # 聚合验证
    # ------------------------------------------------------------------

    def validate_all(
        self,
        env_file: str | Path = ".env",
    ) -> dict[str, ValidationResult]:
        """执行全部验证，返回各项结果。"""
        self.reset()

        results = {
            "env_file": self.validate_env_file(env_file),
            "env_vars": self.validate_required_vars(),
            "consistency": self.validate_config_consistency(),
        }
        return results

    def is_valid(
        self,
        env_file: str | Path = ".env",
    ) -> bool:
        """快速判断配置是否全部通过。"""
        results = self.validate_all(env_file)
        return all(r.valid for r in results.values())
