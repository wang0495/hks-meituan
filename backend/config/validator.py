"""CityFlow YAML 配置文件验证器。

验证 YAML 配置文件的格式、必需字段和值范围。
与 ``backend.tools.config_validator``（验证 .env）互补。

用法::

    from backend.config.validator import ConfigValidator

    validator = ConfigValidator()
    result = validator.validate_file("config/app.yaml")
    if not result.valid:
        for err in result.errors:
            print(err)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from backend.errors import CityFlowException, ErrorCode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: dict[str, str] = {
    "app_name": "应用名称",
    "version": "版本号",
    "environment": "运行环境",
}

VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"development", "testing", "production", "dev", "test", "prod"}
)

VALID_LOG_LEVELS: frozenset[str] = frozenset(
    {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
)

# 各子配置的必需字段
SECTION_REQUIRED_FIELDS: dict[str, dict[str, str]] = {
    "database": {
        "host": "数据库主机",
        "port": "数据库端口",
    },
    "redis": {
        "host": "Redis 主机",
        "port": "Redis 端口",
    },
    "llm": {
        "api_key": "LLM API 密钥",
        "base_url": "LLM 服务地址",
    },
}


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """验证结果。"""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


class ConfigValidationError(CityFlowException):
    """配置验证错误。"""

    def __init__(
        self,
        message: str = "配置验证失败",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.INVALID_REQUEST,
            message=message,
            details=details,
        )


# ---------------------------------------------------------------------------
# 验证器
# ---------------------------------------------------------------------------


class ConfigValidator:
    """YAML 配置文件验证器。

    支持三种验证：
    1. 配置文件格式验证（YAML 语法）
    2. 必需配置项验证
    3. 配置值范围验证
    """

    def __init__(self) -> None:
        self._errors: list[str] = []
        self._warnings: list[str] = []

    def reset(self) -> None:
        """清除累积的问题，以便复用实例。"""
        self._errors.clear()
        self._warnings.clear()

    # ------------------------------------------------------------------
    # 1. 文件验证
    # ------------------------------------------------------------------

    def validate_file(self, config_file: str | Path) -> ValidationResult:
        """验证 YAML 配置文件。

        按顺序执行：
        1. 检查文件是否存在
        2. 解析 YAML 格式
        3. 验证配置内容

        Args:
            config_file: 配置文件路径。

        Returns:
            验证结果。
        """
        self.reset()
        result = ValidationResult()
        path = Path(config_file)

        if not path.exists():
            result.add_error(f"配置文件不存在: {path}")
            return result

        if path.suffix not in {".yaml", ".yml"}:
            result.add_warning(f"文件扩展名不是 YAML: {path.suffix}")

        try:
            text = path.read_text(encoding="utf-8")
            config = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            result.add_error(f"YAML 格式错误: {exc}")
            return result
        except OSError as exc:
            result.add_error(f"文件读取失败: {exc}")
            return result

        if not isinstance(config, dict):
            result.add_error(f"配置顶层必须是对象，实际类型: {type(config).__name__}")
            return result

        # 合并内容验证结果
        content_result = self.validate_config(config)
        result.errors.extend(content_result.errors)
        result.warnings.extend(content_result.warnings)
        result.valid = result.valid and content_result.valid
        result.details = content_result.details

        return result

    # ------------------------------------------------------------------
    # 2. 内容验证
    # ------------------------------------------------------------------

    def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """验证配置字典内容。

        检查项：
        - 顶层必需字段
        - environment 合法性
        - port 范围
        - log_level 合法性
        - 子配置段的必需字段

        Args:
            config: 配置字典。

        Returns:
            验证结果。
        """
        result = ValidationResult()

        self._check_required_fields(config, result)
        self._check_environment(config, result)
        self._check_port(config, result)
        self._check_log_level(config, result)
        self._check_workers(config, result)
        self._check_sections(config, result)

        result.details["field_count"] = len(config)
        return result

    # ------------------------------------------------------------------
    # 3. 环境变量验证
    # ------------------------------------------------------------------

    def validate_env_vars(self, required_vars: list[str]) -> ValidationResult:
        """验证环境变量是否已设置。

        Args:
            required_vars: 必需的环境变量名列表。

        Returns:
            验证结果。
        """
        import os

        result = ValidationResult()
        missing: list[str] = []

        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)

        if missing:
            result.add_error(f"缺少环境变量: {', '.join(missing)}")
            result.details["missing"] = missing

        return result

    # ------------------------------------------------------------------
    # 内部检查方法
    # ------------------------------------------------------------------

    @staticmethod
    def _check_required_fields(
        config: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """检查顶层必需字段。"""
        for field_name, description in REQUIRED_FIELDS.items():
            if field_name not in config:
                result.add_error(f"缺少必需字段: {field_name}（{description}）")

    @staticmethod
    def _check_environment(
        config: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """检查 environment 值是否合法。"""
        env = config.get("environment")
        if env is None:
            return
        env_str = str(env).lower()
        if env_str not in VALID_ENVIRONMENTS:
            result.add_warning(
                f"未知环境: {env!r}，"
                f"建议值: {', '.join(sorted(VALID_ENVIRONMENTS))}"
            )

    @staticmethod
    def _check_port(
        config: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """检查端口范围。"""
        port = config.get("port")
        if port is None:
            return

        if not isinstance(port, int) or not (1 <= port <= 65535):
            result.add_error(f"端口必须是 1-65535 的整数: {port}")
        elif port < 1024:
            result.add_warning(f"端口 {port} 是特权端口（<1024），可能需要 root 权限")

    @staticmethod
    def _check_log_level(
        config: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """检查日志级别。"""
        level = config.get("log_level")
        if level is None:
            return
        if str(level).upper() not in VALID_LOG_LEVELS:
            result.add_warning(
                f"未知日志级别: {level!r}，"
                f"可选值: {', '.join(sorted(VALID_LOG_LEVELS))}"
            )

    @staticmethod
    def _check_workers(
        config: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """检查 workers 数量。"""
        workers = config.get("workers")
        if workers is None:
            return
        if not isinstance(workers, int) or workers < 1:
            result.add_error(f"workers 必须是正整数: {workers}")

    @classmethod
    def _check_sections(
        cls,
        config: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """检查子配置段的必需字段。"""
        for section_name, required in SECTION_REQUIRED_FIELDS.items():
            section = config.get(section_name)
            if section is None:
                continue
            if not isinstance(section, dict):
                result.add_error(f"{section_name} 必须是对象，实际类型: {type(section).__name__}")
                continue
            for field_name, description in required.items():
                if field_name not in section:
                    result.add_warning(
                        f"{section_name}.{field_name} 未配置（{description}）"
                    )

    # ------------------------------------------------------------------
    # 聚合验证
    # ------------------------------------------------------------------

    def validate_all(
        self,
        config_file: str | Path,
        required_env_vars: list[str] | None = None,
    ) -> dict[str, ValidationResult]:
        """执行全部验证。

        Args:
            config_file: 配置文件路径。
            required_env_vars: 额外需要检查的环境变量。

        Returns:
            各项验证结果。
        """
        self.reset()
        results: dict[str, ValidationResult] = {
            "config_file": self.validate_file(config_file),
        }

        if required_env_vars:
            results["env_vars"] = self.validate_env_vars(required_env_vars)

        return results

    def is_valid(
        self,
        config_file: str | Path,
        required_env_vars: list[str] | None = None,
    ) -> bool:
        """快速判断配置是否全部通过。"""
        results = self.validate_all(config_file, required_env_vars)
        return all(r.valid for r in results.values())
