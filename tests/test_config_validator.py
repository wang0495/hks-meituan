"""backend.config.validator 测试。

覆盖：
- YAML 文件格式验证
- 必需字段检查
- 端口范围验证
- 日志级别验证
- 环境变量验证
- 子配置段检查
- 聚合验证
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.config.validator import ConfigValidator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator() -> ConfigValidator:
    return ConfigValidator()


@pytest.fixture
def valid_config() -> dict:
    return {
        "app_name": "CityFlow",
        "version": "1.0.0",
        "environment": "development",
        "port": 8000,
        "log_level": "INFO",
        "workers": 2,
    }


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    return cfg_dir


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# validate_config - 必需字段
# ---------------------------------------------------------------------------


class TestRequiredFields:
    def test_valid_config_passes(self, validator: ConfigValidator, valid_config: dict) -> None:
        result = validator.validate_config(valid_config)
        assert result.valid
        assert result.errors == []

    def test_missing_app_name(self, validator: ConfigValidator, valid_config: dict) -> None:
        del valid_config["app_name"]
        result = validator.validate_config(valid_config)
        assert not result.valid
        assert any("app_name" in e for e in result.errors)

    def test_missing_version(self, validator: ConfigValidator, valid_config: dict) -> None:
        del valid_config["version"]
        result = validator.validate_config(valid_config)
        assert not result.valid
        assert any("version" in e for e in result.errors)

    def test_missing_environment(self, validator: ConfigValidator, valid_config: dict) -> None:
        del valid_config["environment"]
        result = validator.validate_config(valid_config)
        assert not result.valid
        assert any("environment" in e for e in result.errors)

    def test_empty_config(self, validator: ConfigValidator) -> None:
        result = validator.validate_config({})
        assert not result.valid
        assert len(result.errors) == 3  # 三个必需字段都缺


# ---------------------------------------------------------------------------
# validate_config - environment
# ---------------------------------------------------------------------------


class TestEnvironment:
    @pytest.mark.parametrize("env", ["development", "testing", "production", "dev", "test", "prod"])
    def test_valid_environments(
        self, validator: ConfigValidator, valid_config: dict, env: str
    ) -> None:
        valid_config["environment"] = env
        result = validator.validate_config(valid_config)
        assert not any("环境" in w for w in result.warnings)

    def test_unknown_environment_warns(
        self, validator: ConfigValidator, valid_config: dict
    ) -> None:
        valid_config["environment"] = "staging"
        result = validator.validate_config(valid_config)
        assert result.valid  # warning, not error
        assert any("未知环境" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_config - port
# ---------------------------------------------------------------------------


class TestPort:
    def test_valid_port(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["port"] = 8080
        result = validator.validate_config(valid_config)
        assert not any("端口" in e for e in result.errors)

    def test_port_out_of_range_high(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["port"] = 70000
        result = validator.validate_config(valid_config)
        assert not result.valid
        assert any("端口" in e for e in result.errors)

    def test_port_zero(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["port"] = 0
        result = validator.validate_config(valid_config)
        assert not result.valid

    def test_privileged_port_warns(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["port"] = 80
        result = validator.validate_config(valid_config)
        assert result.valid  # warning only
        assert any("特权端口" in w for w in result.warnings)

    def test_string_port_errors(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["port"] = "8000"
        result = validator.validate_config(valid_config)
        assert not result.valid

    def test_no_port_is_fine(self, validator: ConfigValidator, valid_config: dict) -> None:
        del valid_config["port"]
        result = validator.validate_config(valid_config)
        assert not any("端口" in e for e in result.errors)


# ---------------------------------------------------------------------------
# validate_config - log_level
# ---------------------------------------------------------------------------


class TestLogLevel:
    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    def test_valid_levels(self, validator: ConfigValidator, valid_config: dict, level: str) -> None:
        valid_config["log_level"] = level
        result = validator.validate_config(valid_config)
        assert not any("日志级别" in w for w in result.warnings)

    def test_unknown_level_warns(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["log_level"] = "TRACE"
        result = validator.validate_config(valid_config)
        assert result.valid
        assert any("未知日志级别" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_config - workers
# ---------------------------------------------------------------------------


class TestWorkers:
    def test_valid_workers(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["workers"] = 4
        result = validator.validate_config(valid_config)
        assert not any("workers" in e for e in result.errors)

    def test_zero_workers_errors(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["workers"] = 0
        result = validator.validate_config(valid_config)
        assert not result.valid

    def test_negative_workers_errors(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["workers"] = -1
        result = validator.validate_config(valid_config)
        assert not result.valid


# ---------------------------------------------------------------------------
# validate_config - 子配置段
# ---------------------------------------------------------------------------


class TestSections:
    def test_database_missing_fields_warns(
        self, validator: ConfigValidator, valid_config: dict
    ) -> None:
        valid_config["database"] = {}
        result = validator.validate_config(valid_config)
        assert result.valid  # warnings only
        assert any("database.host" in w for w in result.warnings)
        assert any("database.port" in w for w in result.warnings)

    def test_redis_missing_fields_warns(
        self, validator: ConfigValidator, valid_config: dict
    ) -> None:
        valid_config["redis"] = {"host": "localhost"}
        result = validator.validate_config(valid_config)
        assert result.valid
        assert any("redis.port" in w for w in result.warnings)

    def test_llm_section_complete(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["llm"] = {"api_key": "sk-xxx", "base_url": "https://api.openai.com/v1"}
        result = validator.validate_config(valid_config)
        assert not any("llm." in w for w in result.warnings)

    def test_non_dict_section_errors(self, validator: ConfigValidator, valid_config: dict) -> None:
        valid_config["database"] = "not a dict"
        result = validator.validate_config(valid_config)
        assert not result.valid
        assert any("database" in e and "对象" in e for e in result.errors)

    def test_missing_section_is_fine(self, validator: ConfigValidator, valid_config: dict) -> None:
        result = validator.validate_config(valid_config)
        assert not any("database" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_file
# ---------------------------------------------------------------------------


class TestValidateFile:
    def test_valid_file(
        self, validator: ConfigValidator, config_dir: Path, valid_config: dict
    ) -> None:
        path = _write_yaml(config_dir / "app.yaml", valid_config)
        result = validator.validate_file(path)
        assert result.valid

    def test_nonexistent_file(self, validator: ConfigValidator, config_dir: Path) -> None:
        result = validator.validate_file(config_dir / "nope.yaml")
        assert not result.valid
        assert any("不存在" in e for e in result.errors)

    def test_invalid_yaml(self, validator: ConfigValidator, config_dir: Path) -> None:
        bad_file = config_dir / "bad.yaml"
        bad_file.write_text("{{{{invalid yaml: [", encoding="utf-8")
        result = validator.validate_file(bad_file)
        assert not result.valid
        assert any("YAML" in e or "格式" in e for e in result.errors)

    def test_non_dict_top_level(self, validator: ConfigValidator, config_dir: Path) -> None:
        list_file = config_dir / "list.yaml"
        list_file.write_text("- item1\n- item2\n", encoding="utf-8")
        result = validator.validate_file(list_file)
        assert not result.valid
        assert any("顶层" in e for e in result.errors)

    def test_non_yaml_extension_warns(
        self, validator: ConfigValidator, config_dir: Path, valid_config: dict
    ) -> None:
        path = _write_yaml(config_dir / "app.txt", valid_config)
        result = validator.validate_file(path)
        # file still parses, but we get a warning
        assert any("扩展名" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# validate_env_vars
# ---------------------------------------------------------------------------


class TestValidateEnvVars:
    def test_all_present(self, validator: ConfigValidator, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_VAR_A", "value1")
        monkeypatch.setenv("TEST_VAR_B", "value2")
        result = validator.validate_env_vars(["TEST_VAR_A", "TEST_VAR_B"])
        assert result.valid

    def test_missing_vars(
        self, validator: ConfigValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TEST_MISSING_X", raising=False)
        result = validator.validate_env_vars(["TEST_MISSING_X"])
        assert not result.valid
        assert "TEST_MISSING_X" in result.details.get("missing", [])

    def test_empty_value_counts_as_missing(
        self, validator: ConfigValidator, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_EMPTY", "")
        result = validator.validate_env_vars(["TEST_EMPTY"])
        assert not result.valid


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_state(self, validator: ConfigValidator) -> None:
        # Manually add something to internal lists to test reset
        validator._errors.append("test error")
        validator._warnings.append("test warning")

        validator.reset()
        assert validator._errors == []
        assert validator._warnings == []


# ---------------------------------------------------------------------------
# is_valid / validate_all
# ---------------------------------------------------------------------------


class TestAggregateValidation:
    def test_is_valid_true(
        self, validator: ConfigValidator, config_dir: Path, valid_config: dict
    ) -> None:
        path = _write_yaml(config_dir / "app.yaml", valid_config)
        assert validator.is_valid(path)

    def test_is_valid_false_for_bad_file(
        self, validator: ConfigValidator, config_dir: Path
    ) -> None:
        assert not validator.is_valid(config_dir / "nope.yaml")

    def test_validate_all_with_env_vars(
        self,
        validator: ConfigValidator,
        config_dir: Path,
        valid_config: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        path = _write_yaml(config_dir / "app.yaml", valid_config)
        monkeypatch.setenv("MY_KEY", "val")
        results = validator.validate_all(path, required_env_vars=["MY_KEY"])
        assert "config_file" in results
        assert "env_vars" in results
        assert all(r.valid for r in results.values())
