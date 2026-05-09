"""CityFlow 测试配置优化器：生成优化的 pytest / coverage 配置。

功能：
1. 生成优化的 pytest.ini 配置
2. 生成优化的 .coveragerc 配置
3. 提供 pytest-xdist / pytest-timeout 插件检测
4. 输出 pyproject.toml 兼容格式

用法：
    from backend.tools.test_config_optimizer import TestConfigOptimizer

    optimizer = TestConfigOptimizer()
    config = optimizer.get_optimized_config()

    # 写入 pytest.ini
    optimizer.write_pytest_ini()

    # 写入 pyproject.toml 的 [tool.pytest.ini_options] 段
    optimizer.write_pyproject_section()

CLI:
    python -m backend.tools.test_config_optimizer           # 打印优化配置
    python -m backend.tools.test_config_optimizer --write    # 写入文件
    python -m backend.tools.test_config_optimizer --check    # 检查当前配置
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["TestConfigOptimizer", "OptimizedConfig"]

ROOT = Path(__file__).resolve().parent.parent.parent

# 检测插件可用性
_HAS_XDIST = importlib.util.find_spec("xdist") is not None  # type: ignore[attr-defined]
_HAS_TIMEOUT = importlib.util.find_spec("pytest_timeout") is not None  # type: ignore[attr-defined]
_HAS_COV = importlib.util.find_spec("pytest_cov") is not None  # type: ignore[attr-defined]
_HAS_ASYNCIO = importlib.util.find_spec("pytest_asyncio") is not None  # type: ignore[attr-defined]


@dataclass
class OptimizedConfig:
    """优化后的测试配置。"""

    pytest: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    markers: dict[str, str] = field(default_factory=dict)
    plugins_detected: dict[str, bool] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)


class TestConfigOptimizer:
    """测试配置优化器。

    根据项目实际情况和已安装插件，生成最优的 pytest / coverage 配置。
    """

    def __init__(self, *, detect_plugins: bool = True) -> None:
        self._detect_plugins = detect_plugins
        self._plugins = self._detect_available_plugins() if detect_plugins else {}

    # ------------------------------------------------------------------
    # 配置生成
    # ------------------------------------------------------------------

    def get_optimized_config(self) -> OptimizedConfig:
        """获取优化配置。

        Returns:
            OptimizedConfig 实例，包含 pytest / coverage / markers 配置
        """
        pytest_cfg = self._build_pytest_config()
        coverage_cfg = self._build_coverage_config()
        markers = self._build_markers()
        suggestions = self._generate_suggestions()

        return OptimizedConfig(
            pytest=pytest_cfg,
            coverage=coverage_cfg,
            markers=markers,
            plugins_detected=self._plugins,
            suggestions=suggestions,
        )

    def get_pytest_ini_content(self) -> str:
        """生成 pytest.ini 文件内容。

        Returns:
            pytest.ini 的完整文本内容
        """
        config = self.get_optimized_config()
        lines = ["[pytest]"]

        # addopts
        if "addopts" in config.pytest:
            lines.append(f"addopts = {config.pytest['addopts']}")

        # testpaths
        if "testpaths" in config.pytest:
            paths = " ".join(config.pytest["testpaths"])
            lines.append(f"testpaths = {paths}")

        # python_files / python_classes / python_functions
        for key in ("python_files", "python_classes", "python_functions"):
            if key in config.pytest:
                lines.append(f"{key} = {config.pytest[key]}")

        # asyncio_mode
        if "asyncio_mode" in config.pytest:
            lines.append(f"asyncio_mode = {config.pytest['asyncio_mode']}")

        # timeout
        if "timeout" in config.pytest:
            lines.append(f"timeout = {config.pytest['timeout']}")

        # markers
        if config.markers:
            lines.append("markers =")
            for name, desc in config.markers.items():
                lines.append(f"    {name}: {desc}")

        return "\n".join(lines) + "\n"

    def get_pyproject_section(self) -> str:
        """生成 pyproject.toml 的 [tool.pytest.ini_options] 段。

        Returns:
            TOML 格式的配置段
        """
        config = self.get_optimized_config()
        lines = ["[tool.pytest.ini_options]"]

        if "addopts" in config.pytest:
            opts = config.pytest["addopts"]
            lines.append(f'addopts = "{opts}"')

        if "testpaths" in config.pytest:
            paths = config.pytest["testpaths"]
            paths_str = ", ".join(f'"{p}"' for p in paths)
            lines.append(f"testpaths = [{paths_str}]")

        for key in ("python_files", "python_classes", "python_functions"):
            if key in config.pytest:
                lines.append(f'{key} = "{config.pytest[key]}"')

        if "asyncio_mode" in config.pytest:
            lines.append(f'asyncio_mode = "{config.pytest["asyncio_mode"]}"')

        if "timeout" in config.pytest:
            lines.append(f"timeout = {config.pytest['timeout']}")

        if config.markers:
            lines.append("markers = [")
            for name, desc in config.markers.items():
                lines.append(f'    "{name}: {desc}",')
            lines.append("]")

        # coverage 段
        lines.append("")
        lines.append("[tool.coverage.run]")
        cov_run = config.coverage.get("run", {})
        if "source" in cov_run:
            sources = ", ".join(f'"{s}"' for s in cov_run["source"])
            lines.append(f"source = [{sources}]")
        if "omit" in cov_run:
            omits = ", ".join(f'"{o}"' for o in cov_run["omit"])
            lines.append(f"omit = [{omits}]")

        lines.append("")
        lines.append("[tool.coverage.report]")
        cov_report = config.coverage.get("report", {})
        if "exclude_lines" in cov_report:
            excludes = ", ".join(f'"{e}"' for e in cov_report["exclude_lines"])
            lines.append(f"exclude_lines = [{excludes}]")
        if "fail_under" in cov_report:
            lines.append(f"fail_under = {cov_report['fail_under']}")

        return "\n".join(lines) + "\n"

    def get_coveragerc_content(self) -> str:
        """生成 .coveragerc 文件内容。

        Returns:
            .coveragerc 的完整文本内容
        """
        config = self.get_optimized_config()
        lines = ["[run]"]

        cov_run = config.coverage.get("run", {})
        if "source" in cov_run:
            for s in cov_run["source"]:
                lines.append(f"source = {s}")
        if "omit" in cov_run:
            lines.append("omit =")
            for o in cov_run["omit"]:
                lines.append(f"    {o}")

        lines.append("")
        lines.append("[report]")

        cov_report = config.coverage.get("report", {})
        if "exclude_lines" in cov_report:
            lines.append("exclude_lines =")
            for e in cov_report["exclude_lines"]:
                lines.append(f"    {e}")
        if "fail_under" in cov_report:
            lines.append(f"fail_under = {cov_report['fail_under']}")

        lines.append("")
        lines.append("[html]")
        lines.append("directory = coverage_html")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # 配置检查
    # ------------------------------------------------------------------

    def check_current_config(self) -> dict[str, Any]:
        """检查当前 pytest.ini / pyproject.toml 配置，与优化配置对比。

        Returns:
            检查结果字典
        """
        current_ini = ROOT / "pytest.ini"
        current_pyproject = ROOT / "pyproject.toml"

        issues: list[str] = []
        info: list[str] = []

        # 检查 pytest.ini
        if current_ini.exists():
            content = current_ini.read_text(encoding="utf-8")
            if "--dist=loadfile" not in content and _HAS_XDIST:
                issues.append("未配置 --dist=loadfile（pytest-xdist 已安装）")
            if "timeout" not in content and _HAS_TIMEOUT:
                issues.append("未配置 timeout（pytest-timeout 已安装）")
            if "asyncio_mode" not in content and _HAS_ASYNCIO:
                issues.append("未配置 asyncio_mode（pytest-asyncio 已安装）")
            info.append(f"当前使用 pytest.ini: {current_ini}")
        elif current_pyproject.exists():
            info.append(f"当前使用 pyproject.toml: {current_pyproject}")
        else:
            issues.append("未找到 pytest.ini 或 pyproject.toml 中的 pytest 配置")

        # 检查插件
        missing_plugins: list[str] = []
        if not _HAS_XDIST:
            missing_plugins.append("pytest-xdist（并行执行）")
        if not _HAS_TIMEOUT:
            missing_plugins.append("pytest-timeout（超时控制）")
        if not _HAS_COV:
            missing_plugins.append("pytest-cov（覆盖率收集）")
        if not _HAS_ASYNCIO:
            missing_plugins.append("pytest-asyncio（异步测试）")

        if missing_plugins:
            issues.append(f"缺少插件: {', '.join(missing_plugins)}")

        return {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "info": info,
            "plugins": self._plugins,
        }

    # ------------------------------------------------------------------
    # 写入文件
    # ------------------------------------------------------------------

    def write_pytest_ini(self, path: Path | None = None) -> Path:
        """写入优化后的 pytest.ini。

        Args:
            path: 输出路径，默认项目根目录/pytest.ini

        Returns:
            写入的文件路径
        """
        target = path or (ROOT / "pytest.ini")
        content = self.get_pytest_ini_content()
        target.write_text(content, encoding="utf-8")
        logger.info("已写入 pytest.ini: %s", target)
        return target

    def write_coveragerc(self, path: Path | None = None) -> Path:
        """写入优化后的 .coveragerc。

        Args:
            path: 输出路径，默认项目根目录/.coveragerc

        Returns:
            写入的文件路径
        """
        target = path or (ROOT / ".coveragerc")
        content = self.get_coveragerc_content()
        target.write_text(content, encoding="utf-8")
        logger.info("已写入 .coveragerc: %s", target)
        return target

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _detect_available_plugins(self) -> dict[str, bool]:
        """检测可用的 pytest 插件。"""
        plugins = {
            "pytest-xdist": _HAS_XDIST,
            "pytest-timeout": _HAS_TIMEOUT,
            "pytest-cov": _HAS_COV,
            "pytest-asyncio": _HAS_ASYNCIO,
        }

        # 额外检测
        for spec_name, display_name in [
            ("pytest_mock", "pytest-mock"),
            ("pytest_randomly", "pytest-randomly"),
            ("pytest_repeat", "pytest-repeat"),
            ("pytest_benchmark", "pytest-benchmark"),
            ("pytest_html", "pytest-html"),
        ]:
            plugins[display_name] = importlib.util.find_spec(spec_name) is not None  # type: ignore[attr-defined]

        return plugins

    def _build_pytest_config(self) -> dict[str, Any]:
        """构建 pytest 配置。"""
        # 构建 addopts
        addopts_parts: list[str] = []

        if _HAS_XDIST:
            addopts_parts.extend(["-n", "auto", "--dist=loadfile"])

        if _HAS_TIMEOUT:
            addopts_parts.append("--timeout=300")

        addopts_parts.extend(["-v", "--tb=short"])

        config: dict[str, Any] = {
            "addopts": " ".join(addopts_parts),
            "testpaths": ["tests", "backend/tests"],
            "python_files": "test_*.py",
            "python_classes": "Test*",
            "python_functions": "test_*",
        }

        if _HAS_ASYNCIO:
            config["asyncio_mode"] = "auto"

        if _HAS_TIMEOUT:
            config["timeout"] = 300

        return config

    def _build_coverage_config(self) -> dict[str, Any]:
        """构建 coverage 配置。"""
        return {
            "run": {
                "source": ["backend"],
                "omit": [
                    "*/tests/*",
                    "*/test_*",
                    "*/migrations/*",
                    "*/__pycache__/*",
                    "*/conftest.py",
                    "*/alembic/*",
                ],
            },
            "report": {
                "exclude_lines": [
                    "pragma: no cover",
                    "def __repr__",
                    "if __name__ == .__main__.",
                    "raise NotImplementedError",
                    "pass",
                    "\\.\\.\\.",
                    "if TYPE_CHECKING:",
                    "if typing.TYPE_CHECKING:",
                ],
                "fail_under": 60,
            },
        }

    def _build_markers(self) -> dict[str, str]:
        """构建 pytest markers 定义。"""
        return {
            "slow": "慢速测试（deselect with '-m \"not slow\"'）",
            "integration": "集成测试（需要外部依赖）",
            "e2e": "端到端测试",
            "unit": "单元测试",
            "smoke": "冒烟测试（快速验证核心功能）",
        }

    def _generate_suggestions(self) -> list[str]:
        """生成配置优化建议。"""
        suggestions: list[str] = []

        if not _HAS_XDIST:
            suggestions.append(
                "安装 pytest-xdist 可大幅提升测试速度: pip install pytest-xdist"
            )

        if not _HAS_TIMEOUT:
            suggestions.append(
                "安装 pytest-timeout 可防止测试挂起: pip install pytest-timeout"
            )

        if not _HAS_COV:
            suggestions.append(
                "安装 pytest-cov 可自动生成覆盖率报告: pip install pytest-cov"
            )

        if not _HAS_ASYNCIO:
            suggestions.append(
                "安装 pytest-asyncio 可支持异步测试: pip install pytest-asyncio"
            )

        # 检查当前配置文件
        ini_path = ROOT / "pytest.ini"
        if ini_path.exists():
            content = ini_path.read_text(encoding="utf-8")
            if "-n auto" not in content and _HAS_XDIST:
                suggestions.append(
                    "pytest.ini 中未启用并行执行，建议添加 -n auto --dist=loadfile"
                )

        return suggestions


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI 入口。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="CityFlow 测试配置优化器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.test_config_optimizer           # 打印优化配置
  python -m backend.tools.test_config_optimizer --write    # 写入文件
  python -m backend.tools.test_config_optimizer --check    # 检查当前配置
  python -m backend.tools.test_config_optimizer --format pyproject  # pyproject.toml 格式
        """,
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="写入 pytest.ini 和 .coveragerc 文件",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="检查当前配置并给出建议",
    )
    parser.add_argument(
        "--format",
        choices=["ini", "pyproject", "coveragerc"],
        default="ini",
        help="输出格式（默认 ini）",
    )

    args = parser.parse_args()

    optimizer = TestConfigOptimizer()

    # 检查模式
    if args.check:
        result = optimizer.check_current_config()
        print("\n配置检查结果:")
        print("=" * 50)

        if result["info"]:
            print("\n信息:")
            for info in result["info"]:
                print(f"  [INFO] {info}")

        if result["issues"]:
            print("\n问题:")
            for issue in result["issues"]:
                print(f"  [WARN] {issue}")
        else:
            print("\n  当前配置无明显问题")

        print("\n已安装插件:")
        for name, available in result["plugins"].items():
            status = "OK" if available else "MISSING"
            print(f"  [{status}] {name}")

        return

    # 写入模式
    if args.write:
        ini_path = optimizer.write_pytest_ini()
        print(f"已写入: {ini_path}")

        cov_path = optimizer.write_coveragerc()
        print(f"已写入: {cov_path}")

        # 打印建议
        config = optimizer.get_optimized_config()
        if config.suggestions:
            print("\n优化建议:")
            for s in config.suggestions:
                print(f"  - {s}")
        return

    # 打印模式
    if args.format == "ini":
        print(optimizer.get_pytest_ini_content())
    elif args.format == "pyproject":
        print(optimizer.get_pyproject_section())
    elif args.format == "coveragerc":
        print(optimizer.get_coveragerc_content())

    # 打印插件检测和建议
    config = optimizer.get_optimized_config()

    print("\n# 插件检测:")
    for name, available in config.plugins_detected.items():
        status = "OK" if available else "MISSING"
        print(f"#   [{status}] {name}")

    if config.suggestions:
        print("\n# 优化建议:")
        for s in config.suggestions:
            print(f"#   - {s}")


if __name__ == "__main__":
    main()
