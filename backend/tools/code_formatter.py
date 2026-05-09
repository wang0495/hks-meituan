"""代码格式化工具 - 集成 Black、Ruff、isort。"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class FormatResult:
    """格式化工具执行结果。"""

    tool: str
    success: bool
    output: str
    errors: str

    def to_dict(self) -> Dict[str, object]:
        """转换为字典。"""
        return {
            "tool": self.tool,
            "success": self.success,
            "output": self.output,
            "errors": self.errors,
        }


class CodeFormatter:
    """代码格式化工具，支持 Black、Ruff、isort。"""

    def __init__(
        self,
        target_dirs: Optional[List[str]] = None,
        project_root: Optional[Path] = None,
    ) -> None:
        """初始化格式化工具。

        Args:
            target_dirs: 要格式化的目标目录列表
            project_root: 项目根目录
        """
        self.target_dirs = target_dirs or ["backend/", "tests/"]
        self.project_root = project_root or Path.cwd()

    def run_black(self, check_only: bool = True) -> FormatResult:
        """运行 Black 格式化。

        Args:
            check_only: 仅检查不修改

        Returns:
            FormatResult: 执行结果
        """
        cmd = ["black"] + self.target_dirs

        if check_only:
            cmd.append("--check")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        return FormatResult(
            tool="black",
            success=result.returncode == 0,
            output=result.stdout,
            errors=result.stderr,
        )

    def run_ruff(self, fix: bool = False) -> FormatResult:
        """运行 Ruff 代码检查。

        Args:
            fix: 自动修复问题

        Returns:
            FormatResult: 执行结果
        """
        cmd = ["ruff", "check"] + self.target_dirs

        if fix:
            cmd.append("--fix")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        return FormatResult(
            tool="ruff",
            success=result.returncode == 0,
            output=result.stdout,
            errors=result.stderr,
        )

    def run_isort(self, check_only: bool = True) -> FormatResult:
        """运行 isort 导入排序。

        Args:
            check_only: 仅检查不修改

        Returns:
            FormatResult: 执行结果
        """
        cmd = ["isort"] + self.target_dirs

        if check_only:
            cmd.append("--check-only")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
        )

        return FormatResult(
            tool="isort",
            success=result.returncode == 0,
            output=result.stdout,
            errors=result.stderr,
        )

    def format_all(self) -> Dict[str, object]:
        """自动格式化所有代码（Black + Ruff fix + isort）。

        Returns:
            Dict: 各工具执行结果及总体状态
        """
        black = self.run_black(check_only=False)
        ruff = self.run_ruff(fix=True)
        isort = self.run_isort(check_only=False)

        return {
            "black": black.to_dict(),
            "ruff": ruff.to_dict(),
            "isort": isort.to_dict(),
            "overall": black.success and ruff.success and isort.success,
        }

    def check_all(self) -> Dict[str, object]:
        """检查所有代码格式（只读模式）。

        Returns:
            Dict: 各工具检查结果及总体状态
        """
        black = self.run_black(check_only=True)
        ruff = self.run_ruff(fix=False)
        isort = self.run_isort(check_only=True)

        return {
            "black": black.to_dict(),
            "ruff": ruff.to_dict(),
            "isort": isort.to_dict(),
            "overall": black.success and ruff.success and isort.success,
        }
