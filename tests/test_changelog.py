"""变更日志解析器与生成器测试。"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from backend.tools.changelog_generator import ChangelogGenerator
from backend.tools.changelog_parser import ChangelogParser, VersionEntry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CHANGELOG = textwrap.dedent("""\
    # Changelog

    ## [1.2.0] - 2024-03-15

    ### 新增
    - 用户搜索功能
    - 地图路线规划

    ### 修复
    - 登录超时问题

    ## [1.1.0] - 2024-02-01

    ### 新增
    - POI 收藏功能

    ### 变更
    - 优化首页加载速度

    ## [1.0.0] - 2024-01-01

    ### 新增
    - 初始版本发布
""")


@pytest.fixture
def sample_changelog(tmp_path: Path) -> Path:
    """创建示例 CHANGELOG.md 文件。"""
    file = tmp_path / "CHANGELOG.md"
    file.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    return file


@pytest.fixture
def empty_dir(tmp_path: Path) -> Path:
    """返回空目录路径。"""
    return tmp_path


# ---------------------------------------------------------------------------
# ChangelogParser 测试
# ---------------------------------------------------------------------------


class TestChangelogParser:
    """ChangelogParser 测试套件。"""

    def test_parse_returns_all_versions(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        versions = parser.parse()
        assert len(versions) == 3
        assert [v.version for v in versions] == ["1.2.0", "1.1.0", "1.0.0"]

    def test_parse_extracts_dates(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        versions = parser.parse()
        assert versions[0].date == "2024-03-15"
        assert versions[1].date == "2024-02-01"
        assert versions[2].date == "2024-01-01"

    def test_parse_extracts_content(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        versions = parser.parse()
        assert "用户搜索功能" in versions[0].content
        assert "POI 收藏功能" in versions[1].content

    def test_parse_returns_dataclass(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        versions = parser.parse()
        assert isinstance(versions[0], VersionEntry)

    def test_parse_missing_file_returns_empty(self, empty_dir: Path) -> None:
        path = empty_dir / "nonexistent.md"
        parser = ChangelogParser(str(path))
        assert parser.parse() == []

    def test_get_latest_version(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        latest = parser.get_latest_version()
        assert latest is not None
        assert latest.version == "1.2.0"

    def test_get_latest_version_empty(self, empty_dir: Path) -> None:
        path = empty_dir / "CHANGELOG.md"
        parser = ChangelogParser(str(path))
        assert parser.get_latest_version() is None

    def test_get_version_found(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        entry = parser.get_version("1.1.0")
        assert entry is not None
        assert entry.version == "1.1.0"

    def test_get_version_not_found(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        assert parser.get_version("9.9.9") is None

    def test_get_changes_by_type(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        changes = parser.get_changes_by_type("1.2.0")
        assert "added" in changes
        assert "用户搜索功能" in changes["added"]
        assert "fixed" in changes
        assert "登录超时问题" in changes["fixed"]

    def test_get_changes_by_type_missing_version(self, sample_changelog: Path) -> None:
        parser = ChangelogParser(str(sample_changelog))
        assert parser.get_changes_by_type("9.9.9") == {}


# ---------------------------------------------------------------------------
# ChangelogGenerator 测试
# ---------------------------------------------------------------------------


class TestChangelogGenerator:
    """ChangelogGenerator 测试套件。"""

    def test_add_version_creates_file(self, empty_dir: Path) -> None:
        path = empty_dir / "CHANGELOG.md"
        gen = ChangelogGenerator(str(path))
        gen.add_version("1.0.0", [{"type": "added", "description": "初始版本"}])
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "1.0.0" in content
        assert "初始版本" in content

    def test_add_version_has_header(self, empty_dir: Path) -> None:
        path = empty_dir / "CHANGELOG.md"
        gen = ChangelogGenerator(str(path))
        gen.add_version("1.0.0", [{"type": "added", "description": "测试"}])
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# Changelog")

    def test_add_version_prepends(self, empty_dir: Path) -> None:
        path = empty_dir / "CHANGELOG.md"
        gen = ChangelogGenerator(str(path))

        gen.add_version("1.0.0", [{"type": "added", "description": "V1"}])
        gen.add_version("2.0.0", [{"type": "added", "description": "V2"}])

        content = path.read_text(encoding="utf-8")
        # V2 应该在 V1 前面
        v2_pos = content.index("2.0.0")
        v1_pos = content.index("1.0.0")
        assert v2_pos < v1_pos

    def test_add_version_groups_by_type(self, empty_dir: Path) -> None:
        path = empty_dir / "CHANGELOG.md"
        gen = ChangelogGenerator(str(path))
        gen.add_version(
            "1.0.0",
            [
                {"type": "added", "description": "功能A"},
                {"type": "added", "description": "功能B"},
                {"type": "fixed", "description": "Bug C"},
            ],
        )
        content = path.read_text(encoding="utf-8")
        assert "### 新增" in content
        assert "### 修复" in content

    def test_add_version_custom_date(self, empty_dir: Path) -> None:
        path = empty_dir / "CHANGELOG.md"
        gen = ChangelogGenerator(str(path))
        gen.add_version(
            "1.0.0",
            [{"type": "added", "description": "测试"}],
            date="2025-06-01",
        )
        content = path.read_text(encoding="utf-8")
        assert "2025-06-01" in content

    def test_roundtrip_parse_and_generate(self, empty_dir: Path) -> None:
        """生成后解析，验证数据一致性。"""
        path = empty_dir / "CHANGELOG.md"
        gen = ChangelogGenerator(str(path))
        gen.add_version(
            "1.0.0",
            [
                {"type": "added", "description": "功能A"},
                {"type": "fixed", "description": "Bug B"},
            ],
            date="2024-06-15",
        )

        parser = ChangelogParser(str(path))
        versions = parser.parse()
        assert len(versions) == 1
        assert versions[0].version == "1.0.0"
        assert versions[0].date == "2024-06-15"

        changes = parser.get_changes_by_type("1.0.0")
        assert "功能A" in changes["added"]
        assert "Bug B" in changes["fixed"]

    def test_generate_from_commits(self, empty_dir: Path) -> None:
        gen = ChangelogGenerator(str(empty_dir / "CHANGELOG.md"))
        commits = [
            "abc1234 feat: 新增用户搜索",
            "def5678 fix: 修复登录问题",
            "ghi9012 refactor: 优化数据库查询",
            "jkl3456 docs: 更新README",
        ]
        changes = gen.generate_from_commits(commits)
        assert len(changes) == 4
        assert changes[0]["type"] == "added"
        assert changes[1]["type"] == "fixed"
        assert changes[2]["type"] == "changed"
        assert changes[3]["type"] == "changed"

    def test_generate_from_commits_with_scope(self, empty_dir: Path) -> None:
        gen = ChangelogGenerator(str(empty_dir / "CHANGELOG.md"))
        commits = ["abc1234 feat(auth): 新增OAuth登录"]
        changes = gen.generate_from_commits(commits)
        assert len(changes) == 1
        assert changes[0]["type"] == "added"
        assert "新增OAuth登录" in changes[0]["description"]

    def test_generate_from_commits_no_colon(self, empty_dir: Path) -> None:
        gen = ChangelogGenerator(str(empty_dir / "CHANGELOG.md"))
        commits = ["abc1234 无类型描述"]
        changes = gen.generate_from_commits(commits)
        assert len(changes) == 0

    def test_generate_from_commits_empty(self, empty_dir: Path) -> None:
        gen = ChangelogGenerator(str(empty_dir / "CHANGELOG.md"))
        assert gen.generate_from_commits([]) == []
