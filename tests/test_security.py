"""CityFlow 安全扫描器测试。

覆盖 SecurityScanner 的所有公共方法，使用 mock 避免依赖外部工具。
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

from backend.security.scanner import ScanResult, SecurityScanner


# ---------------------------------------------------------------------------
# ScanResult 数据类测试
# ---------------------------------------------------------------------------


class TestScanResult:
    """ScanResult 数据类的基本行为。"""

    def test_default_values(self) -> None:
        result = ScanResult(tool="test", success=True)
        assert result.tool == "test"
        assert result.success is True
        assert result.has_issues is False
        assert result.output == ""
        assert result.error == ""
        assert result.issues == []
        assert result.summary == ""

    def test_with_issues(self) -> None:
        issues = [{"file": "app.py", "line": 10, "message": "hardcoded password"}]
        result = ScanResult(
            tool="bandit",
            success=True,
            has_issues=True,
            issues=issues,
            summary="发现 1 个问题",
        )
        assert result.has_issues is True
        assert len(result.issues) == 1
        assert result.issues[0]["file"] == "app.py"


# ---------------------------------------------------------------------------
# SecurityScanner 初始化
# ---------------------------------------------------------------------------


class TestSecurityScannerInit:
    """Scanner 初始化与默认值。"""

    def test_default_target_dir(self) -> None:
        from pathlib import Path

        scanner = SecurityScanner()
        assert scanner._target_dir == Path("backend")

    def test_custom_target_dir(self) -> None:
        scanner = SecurityScanner(target_dir="src/app")
        assert scanner._target_dir.name == "app"

    def test_target_dir_as_path(self) -> None:
        from pathlib import Path

        scanner = SecurityScanner(target_dir=Path("some/path"))
        assert scanner._target_dir == Path("some/path")


# ---------------------------------------------------------------------------
# Bandit 扫描测试
# ---------------------------------------------------------------------------


class TestRunBandit:
    """Bandit 代码扫描。"""

    BANDIT_CLEAN_OUTPUT = json.dumps(
        {
            "results": [],
            "metrics": {"_totals": {"loc": 1000}},
        }
    )

    BANDIT_ISSUES_OUTPUT = json.dumps(
        {
            "results": [
                {
                    "filename": "backend/auth.py",
                    "line_number": 42,
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "test_id": "B105",
                    "issue_text": "Possible hardcoded password",
                },
                {
                    "filename": "backend/utils.py",
                    "line_number": 10,
                    "issue_severity": "MEDIUM",
                    "issue_confidence": "MEDIUM",
                    "test_id": "B301",
                    "issue_text": "Use of pickle",
                },
            ],
            "metrics": {"_totals": {"loc": 500}},
        }
    )

    @patch("backend.security.scanner.subprocess.run")
    def test_clean_scan(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self.BANDIT_CLEAN_OUTPUT,
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_bandit()

        assert result.success is True
        assert result.has_issues is False
        assert result.tool == "bandit"
        assert result.issues == []
        assert "未发现" in result.summary

    @patch("backend.security.scanner.subprocess.run")
    def test_scan_with_issues(self, mock_run: MagicMock) -> None:
        # bandit returns 1 when issues found
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=self.BANDIT_ISSUES_OUTPUT,
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_bandit()

        assert result.success is True  # returncode 1 is expected
        assert result.has_issues is True
        assert len(result.issues) == 2
        assert result.issues[0]["file"] == "backend/auth.py"
        assert result.issues[0]["severity"] == "HIGH"
        assert result.issues[1]["test"] == "B301"

    @patch("backend.security.scanner.subprocess.run")
    def test_bandit_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("bandit not found")
        scanner = SecurityScanner()
        result = scanner.run_bandit()

        assert result.success is False
        assert "未安装" in result.error

    @patch("backend.security.scanner.subprocess.run")
    def test_bandit_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bandit", timeout=300)
        scanner = SecurityScanner()
        result = scanner.run_bandit()

        assert result.success is False
        assert "超时" in result.error

    @patch("backend.security.scanner.subprocess.run")
    def test_bandit_invalid_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json {{{",
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_bandit()

        assert result.success is True
        assert result.has_issues is False
        assert result.output == "not valid json {{{"

    @patch("backend.security.scanner.subprocess.run")
    def test_bandit_passes_correct_args(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scanner = SecurityScanner(target_dir="myapp")
        scanner.run_bandit()

        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[0] == "bandit"
        assert "-r" in cmd
        assert "myapp" in cmd
        assert "-f" in cmd
        assert "json" in cmd

    @patch("backend.security.scanner.subprocess.run")
    def test_bandit_empty_stdout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scanner = SecurityScanner()
        result = scanner.run_bandit()

        assert result.success is True
        assert result.has_issues is False


# ---------------------------------------------------------------------------
# Safety 检查测试
# ---------------------------------------------------------------------------


class TestRunSafety:
    """Safety 依赖漏洞检查。"""

    SAFETY_CLEAN_OUTPUT = "[]"

    SAFETY_ISSUES_OUTPUT = json.dumps(
        [
            {
                "package": "requests",
                "installed_version": "2.25.0",
                "vulnerable_spec": "<2.31.0",
                "advisory": "Requests vulnerable to unintended proxy usage",
                "cve": "CVE-2023-32681",
            },
            {
                "package": "cryptography",
                "installed_version": "41.0.0",
                "vulnerable_spec": "<42.0.0",
                "advisory": "Memory corruption in PKCS12",
                "cve": "CVE-2024-26130",
            },
        ]
    )

    @patch("backend.security.scanner.subprocess.run")
    def test_clean_check(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self.SAFETY_CLEAN_OUTPUT,
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_safety()

        assert result.success is True
        assert result.has_issues is False
        assert result.tool == "safety"

    @patch("backend.security.scanner.subprocess.run")
    def test_check_with_vulnerabilities(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self.SAFETY_ISSUES_OUTPUT,
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_safety()

        assert result.success is True
        assert result.has_issues is True
        assert len(result.issues) == 2
        assert result.issues[0]["package"] == "requests"
        assert result.issues[0]["cve"] == "CVE-2023-32681"
        assert "漏洞" in result.summary

    @patch("backend.security.scanner.subprocess.run")
    def test_safety_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("safety not found")
        scanner = SecurityScanner()
        result = scanner.run_safety()

        assert result.success is False
        assert "未安装" in result.error

    @patch("backend.security.scanner.subprocess.run")
    def test_safety_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="safety", timeout=120)
        scanner = SecurityScanner()
        result = scanner.run_safety()

        assert result.success is False
        assert "超时" in result.error

    @patch("backend.security.scanner.subprocess.run")
    def test_safety_invalid_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="some error output",
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_safety()

        assert result.success is True
        assert result.has_issues is False

    @patch("backend.security.scanner.subprocess.run")
    def test_safety_empty_list(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        scanner = SecurityScanner()
        result = scanner.run_safety()

        assert result.success is True
        assert result.has_issues is False
        assert "安全" in result.summary


# ---------------------------------------------------------------------------
# pip-audit 审计测试
# ---------------------------------------------------------------------------


class TestRunPipAudit:
    """pip-audit 包审计。"""

    PIP_AUDIT_CLEAN = json.dumps({"dependencies": []})

    PIP_AUDIT_ISSUES = json.dumps(
        {
            "dependencies": [
                {
                    "name": "jinja2",
                    "version": "3.1.0",
                    "vulns": [
                        {
                            "id": "GHSA-xxxx",
                            "fix_versions": ["3.1.3"],
                            "description": "XSS vulnerability",
                        }
                    ],
                },
                {
                    "name": "urllib3",
                    "version": "1.26.0",
                    "vulns": [
                        {
                            "id": "GHSA-yyyy",
                            "fix_versions": ["1.26.18", "2.0.7"],
                            "description": "CRLF injection",
                        }
                    ],
                },
            ]
        }
    )

    @patch("backend.security.scanner.subprocess.run")
    def test_clean_audit(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self.PIP_AUDIT_CLEAN,
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_pip_audit()

        assert result.success is True
        assert result.has_issues is False
        assert result.tool == "pip-audit"

    @patch("backend.security.scanner.subprocess.run")
    def test_audit_with_vulnerabilities(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self.PIP_AUDIT_ISSUES,
            stderr="",
        )
        scanner = SecurityScanner()
        result = scanner.run_pip_audit()

        assert result.success is True
        assert result.has_issues is True
        assert len(result.issues) == 2
        assert result.issues[0]["name"] == "jinja2"
        assert len(result.issues[0]["vulns"]) == 1
        assert result.issues[0]["vulns"][0]["fix_versions"] == ["3.1.3"]

    @patch("backend.security.scanner.subprocess.run")
    def test_pip_audit_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError("pip-audit not found")
        scanner = SecurityScanner()
        result = scanner.run_pip_audit()

        assert result.success is False
        assert "未安装" in result.error

    @patch("backend.security.scanner.subprocess.run")
    def test_pip_audit_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pip-audit", timeout=120)
        scanner = SecurityScanner()
        result = scanner.run_pip_audit()

        assert result.success is False
        assert "超时" in result.error

    @patch("backend.security.scanner.subprocess.run")
    def test_pip_audit_invalid_json(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        scanner = SecurityScanner()
        result = scanner.run_pip_audit()

        assert result.success is True
        assert result.has_issues is False


# ---------------------------------------------------------------------------
# 综合报告测试
# ---------------------------------------------------------------------------


class TestGenerateReport:
    """generate_report 综合报告。"""

    @patch.object(SecurityScanner, "run_pip_audit")
    @patch.object(SecurityScanner, "run_safety")
    @patch.object(SecurityScanner, "run_bandit")
    def test_all_clean(
        self,
        mock_bandit: MagicMock,
        mock_safety: MagicMock,
        mock_pip_audit: MagicMock,
    ) -> None:
        mock_bandit.return_value = ScanResult(tool="bandit", success=True)
        mock_safety.return_value = ScanResult(tool="safety", success=True)
        mock_pip_audit.return_value = ScanResult(tool="pip-audit", success=True)

        scanner = SecurityScanner()
        report = scanner.generate_report()

        assert report["status"] == "clean"
        assert report["bandit"]["success"] is True
        assert report["bandit"]["has_issues"] is False
        assert report["safety"]["success"] is True
        assert report["pip_audit"]["success"] is True

    @patch.object(SecurityScanner, "run_pip_audit")
    @patch.object(SecurityScanner, "run_safety")
    @patch.object(SecurityScanner, "run_bandit")
    def test_issues_found(
        self,
        mock_bandit: MagicMock,
        mock_safety: MagicMock,
        mock_pip_audit: MagicMock,
    ) -> None:
        mock_bandit.return_value = ScanResult(
            tool="bandit",
            success=True,
            has_issues=True,
            issues=[{"file": "app.py", "line": 1}],
            summary="1 问题",
        )
        mock_safety.return_value = ScanResult(tool="safety", success=True)
        mock_pip_audit.return_value = ScanResult(tool="pip-audit", success=True)

        scanner = SecurityScanner()
        report = scanner.generate_report()

        assert report["status"] == "issues_found"
        assert report["bandit"]["has_issues"] is True
        assert len(report["bandit"]["issues"]) == 1

    @patch.object(SecurityScanner, "run_pip_audit")
    @patch.object(SecurityScanner, "run_safety")
    @patch.object(SecurityScanner, "run_bandit")
    def test_partial_failure(
        self,
        mock_bandit: MagicMock,
        mock_safety: MagicMock,
        mock_pip_audit: MagicMock,
    ) -> None:
        mock_bandit.return_value = ScanResult(
            tool="bandit", success=False, error="未安装"
        )
        mock_safety.return_value = ScanResult(tool="safety", success=True)
        mock_pip_audit.return_value = ScanResult(tool="pip-audit", success=True)

        scanner = SecurityScanner()
        report = scanner.generate_report()

        assert report["status"] == "partial_failure"
        assert report["bandit"]["success"] is False

    @patch.object(SecurityScanner, "run_pip_audit")
    @patch.object(SecurityScanner, "run_safety")
    @patch.object(SecurityScanner, "run_bandit")
    def test_issues_take_priority_over_partial_failure(
        self,
        mock_bandit: MagicMock,
        mock_safety: MagicMock,
        mock_pip_audit: MagicMock,
    ) -> None:
        """当同时有工具失败和发现问题时，状态应为 issues_found。"""
        mock_bandit.return_value = ScanResult(tool="bandit", success=False, error="err")
        mock_safety.return_value = ScanResult(
            tool="safety",
            success=True,
            has_issues=True,
            issues=[{"package": "flask"}],
        )
        mock_pip_audit.return_value = ScanResult(tool="pip-audit", success=True)

        scanner = SecurityScanner()
        report = scanner.generate_report()

        assert report["status"] == "issues_found"

    @patch.object(SecurityScanner, "run_pip_audit")
    @patch.object(SecurityScanner, "run_safety")
    @patch.object(SecurityScanner, "run_bandit")
    def test_report_contains_all_fields(
        self,
        mock_bandit: MagicMock,
        mock_safety: MagicMock,
        mock_pip_audit: MagicMock,
    ) -> None:
        mock_bandit.return_value = ScanResult(tool="bandit", success=True)
        mock_safety.return_value = ScanResult(tool="safety", success=True)
        mock_pip_audit.return_value = ScanResult(tool="pip-audit", success=True)

        scanner = SecurityScanner()
        report = scanner.generate_report()

        assert "status" in report
        assert "bandit" in report
        assert "safety" in report
        assert "pip_audit" in report

        for tool_key in ("bandit", "safety", "pip_audit"):
            tool_report = report[tool_key]
            assert "success" in tool_report
            assert "has_issues" in tool_report
            assert "summary" in tool_report
            assert "issues" in tool_report
            assert "error" in tool_report


# ---------------------------------------------------------------------------
# 模块导出测试
# ---------------------------------------------------------------------------


class TestModuleExports:
    """__init__.py 正确导出。"""

    def test_import_scanner(self) -> None:
        from backend.security import SecurityScanner

        assert SecurityScanner is not None

    def test_import_scan_result(self) -> None:
        from backend.security import ScanResult

        assert ScanResult is not None

    def test_all_exports(self) -> None:
        import backend.security as sec

        assert "SecurityScanner" in sec.__all__
        assert "ScanResult" in sec.__all__
