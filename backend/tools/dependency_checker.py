"""CityFlow 依赖检查工具。

检查项目依赖的版本状态、安全漏洞和更新建议。

功能：
    - 检查过时依赖（pip list --outdated）
    - 安全漏洞扫描（pip-audit）
    - 依赖树统计（pip list）

依赖：
    - pip（Python 自带）
    - pip-audit（可选，用于安全扫描）
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OutdatedPackage:
    """过时的包信息。"""

    name: str
    version: str
    latest_version: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    """检查操作的统一返回结果。"""

    success: bool
    message: str = ""
    data: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 检查器
# ---------------------------------------------------------------------------


class DependencyChecker:
    """依赖检查器。

    Parameters
    ----------
    requirements_file : str
        requirements.txt 文件路径，默认为当前目录下的 requirements.txt。
    """

    def __init__(self, requirements_file: str = "requirements.txt") -> None:
        self._requirements_file = Path(requirements_file)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def check_outdated(self) -> CheckResult:
        """检查过时依赖。

        调用 `pip list --outdated --format=json` 获取过时包列表。

        Returns
        -------
        CheckResult
            success=True 时 data 包含 OutdatedPackage 字典列表，
            success=False 时 message 包含错误信息。
        """
        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return CheckResult(success=False, message="pip 未安装或不在 PATH 中")

        if result.returncode != 0:
            return CheckResult(success=False, message=result.stderr.strip())

        try:
            outdated: list[dict[str, str]] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return CheckResult(success=False, message=f"JSON 解析失败: {exc}")

        return CheckResult(
            success=True,
            message=f"发现 {len(outdated)} 个过时依赖",
            data=outdated,
        )

    def check_security(self) -> CheckResult:
        """检查安全漏洞。

        调用 `pip-audit` 扫描已安装包的已知漏洞。

        Returns
        -------
        CheckResult
            success=True 且 data 为空表示无漏洞；
            success=True 且 data 非空表示发现漏洞；
            success=False 时 message 包含错误信息。
        """
        try:
            result = subprocess.run(
                ["pip-audit"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return CheckResult(
                success=False,
                message="pip-audit 未安装，请运行: pip install pip-audit",
            )

        if result.returncode == 0:
            return CheckResult(success=True, message="未发现安全漏洞")

        # pip-audit 非零退出码表示发现漏洞或运行出错
        # 尝试解析 JSON 输出（pip-audit --format=json）
        vulns = self._parse_audit_output(result.stdout)
        return CheckResult(
            success=True,
            message=f"发现 {len(vulns)} 个安全漏洞",
            data=vulns,
        )

    def get_dependency_tree(self) -> CheckResult:
        """获取已安装依赖列表及数量。

        调用 `pip list --format=json` 获取所有已安装包。

        Returns
        -------
        CheckResult
            success=True 时 data 包含包信息字典列表，
            message 包含包数量摘要。
        """
        try:
            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return CheckResult(success=False, message="pip 未安装或不在 PATH 中")

        if result.returncode != 0:
            return CheckResult(success=False, message=result.stderr.strip())

        try:
            packages: list[dict[str, str]] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return CheckResult(success=False, message=f"JSON 解析失败: {exc}")

        return CheckResult(
            success=True,
            message=f"已安装 {len(packages)} 个包",
            data=packages,
        )

    def get_update_recommendations(self) -> CheckResult:
        """获取依赖更新建议。

        综合过时检查结果，生成分级更新建议：
        - major: 主版本升级（可能有破坏性变更）
        - minor: 次版本升级（新功能，向后兼容）
        - patch: 补丁升级（bug 修复）

        Returns
        -------
        CheckResult
            data 包含 major/minor/patch 三个键的字典。
        """
        outdated_result = self.check_outdated()
        if not outdated_result.success:
            return outdated_result

        recommendations: dict[str, list[dict[str, str]]] = {
            "major": [],
            "minor": [],
            "patch": [],
        }

        for pkg in outdated_result.data:
            category = self._classify_update(
                pkg.get("version", ""),
                pkg.get("latest_version", ""),
            )
            recommendations[category].append(pkg)

        total = sum(len(v) for v in recommendations.values())
        return CheckResult(
            success=True,
            message=f"生成 {total} 条更新建议",
            data=[recommendations],  # 包装为单元素列表以保持 data 类型一致
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_update(current: str, latest: str) -> str:
        """根据版本号判断更新级别。

        Parameters
        ----------
        current : str
            当前版本号，如 "1.2.3"。
        latest : str
            最新版本号，如 "2.0.0"。

        Returns
        -------
        str
            "major" / "minor" / "patch"。
        """
        try:
            cur_parts = [int(p) for p in current.split(".")[:3]]
            lat_parts = [int(p) for p in latest.split(".")[:3]]
        except (ValueError, IndexError):
            return "minor"  # 无法解析时归为 minor

        if lat_parts[0] > cur_parts[0]:
            return "major"
        if len(lat_parts) > 1 and len(cur_parts) > 1 and lat_parts[1] > cur_parts[1]:
            return "minor"
        return "patch"

    @staticmethod
    def _parse_audit_output(output: str) -> list[dict[str, str]]:
        """解析 pip-audit 的文本输出为结构化数据。

        尝试 JSON 解析，失败则逐行提取关键信息。

        Parameters
        ----------
        output : str
            pip-audit 的标准输出。

        Returns
        -------
        list[dict[str, str]]
            漏洞信息列表。
        """
        # 先尝试 JSON 解析
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "dependencies" in data:
                return [dep for dep in data["dependencies"] if dep.get("vulns")]
        except json.JSONDecodeError:
            pass

        # 降级：逐行解析文本输出
        vulns: list[dict[str, str]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("="):
                continue
            # 典型格式: package_name  version  vulnerability_id  description
            parts = line.split()
            if len(parts) >= 3:
                vulns.append(
                    {
                        "name": parts[0],
                        "version": parts[1],
                        "vuln_id": parts[2],
                        "description": " ".join(parts[3:]) if len(parts) > 3 else "",
                    }
                )
        return vulns
