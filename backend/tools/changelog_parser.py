"""CityFlow 变更日志解析器。

解析符合 Keep a Changelog 格式的 CHANGELOG.md 文件，
提取版本号、日期和变更内容。

文件格式要求：
    ## [x.y.z] - YYYY-MM-DD
    ### 新增
    - 描述内容
    ### 修复
    - 描述内容
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VersionEntry:
    """单个版本的变更记录。"""

    version: str
    date: str
    content: str


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------

# 匹配版本标题行：## [1.0.0] - 2024-01-01
_VERSION_RE = re.compile(r"## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})")

# 匹配变更类型标题：### 新增 / ### 修复 / ### 变更 / ### 移除
_SECTION_RE = re.compile(r"### (新增|修复|变更|移除)\s*")

# 变更类型中英文映射
_TYPE_MAP: dict[str, str] = {
    "新增": "added",
    "修复": "fixed",
    "变更": "changed",
    "移除": "removed",
}


class ChangelogParser:
    """变更日志解析器。

    读取 CHANGELOG.md 文件并解析为结构化的版本列表。

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

    def parse(self) -> list[VersionEntry]:
        """解析变更日志，返回版本列表（按时间倒序）。"""
        if not self._file.exists():
            return []

        content = self._file.read_text(encoding="utf-8")
        return self._parse_content(content)

    def get_latest_version(self) -> VersionEntry | None:
        """获取最新版本条目，无版本时返回 None。"""
        versions = self.parse()
        return versions[0] if versions else None

    def get_version(self, version: str) -> VersionEntry | None:
        """按版本号查找，未找到返回 None。"""
        for entry in self.parse():
            if entry.version == version:
                return entry
        return None

    def get_changes_by_type(self, version: str) -> dict[str, list[str]]:
        """提取指定版本的按类型分组变更列表。

        Returns
        -------
        dict[str, list[str]]
            键为变更类型英文名 (added/fixed/changed/removed)，
            值为该类型下的描述列表。
        """
        entry = self.get_version(version)
        if entry is None:
            return {}
        return self._extract_sections(entry.content)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _parse_content(self, content: str) -> list[VersionEntry]:
        """从文本内容解析出版本列表。"""
        versions: list[VersionEntry] = []
        matches = list(_VERSION_RE.finditer(content))

        for i, match in enumerate(matches):
            ver = match.group(1)
            date = match.group(2)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section = content[start:end].strip()
            versions.append(VersionEntry(version=ver, date=date, content=section))

        return versions

    @staticmethod
    def _extract_sections(content: str) -> dict[str, list[str]]:
        """从版本内容中提取按类型分组的变更项。"""
        result: dict[str, list[str]] = {}
        current_type: str | None = None

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            section_match = _SECTION_RE.match(line)
            if section_match:
                cn_name = section_match.group(1)
                current_type = _TYPE_MAP.get(cn_name, cn_name)
                result.setdefault(current_type, [])
                continue

            if line.startswith("- ") and current_type is not None:
                result[current_type].append(line[2:].strip())

        return result
