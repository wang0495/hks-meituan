"""代码审查器 -- 集成 Ruff、Mypy、Black、Radon 进行自动化代码审查。"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    """单项检查结果。"""

    name: str
    success: bool
    output: str = ""
    errors: str = ""
    error_message: str = ""

    @property
    def summary(self) -> str:
        """返回人类可读的一行摘要。"""
        if self.error_message:
            return f"[{self.name}] 工具不可用: {self.error_message}"
        status = "通过" if self.success else "发现问题"
        return f"[{self.name}] {status}"


@dataclass
class ReviewReport:
    """完整审查报告。"""

    results: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.success)


def _run_tool(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    """统一执行外部工具，捕获常见异常。"""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
    )


class CodeReviewer:
    """代码审查器，串联多种静态分析工具。"""

    def __init__(self, source_dir: str | Path = "backend") -> None:
        self._source_dir = Path(source_dir)
        if not self._source_dir.exists():
            raise FileNotFoundError(f"源码目录不存在: {self._source_dir}")

    # ------------------------------------------------------------------
    # 单项检查
    # ------------------------------------------------------------------

    def run_ruff_check(self) -> CheckResult:
        """运行 Ruff linter 检查。"""
        try:
            proc = _run_tool(["ruff", "check", str(self._source_dir)])
            return CheckResult(
                name="Ruff",
                success=proc.returncode == 0,
                output=proc.stdout,
                errors=proc.stderr,
            )
        except FileNotFoundError:
            return CheckResult(
                name="Ruff",
                success=False,
                error_message="ruff 未安装，请执行 pip install ruff",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(name="Ruff", success=False, error_message="执行超时")

    def run_mypy_check(self) -> CheckResult:
        """运行 Mypy 类型检查。"""
        try:
            proc = _run_tool(
                [
                    "mypy",
                    str(self._source_dir),
                    "--ignore-missing-imports",
                    "--no-error-summary",
                ]
            )
            return CheckResult(
                name="Mypy",
                success=proc.returncode == 0,
                output=proc.stdout,
                errors=proc.stderr,
            )
        except FileNotFoundError:
            return CheckResult(
                name="Mypy",
                success=False,
                error_message="mypy 未安装，请执行 pip install mypy",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(name="Mypy", success=False, error_message="执行超时")

    def run_black_check(self) -> CheckResult:
        """运行 Black 格式检查（只检查不修改）。"""
        try:
            proc = _run_tool(["black", "--check", "--diff", str(self._source_dir)])
            return CheckResult(
                name="Black",
                success=proc.returncode == 0,
                output=proc.stdout,
                errors=proc.stderr,
            )
        except FileNotFoundError:
            return CheckResult(
                name="Black",
                success=False,
                error_message="black 未安装，请执行 pip install black",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(name="Black", success=False, error_message="执行超时")

    def analyze_complexity(self) -> CheckResult:
        """使用 Radon 分析圈复杂度。"""
        try:
            proc = _run_tool(["radon", "cc", str(self._source_dir), "-s", "-n", "C"])
            return CheckResult(
                name="Radon-CC",
                success=proc.returncode == 0,
                output=proc.stdout,
                errors=proc.stderr,
            )
        except FileNotFoundError:
            return CheckResult(
                name="Radon-CC",
                success=False,
                error_message="radon 未安装，请执行 pip install radon",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(name="Radon-CC", success=False, error_message="执行超时")

    def analyze_maintainability(self) -> CheckResult:
        """使用 Radon 分析可维护性指数。"""
        try:
            proc = _run_tool(["radon", "mi", str(self._source_dir), "-s"])
            return CheckResult(
                name="Radon-MI",
                success=proc.returncode == 0,
                output=proc.stdout,
                errors=proc.stderr,
            )
        except FileNotFoundError:
            return CheckResult(
                name="Radon-MI",
                success=False,
                error_message="radon 未安装，请执行 pip install radon",
            )
        except subprocess.TimeoutExpired:
            return CheckResult(name="Radon-MI", success=False, error_message="执行超时")

    # ------------------------------------------------------------------
    # 汇总运行
    # ------------------------------------------------------------------

    def run_all(self) -> ReviewReport:
        """执行全部检查并返回汇总报告。"""
        report = ReviewReport()
        report.results.append(self.run_ruff_check())
        report.results.append(self.run_mypy_check())
        report.results.append(self.run_black_check())
        report.results.append(self.analyze_complexity())
        report.results.append(self.analyze_maintainability())
        return report
