"""CityFlow 安全扫描器。

集成多种安全扫描工具：
- **Bandit** — Python 代码安全分析
- **Safety** — 依赖漏洞检查
- **pip-audit** — 包审计

依赖安装::

    pip install bandit safety pip-audit
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 项目根目录（backend/ 的父目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class ScanResult:
    """单次扫描结果。"""

    tool: str
    """扫描工具名称。"""

    success: bool
    """扫描是否成功执行（无报错）。"""

    has_issues: bool = False
    """是否发现安全问题。"""

    output: str = ""
    """工具原始输出。"""

    error: str = ""
    """错误信息。"""

    issues: list[dict[str, Any]] = field(default_factory=list)
    """解析后的结构化问题列表。"""

    summary: str = ""
    """摘要信息。"""


class SecurityScanner:
    """安全扫描器 —— 统一调度多种安全扫描工具。

    用法::

        scanner = SecurityScanner()
        report = scanner.generate_report()
    """

    def __init__(self, target_dir: str | Path = "backend") -> None:
        """初始化扫描器。

        Args:
            target_dir: 要扫描的目录路径（相对于项目根目录）。
        """
        self._target_dir = Path(target_dir)
        self._tools_checked = False

    # ------------------------------------------------------------------
    # Bandit —— 代码安全扫描
    # ------------------------------------------------------------------

    def run_bandit(self) -> ScanResult:
        """运行 Bandit 代码安全扫描。

        Returns:
            ScanResult 包含扫描结果。
        """
        try:
            result = subprocess.run(
                [
                    "bandit",
                    "-r",
                    str(self._target_dir),
                    "-f",
                    "json",
                    "--severity-level",
                    "medium",
                ],
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                timeout=300,
            )

            issues: list[dict[str, Any]] = []
            output = result.stdout.strip()

            if output:
                try:
                    data = json.loads(output)
                    raw_issues = data.get("results", [])
                    issues = [
                        {
                            "file": item.get("filename", ""),
                            "line": item.get("line_number", 0),
                            "severity": item.get("issue_severity", ""),
                            "confidence": item.get("issue_confidence", ""),
                            "test": item.get("test_id", ""),
                            "message": item.get("issue_text", ""),
                        }
                        for item in raw_issues
                    ]
                except json.JSONDecodeError:
                    logger.warning("Bandit 输出不是合法 JSON，使用原始文本")

            has_issues = len(issues) > 0

            summary = f"发现 {len(issues)} 个问题" if has_issues else "未发现安全问题"

            return ScanResult(
                tool="bandit",
                success=result.returncode == 0 or result.returncode == 1,
                has_issues=has_issues,
                output=output,
                error=result.stderr.strip(),
                issues=issues,
                summary=summary,
            )

        except FileNotFoundError:
            logger.error("bandit 未安装，请运行: pip install bandit")
            return ScanResult(
                tool="bandit",
                success=False,
                error="bandit 未安装，请运行: pip install bandit",
            )
        except subprocess.TimeoutExpired:
            logger.error("Bandit 扫描超时（300s）")
            return ScanResult(
                tool="bandit",
                success=False,
                error="扫描超时（300s）",
            )

    # ------------------------------------------------------------------
    # Safety —— 依赖漏洞检查
    # ------------------------------------------------------------------

    def run_safety(self) -> ScanResult:
        """运行 Safety 依赖漏洞检查。

        Returns:
            ScanResult 包含检查结果。
        """
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                timeout=120,
            )

            issues: list[dict[str, Any]] = []
            output = result.stdout.strip()

            if output:
                try:
                    raw_issues = json.loads(output)
                    if isinstance(raw_issues, list):
                        issues = [
                            {
                                "package": item.get("package", ""),
                                "installed": item.get("installed_version", ""),
                                "vulnerable": item.get("vulnerable_spec", ""),
                                "advisory": item.get("advisory", ""),
                                "cve": item.get("cve", ""),
                            }
                            for item in raw_issues
                        ]
                except json.JSONDecodeError:
                    logger.warning("Safety 输出不是合法 JSON，使用原始文本")

            has_issues = len(issues) > 0

            return ScanResult(
                tool="safety",
                success=True,
                has_issues=has_issues,
                output=output,
                error=result.stderr.strip(),
                issues=issues,
                summary=(f"发现 {len(issues)} 个漏洞" if has_issues else "依赖安全，无已知漏洞"),
            )

        except FileNotFoundError:
            logger.error("safety 未安装，请运行: pip install safety")
            return ScanResult(
                tool="safety",
                success=False,
                error="safety 未安装，请运行: pip install safety",
            )
        except subprocess.TimeoutExpired:
            logger.error("Safety 检查超时（120s）")
            return ScanResult(
                tool="safety",
                success=False,
                error="检查超时（120s）",
            )

    # ------------------------------------------------------------------
    # pip-audit —— 包审计
    # ------------------------------------------------------------------

    def run_pip_audit(self) -> ScanResult:
        """运行 pip-audit 包审计。

        Returns:
            ScanResult 包含审计结果。
        """
        try:
            result = subprocess.run(
                ["pip-audit", "--format=json"],
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
                timeout=120,
            )

            issues: list[dict[str, Any]] = []
            output = result.stdout.strip()

            if output:
                try:
                    raw_data = json.loads(output)
                    raw_issues = raw_data.get("dependencies", [])
                    issues = [
                        {
                            "name": item.get("name", ""),
                            "version": item.get("version", ""),
                            "vulns": [
                                {
                                    "id": v.get("id", ""),
                                    "fix_versions": v.get("fix_versions", []),
                                    "description": v.get("description", ""),
                                }
                                for v in item.get("vulns", [])
                            ],
                        }
                        for item in raw_issues
                        if item.get("vulns")
                    ]
                except json.JSONDecodeError:
                    logger.warning("pip-audit 输出不是合法 JSON，使用原始文本")

            has_issues = len(issues) > 0

            return ScanResult(
                tool="pip-audit",
                success=True,
                has_issues=has_issues,
                output=output,
                error=result.stderr.strip(),
                issues=issues,
                summary=(f"发现 {len(issues)} 个包存在漏洞" if has_issues else "所有包安全"),
            )

        except FileNotFoundError:
            logger.error("pip-audit 未安装，请运行: pip install pip-audit")
            return ScanResult(
                tool="pip-audit",
                success=False,
                error="pip-audit 未安装，请运行: pip install pip-audit",
            )
        except subprocess.TimeoutExpired:
            logger.error("pip-audit 审计超时（120s）")
            return ScanResult(
                tool="pip-audit",
                success=False,
                error="审计超时（120s）",
            )

    # ------------------------------------------------------------------
    # 综合报告
    # ------------------------------------------------------------------

    def generate_report(self) -> dict[str, Any]:
        """运行所有扫描工具并生成综合安全报告。

        Returns:
            包含各工具扫描结果和总体评估的字典。
        """
        logger.info("开始安全扫描...")

        bandit_result = self.run_bandit()
        safety_result = self.run_safety()
        pip_audit_result = self.run_pip_audit()

        # 判断整体状态
        all_succeeded = all(r.success for r in [bandit_result, safety_result, pip_audit_result])
        any_issues = any(r.has_issues for r in [bandit_result, safety_result, pip_audit_result])

        if any_issues:
            status = "issues_found"
        elif not all_succeeded:
            status = "partial_failure"
        else:
            status = "clean"

        return {
            "status": status,
            "bandit": {
                "success": bandit_result.success,
                "has_issues": bandit_result.has_issues,
                "summary": bandit_result.summary,
                "issues": bandit_result.issues,
                "error": bandit_result.error,
            },
            "safety": {
                "success": safety_result.success,
                "has_issues": safety_result.has_issues,
                "summary": safety_result.summary,
                "issues": safety_result.issues,
                "error": safety_result.error,
            },
            "pip_audit": {
                "success": pip_audit_result.success,
                "has_issues": pip_audit_result.has_issues,
                "summary": pip_audit_result.summary,
                "issues": pip_audit_result.issues,
                "error": pip_audit_result.error,
            },
        }
