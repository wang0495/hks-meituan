"""代码质量检查器 -- 集成 Ruff、Mypy、Black 进行质量检查并生成报告。"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class QualityCheckResult:
    """单项检查结果。"""

    name: str
    success: bool
    output: str = ""
    errors: str = ""
    error_message: str = ""
    duration_ms: float = 0.0

    @property
    def summary(self) -> str:
        """返回人类可读的一行摘要。"""
        if self.error_message:
            return f"[{self.name}] 工具不可用: {self.error_message}"
        status = "通过" if self.success else "发现问题"
        return f"[{self.name}] {status} ({self.duration_ms:.0f}ms)"


@dataclass
class QualityReport:
    """完整质量报告。"""

    ruff: QualityCheckResult | None = None
    mypy: QualityCheckResult | None = None
    black: QualityCheckResult | None = None
    results: list[QualityCheckResult] = field(default_factory=list)

    @property
    def overall_success(self) -> bool:
        """所有检查是否全部通过。"""
        return all(r.success for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results)


def _run_tool(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """统一执行外部工具。"""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _timed_check(name: str, cmd: list[str]) -> QualityCheckResult:
    """执行检查并记录耗时。"""
    start = time.monotonic()
    try:
        proc = _run_tool(cmd)
        elapsed = (time.monotonic() - start) * 1000
        return QualityCheckResult(
            name=name,
            success=proc.returncode == 0,
            output=proc.stdout,
            errors=proc.stderr,
            duration_ms=elapsed,
        )
    except FileNotFoundError:
        elapsed = (time.monotonic() - start) * 1000
        tool = cmd[0]
        return QualityCheckResult(
            name=name,
            success=False,
            error_message=f"{tool} 未安装，请执行 pip install {tool}",
            duration_ms=elapsed,
        )
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return QualityCheckResult(
            name=name,
            success=False,
            error_message="执行超时",
            duration_ms=elapsed,
        )


class QualityChecker:
    """代码质量检查器。"""

    def __init__(self, source_dir: str | Path = "backend") -> None:
        self._source_dir = Path(source_dir)
        if not self._source_dir.exists():
            raise FileNotFoundError(f"源码目录不存在: {self._source_dir}")

    def run_ruff(self) -> QualityCheckResult:
        """运行 Ruff linter 检查。"""
        return _timed_check(
            "Ruff",
            ["ruff", "check", str(self._source_dir)],
        )

    def run_mypy(self) -> QualityCheckResult:
        """运行 Mypy 类型检查。"""
        return _timed_check(
            "Mypy",
            [
                "mypy",
                str(self._source_dir),
                "--ignore-missing-imports",
                "--no-error-summary",
            ],
        )

    def run_black_check(self) -> QualityCheckResult:
        """运行 Black 格式检查（只检查不修改）。"""
        return _timed_check(
            "Black",
            ["black", "--check", "--diff", str(self._source_dir)],
        )

    def generate_report(self) -> QualityReport:
        """执行全部检查并生成质量报告。"""
        ruff_result = self.run_ruff()
        mypy_result = self.run_mypy()
        black_result = self.run_black_check()

        return QualityReport(
            ruff=ruff_result,
            mypy=mypy_result,
            black=black_result,
            results=[ruff_result, mypy_result, black_result],
        )
