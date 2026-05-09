# backend/tools/integration_test.py

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent


class IntegrationTestRunner:
    """集成测试运行器"""

    def __init__(self) -> None:
        self._results: List[Dict[str, object]] = []

    def run_all_tests(self) -> Dict[str, object]:
        """运行所有测试"""
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr,
        }

    def run_integration_tests(self) -> Dict[str, object]:
        """运行集成测试"""
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_integration.py", "-v"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr,
        }

    def run_api_tests(self) -> Dict[str, object]:
        """运行API测试"""
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_api_mock.py", "-v"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr,
        }

    def generate_report(self) -> Dict[str, object]:
        """生成报告"""
        all_tests = self.run_all_tests()
        integration = self.run_integration_tests()
        api = self.run_api_tests()

        return {
            "all_tests": all_tests,
            "integration": integration,
            "api": api,
            "overall": (
                bool(all_tests["success"])
                and bool(integration["success"])
                and bool(api["success"])
            ),
        }
