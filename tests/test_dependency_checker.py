"""dependency_checker 模块的单元测试。"""

from __future__ import annotations

import json
from unittest.mock import patch

from backend.tools.dependency_checker import DependencyChecker

# ---------------------------------------------------------------------------
# _classify_update
# ---------------------------------------------------------------------------


class TestClassifyUpdate:
    """版本分类逻辑测试。"""

    def test_major_upgrade(self) -> None:
        assert DependencyChecker._classify_update("1.0.0", "2.0.0") == "major"

    def test_minor_upgrade(self) -> None:
        assert DependencyChecker._classify_update("1.2.0", "1.3.0") == "minor"

    def test_patch_upgrade(self) -> None:
        assert DependencyChecker._classify_update("1.2.3", "1.2.4") == "patch"

    def test_two_part_version(self) -> None:
        assert DependencyChecker._classify_update("1.2", "1.3") == "minor"

    def test_invalid_version_falls_back_to_minor(self) -> None:
        assert DependencyChecker._classify_update("abc", "def") == "minor"


# ---------------------------------------------------------------------------
# check_outdated
# ---------------------------------------------------------------------------


class TestCheckOutdated:
    """过时依赖检查测试。"""

    @patch("subprocess.run")
    def test_success_with_outdated(self, mock_run: object) -> None:
        mock_run.return_value = _mock_completed(
            json.dumps(
                [
                    {
                        "name": "requests",
                        "version": "2.28.0",
                        "latest_version": "2.31.0",
                    },
                    {"name": "urllib3", "version": "1.26.0", "latest_version": "2.0.0"},
                ]
            )
        )
        checker = DependencyChecker()
        result = checker.check_outdated()

        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]["name"] == "requests"

    @patch("subprocess.run")
    def test_success_no_outdated(self, mock_run: object) -> None:
        mock_run.return_value = _mock_completed("[]")
        checker = DependencyChecker()
        result = checker.check_outdated()

        assert result.success is True
        assert result.data == []

    @patch("subprocess.run")
    def test_pip_error(self, mock_run: object) -> None:
        mock_run.return_value = _mock_completed(
            "", stderr="pip not found", returncode=1
        )
        checker = DependencyChecker()
        result = checker.check_outdated()

        assert result.success is False
        assert "pip not found" in result.message

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_pip_not_installed(self, mock_run: object) -> None:
        checker = DependencyChecker()
        result = checker.check_outdated()

        assert result.success is False
        assert "pip" in result.message


# ---------------------------------------------------------------------------
# check_security
# ---------------------------------------------------------------------------


class TestCheckSecurity:
    """安全漏洞检查测试。"""

    @patch("subprocess.run")
    def test_no_vulnerabilities(self, mock_run: object) -> None:
        mock_run.return_value = _mock_completed("No known vulnerabilities found")
        checker = DependencyChecker()
        result = checker.check_security()

        assert result.success is True
        assert result.data == []

    @patch("subprocess.run")
    def test_vulnerabilities_found(self, mock_run: object) -> None:
        mock_run.return_value = _mock_completed(
            json.dumps(
                [
                    {
                        "name": "urllib3",
                        "version": "1.26.0",
                        "vulns": [{"id": "PYSEC-2023-212"}],
                    }
                ]
            ),
            returncode=1,
        )
        checker = DependencyChecker()
        result = checker.check_security()

        assert result.success is True
        assert len(result.data) > 0

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_pip_audit_not_installed(self, mock_run: object) -> None:
        checker = DependencyChecker()
        result = checker.check_security()

        assert result.success is False
        assert "pip-audit" in result.message


# ---------------------------------------------------------------------------
# get_dependency_tree
# ---------------------------------------------------------------------------


class TestGetDependencyTree:
    """依赖树获取测试。"""

    @patch("subprocess.run")
    def test_success(self, mock_run: object) -> None:
        packages = [
            {"name": "fastapi", "version": "0.109.0"},
            {"name": "pydantic", "version": "2.5.3"},
        ]
        mock_run.return_value = _mock_completed(json.dumps(packages))
        checker = DependencyChecker()
        result = checker.get_dependency_tree()

        assert result.success is True
        assert len(result.data) == 2
        assert "2 个包" in result.message


# ---------------------------------------------------------------------------
# get_update_recommendations
# ---------------------------------------------------------------------------


class TestGetUpdateRecommendations:
    """更新建议测试。"""

    @patch("subprocess.run")
    def test_classifies_by_level(self, mock_run: object) -> None:
        outdated = [
            {
                "name": "fastapi",
                "version": "0.109.0",
                "latest_version": "0.110.0",
            },  # minor
            {"name": "httpx", "version": "0.26.0", "latest_version": "0.26.1"},  # patch
            {
                "name": "pydantic",
                "version": "2.5.3",
                "latest_version": "3.0.0",
            },  # major
        ]
        mock_run.return_value = _mock_completed(json.dumps(outdated))
        checker = DependencyChecker()
        result = checker.get_update_recommendations()

        assert result.success is True
        recs = result.data[0]
        assert len(recs["major"]) == 1
        assert len(recs["minor"]) == 1
        assert len(recs["patch"]) == 1


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class _MockCompletedProcess:
    """subprocess.CompletedProcess 的轻量替身。"""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _mock_completed(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> _MockCompletedProcess:
    """创建模拟的 CompletedProcess 对象。"""
    return _MockCompletedProcess(stdout=stdout, stderr=stderr, returncode=returncode)
