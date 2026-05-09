"""CityFlow 变更日志生成器。

支持两种模式：
1. 手动添加版本及变更条目
2. 从 Git 提交历史自动生成
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 变更类型中文映射
# ---------------------------------------------------------------------------

_TYPE_CN: dict[str, str] = {
    "added": "新增",
    "fixed": "修复",
    "changed": "变更",
    "removed": "移除",
}


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------


class ChangelogGenerator:
    """变更日志生成器。

    读写 CHANGELOG.md，支持手动追加版本或从 Git 日志生成。

    Parameters
    ----------
    changelog_file : str
        变更日志文件路径，默认为当前目录下的 CHANGELOG.md。
    """

    def __init__(self, changelog_file: str = "CHANGELOG.md") -> None:
        self._file = Path(changelog_file)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def add_version(
        self,
        version: str,
        changes: list[dict[str, str]],
        date: str | None = None,
    ) -> None:
        """向变更日志追加一个新版本。

        Parameters
        ----------
        version : str
            语义化版本号，如 "1.2.0"。
        changes : list[dict[str, str]]
            变更列表，每项需包含 "type" 和 "description"。
            type 取值：added / fixed / changed / removed。
        date : str | None
            日期字符串，默认使用当天。
        """
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        section = self._build_section(version, date, changes)
        self._prepend_section(section)

    def generate_from_git(
        self,
        last_tag: str | None = None,
    ) -> list[dict[str, str]]:
        """从 Git 提交历史提取变更条目。

        解析 conventional commits 格式（type: description），
        将 commit type 映射为变更类型。

        Parameters
        ----------
        last_tag : str | None
            起始 tag，为空则读取全部历史。

        Returns
        -------
        list[dict[str, str]]
            变更列表，每项含 "type" 和 "description"。
        """
        commits = self._get_git_commits(last_tag)
        return self._parse_commits(commits)

    def generate_from_commits(
        self,
        commits: list[str],
    ) -> list[dict[str, str]]:
        """从 commit 列表提取变更条目（便于测试）。"""
        return self._parse_commits(commits)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_section(
        self,
        version: str,
        date: str,
        changes: list[dict[str, str]],
    ) -> str:
        """构建单个版本的 Markdown 文本。"""
        lines = [f"## [{version}] - {date}", ""]

        # 按类型分组
        grouped: dict[str, list[str]] = {}
        for change in changes:
            ctype = change.get("type", "changed")
            desc = change.get("description", "")
            grouped.setdefault(ctype, []).append(desc)

        for ctype, descs in grouped.items():
            cn = _TYPE_CN.get(ctype, ctype)
            lines.append(f"### {cn}")
            for desc in descs:
                lines.append(f"- {desc}")
            lines.append("")

        return "\n".join(lines)

    def _prepend_section(self, section: str) -> None:
        """将新版本内容插入到文件头部。"""
        header = "# Changelog\n\n"
        existing = ""

        if self._file.exists():
            existing = self._file.read_text(encoding="utf-8")
            # 如果文件已包含 Changelog 标题，去掉重复
            if existing.startswith("# Changelog"):
                existing = existing[len(header) :]

        new_content = f"{header}{section}\n{existing}".rstrip() + "\n"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(new_content, encoding="utf-8")

    @staticmethod
    def _get_git_commits(last_tag: str | None = None) -> list[str]:
        """调用 git log 获取 commit 列表。"""
        try:
            if last_tag:
                cmd = ["git", "log", f"{last_tag}..HEAD", "--oneline"]
            else:
                cmd = ["git", "log", "--oneline"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return [
                line.strip()
                for line in result.stdout.strip().splitlines()
                if line.strip()
            ]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []

    @staticmethod
    def _parse_commits(commits: list[str]) -> list[dict[str, str]]:
        """解析 conventional commit 格式。

        匹配 "type: description" 或 "type(scope): description"。
        """
        # commit type -> 变更类型映射
        type_map: dict[str, str] = {
            "feat": "added",
            "add": "added",
            "fix": "fixed",
            "refactor": "changed",
            "docs": "changed",
            "style": "changed",
            "chore": "changed",
            "perf": "changed",
            "remove": "removed",
            "delete": "removed",
        }

        changes: list[dict[str, str]] = []
        for commit in commits:
            # 去掉 commit hash
            if " " in commit:
                message = commit.split(" ", 1)[1]
            else:
                message = commit

            # 匹配 type(scope): desc 或 type: desc
            if ":" not in message:
                continue

            type_part, desc = message.split(":", 1)
            # 去掉 scope 部分
            raw_type = type_part.split("(")[0].strip().lower()
            mapped = type_map.get(raw_type, "changed")

            changes.append(
                {
                    "type": mapped,
                    "description": desc.strip(),
                }
            )

        return changes
