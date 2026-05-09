"""CityFlow 文档维护工具。

提供文档自动生成、版本管理和全文搜索功能。
整合 DocGenerator、ChangelogGenerator 等现有工具，
为项目文档提供统一的维护入口。

Features:
    - 文档自动生成：API 文档、SDK 文档、使用指南
    - 文档版本管理：基于 Git tag 追踪文档变更历史
    - 文档全文搜索：支持关键词搜索，返回匹配结果
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.tools.changelog_generator import ChangelogGenerator
from backend.tools.doc_generator import DocGenerator
from backend.tools.markdown_generator import MarkdownGenerator

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """文档搜索结果。"""

    file: str
    matches: int
    snippets: list[str] = field(default_factory=list)


@dataclass
class DocVersion:
    """文档版本信息。"""

    version: str
    date: str
    files: list[str] = field(default_factory=list)
    commit_hash: str = ""


@dataclass
class DocStats:
    """文档统计信息。"""

    total_files: int = 0
    total_words: int = 0
    total_lines: int = 0
    last_updated: str = ""
    versions: list[DocVersion] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 文档维护器
# ---------------------------------------------------------------------------


class DocMaintainer:
    """文档维护器。

    提供文档自动生成、版本管理和搜索功能。

    Parameters
    ----------
    docs_dir : str
        文档目录路径，默认 ``"docs"``。
    source_dir : str
        源码目录路径，默认 ``"backend"``。
    project_name : str
        项目名称，默认 ``"CityFlow"``。
    """

    def __init__(
        self,
        docs_dir: str = "docs",
        source_dir: str = "backend",
        project_name: str = "CityFlow",
    ) -> None:
        self._docs_dir = Path(docs_dir)
        self._source_dir = Path(source_dir)
        self._project_name = project_name
        self._docs_dir.mkdir(parents=True, exist_ok=True)

        self._md = MarkdownGenerator()
        self._doc_generator = DocGenerator(
            source_dir=source_dir,
            project_name=project_name,
        )
        self._changelog_generator = ChangelogGenerator(
            changelog_file=str(self._docs_dir / "CHANGELOG.md"),
        )

        # 版本历史文件
        self._version_file = self._docs_dir / ".doc_versions.json"

    # ------------------------------------------------------------------
    # 文档自动生成
    # ------------------------------------------------------------------

    def generate_api_doc(self, api_spec: dict[str, Any] | None = None) -> str:
        """生成 API 文档。

        从 OpenAPI 规范或源码解析生成 API 文档。

        Parameters
        ----------
        api_spec : dict[str, Any] | None
            OpenAPI 规范字典，为 None 时从源码解析。

        Returns
        -------
        str
            API 文档 Markdown 内容。
        """
        if api_spec:
            return self._generate_from_openapi(api_spec)

        # 从源码解析生成
        self._doc_generator.parse()
        return self._doc_generator.generate_api_docs_markdown()

    def generate_sdk_doc(self) -> str:
        """生成 SDK 文档。

        Returns
        -------
        str
            SDK 文档 Markdown 内容。
        """
        self._doc_generator.parse()
        return self._doc_generator.generate_sdk_docs()

    def generate_guide_doc(self) -> str:
        """生成使用指南。

        Returns
        -------
        str
            使用指南 Markdown 内容。
        """
        self._doc_generator.parse()
        return self._doc_generator.generate_usage_guide()

    def generate_changelog(
        self,
        version: str,
        changes: list[dict[str, str]],
        date: str | None = None,
    ) -> str:
        """生成变更日志条目并追加到文件。

        Parameters
        ----------
        version : str
            版本号。
        changes : list[dict[str, str]]
            变更列表，每项含 "type" 和 "description"。
        date : str | None
            日期，默认使用当天。

        Returns
        -------
        str
            生成的变更日志内容。
        """
        date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._changelog_generator.add_version(version, changes, date)

        # 读取生成的内容
        changelog_file = self._docs_dir / "CHANGELOG.md"
        return changelog_file.read_text(encoding="utf-8")

    def generate_all_docs(self) -> dict[str, Path]:
        """生成所有文档并保存。

        Returns
        -------
        dict[str, Path]
            键为文档类型，值为保存路径。
        """
        results: dict[str, Path] = {}

        # 解析源码
        self._doc_generator.parse()

        # API 文档
        api_content = self.generate_api_doc()
        results["api"] = self.save_doc("api_reference.md", api_content)

        # SDK 文档
        sdk_content = self.generate_sdk_doc()
        results["sdk"] = self.save_doc("sdk_reference.md", sdk_content)

        # 使用指南
        guide_content = self.generate_guide_doc()
        results["guide"] = self.save_doc("usage_guide.md", guide_content)

        # 记录版本
        self._record_version("auto", list(results.keys()))

        return results

    # ------------------------------------------------------------------
    # 文档保存
    # ------------------------------------------------------------------

    def save_doc(self, filename: str, content: str) -> Path:
        """保存文档到文件。

        Parameters
        ----------
        filename : str
            文件名。
        content : str
            文档内容。

        Returns
        -------
        Path
            保存的文件路径。
        """
        filepath = self._docs_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return filepath.resolve()

    # ------------------------------------------------------------------
    # 文档版本管理
    # ------------------------------------------------------------------

    def get_version_history(self) -> list[DocVersion]:
        """获取文档版本历史。

        Returns
        -------
        list[DocVersion]
            版本列表，按时间倒序排列。
        """
        versions = self._load_versions()

        # 同时尝试从 Git tag 获取
        git_versions = self._get_git_versions()
        for gv in git_versions:
            if not any(v.version == gv.version for v in versions):
                versions.append(gv)

        return sorted(versions, key=lambda v: v.date, reverse=True)

    def create_version(
        self,
        version: str,
        files: list[str] | None = None,
    ) -> DocVersion:
        """创建新的文档版本。

        Parameters
        ----------
        version : str
            版本号。
        files : list[str] | None
            包含的文件列表，为 None 时自动检测。

        Returns
        -------
        DocVersion
            创建的版本信息。
        """
        if files is None:
            files = [f.name for f in self._docs_dir.glob("*.md")]

        doc_version = DocVersion(
            version=version,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            files=files,
            commit_hash=self._get_current_commit_hash(),
        )

        versions = self._load_versions()
        versions.append(doc_version)
        self._save_versions(versions)

        return doc_version

    def diff_versions(
        self,
        version_a: str,
        version_b: str,
    ) -> dict[str, Any] | None:
        """比较两个版本的差异。

        使用 Git diff 比较两个版本之间的文档变化。

        Parameters
        ----------
        version_a : str
            起始版本（Git tag 或 commit hash）。
        version_b : str
            结束版本。

        Returns
        -------
        dict[str, Any] | None
            差异信息，包含变更文件列表和 diff 内容。
        """
        try:
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    f"{version_a}..{version_b}",
                    "--",
                    str(self._docs_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            changed_files = self._parse_diff_files(result.stdout)

            return {
                "from": version_a,
                "to": version_b,
                "changed_files": changed_files,
                "diff": result.stdout,
            }
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    # ------------------------------------------------------------------
    # 文档搜索
    # ------------------------------------------------------------------

    def search_docs(
        self,
        keyword: str,
        *,
        case_sensitive: bool = False,
        max_snippets: int = 3,
        context_lines: int = 1,
    ) -> list[SearchResult]:
        """搜索文档内容。

        Parameters
        ----------
        keyword : str
            搜索关键词。
        case_sensitive : bool
            是否区分大小写，默认 False。
        max_snippets : int
            每个文件最多返回的匹配片段数，默认 3。
        context_lines : int
            匹配行的上下文行数，默认 1。

        Returns
        -------
        list[SearchResult]
            搜索结果列表，按匹配数降序排列。
        """
        results: list[SearchResult] = []

        for doc_file in self._docs_dir.rglob("*.md"):
            try:
                content = doc_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            # 计算匹配数
            if case_sensitive:
                count = content.count(keyword)
            else:
                count = content.lower().count(keyword.lower())

            if count == 0:
                continue

            # 提取匹配片段
            snippets = self._extract_snippets(
                content,
                keyword,
                max_snippets=max_snippets,
                context_lines=context_lines,
                case_sensitive=case_sensitive,
            )

            relative_path = doc_file.relative_to(self._docs_dir)
            results.append(
                SearchResult(
                    file=str(relative_path),
                    matches=count,
                    snippets=snippets,
                )
            )

        return sorted(results, key=lambda x: x.matches, reverse=True)

    def search_in_file(
        self,
        filename: str,
        keyword: str,
        *,
        case_sensitive: bool = False,
    ) -> list[str]:
        """在指定文件中搜索。

        Parameters
        ----------
        filename : str
            文件名。
        keyword : str
            搜索关键词。
        case_sensitive : bool
            是否区分大小写。

        Returns
        -------
        list[str]
            匹配的行列表。
        """
        filepath = self._docs_dir / filename
        if not filepath.exists():
            return []

        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()

        matched_lines: list[str] = []
        for line in lines:
            if case_sensitive:
                if keyword in line:
                    matched_lines.append(line.strip())
            else:
                if keyword.lower() in line.lower():
                    matched_lines.append(line.strip())

        return matched_lines

    # ------------------------------------------------------------------
    # 文档统计
    # ------------------------------------------------------------------

    def get_stats(self) -> DocStats:
        """获取文档统计信息。

        Returns
        -------
        DocStats
            文档统计数据。
        """
        total_files = 0
        total_words = 0
        total_lines = 0
        last_updated = ""

        for doc_file in self._docs_dir.rglob("*.md"):
            if doc_file.name.startswith("."):
                continue

            total_files += 1
            content = doc_file.read_text(encoding="utf-8")
            total_words += len(content.split())
            total_lines += len(content.splitlines())

            # 获取最后修改时间
            mtime = datetime.fromtimestamp(
                doc_file.stat().st_mtime,
                tz=timezone.utc,
            )
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
            if not last_updated or mtime_str > last_updated:
                last_updated = mtime_str

        versions = self._load_versions()

        return DocStats(
            total_files=total_files,
            total_words=total_words,
            total_lines=total_lines,
            last_updated=last_updated,
            versions=versions,
        )

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _generate_from_openapi(self, api_spec: dict[str, Any]) -> str:
        """从 OpenAPI 规范生成 API 文档。

        Parameters
        ----------
        api_spec : dict[str, Any]
            OpenAPI 规范字典。

        Returns
        -------
        str
            API 文档 Markdown 内容。
        """
        lines: list[str] = []

        # 标题
        info = api_spec.get("info", {})
        title = info.get("title", f"{self._project_name} API")
        version = info.get("version", "1.0.0")
        description = info.get("description", "")

        lines.append(f"# {title}\n")
        lines.append(f"**版本**: {version}\n")
        if description:
            lines.append(f"{description}\n")

        # 服务器信息
        servers = api_spec.get("servers", [])
        if servers:
            lines.append("## 服务器\n")
            lines.append(
                self._md.generate_table(
                    headers=["URL", "描述"],
                    rows=[
                        [s.get("url", ""), s.get("description", "")] for s in servers
                    ],
                )
            )
            lines.append("")

        # API 端点
        paths = api_spec.get("paths", {})
        if paths:
            lines.append("## API 端点\n")

            # 概览表
            overview_rows: list[list[str]] = []
            for path, methods in paths.items():
                for method, spec in methods.items():
                    if method.lower() in ("get", "post", "put", "delete", "patch"):
                        summary = spec.get("summary", "")
                        overview_rows.append([method.upper(), path, summary])

            if overview_rows:
                lines.append(
                    self._md.generate_table(
                        headers=["方法", "路径", "说明"],
                        rows=overview_rows,
                    )
                )
                lines.append("")

            # 详细文档
            for path, methods in paths.items():
                for method, spec in methods.items():
                    if method.lower() not in ("get", "post", "put", "delete", "patch"):
                        continue

                    summary = spec.get("summary", "")
                    description = spec.get("description", "")

                    lines.append(f"### {method.upper()} {path}\n")
                    if summary:
                        lines.append(f"**{summary}**\n")
                    if description:
                        lines.append(f"{description}\n")

                    # 参数
                    parameters = spec.get("parameters", [])
                    if parameters:
                        lines.append("**参数:**\n")
                        lines.append(
                            self._md.generate_table(
                                headers=["名称", "位置", "类型", "必填", "说明"],
                                rows=[
                                    [
                                        p.get("name", ""),
                                        p.get("in", ""),
                                        p.get("schema", {}).get("type", "-"),
                                        "是" if p.get("required") else "否",
                                        p.get("description", ""),
                                    ]
                                    for p in parameters
                                ],
                            )
                        )
                        lines.append("")

                    # 请求体
                    request_body = spec.get("requestBody", {})
                    if request_body:
                        content = request_body.get("content", {})
                        for media_type, media_spec in content.items():
                            example = media_spec.get("example")
                            lines.append(f"**请求体** ({media_type}):\n")
                            if example:
                                lines.append(
                                    self._md.generate_code_block(
                                        json.dumps(
                                            example, ensure_ascii=False, indent=2
                                        ),
                                        language="json",
                                    )
                                )
                                lines.append("")

                    # 响应
                    responses = spec.get("responses", {})
                    if responses:
                        lines.append("**响应:**\n")
                        for status, resp in responses.items():
                            desc = resp.get("description", "")
                            lines.append(f"- `{status}`: {desc}")
                        lines.append("")

                    lines.append("---\n")

        return "\n".join(lines)

    def _record_version(
        self,
        version: str,
        files: list[str],
    ) -> None:
        """记录文档版本。

        Parameters
        ----------
        version : str
            版本标识。
        files : list[str]
            生成的文件列表。
        """
        doc_version = DocVersion(
            version=version,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            files=files,
            commit_hash=self._get_current_commit_hash(),
        )

        versions = self._load_versions()
        versions.append(doc_version)
        self._save_versions(versions)

    def _load_versions(self) -> list[DocVersion]:
        """从文件加载版本历史。

        Returns
        -------
        list[DocVersion]
            版本列表。
        """
        if not self._version_file.exists():
            return []

        try:
            data = json.loads(self._version_file.read_text(encoding="utf-8"))
            return [
                DocVersion(
                    version=v["version"],
                    date=v["date"],
                    files=v.get("files", []),
                    commit_hash=v.get("commit_hash", ""),
                )
                for v in data
            ]
        except (json.JSONDecodeError, KeyError):
            return []

    def _save_versions(self, versions: list[DocVersion]) -> None:
        """保存版本历史到文件。

        Parameters
        ----------
        versions : list[DocVersion]
            版本列表。
        """
        data = [
            {
                "version": v.version,
                "date": v.date,
                "files": v.files,
                "commit_hash": v.commit_hash,
            }
            for v in versions
        ]

        self._version_file.parent.mkdir(parents=True, exist_ok=True)
        self._version_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _get_git_versions(self) -> list[DocVersion]:
        """从 Git tag 获取版本信息。

        Returns
        -------
        list[DocVersion]
            版本列表。
        """
        versions: list[DocVersion] = []

        try:
            result = subprocess.run(
                ["git", "tag", "--sort=-creatordate"],
                capture_output=True,
                text=True,
                check=True,
            )

            for tag in result.stdout.strip().splitlines():
                if not tag:
                    continue

                # 获取 tag 日期
                date_result = subprocess.run(
                    [
                        "git",
                        "log",
                        "-1",
                        "--format=%ai",
                        tag,
                    ],
                    capture_output=True,
                    text=True,
                )

                date_str = ""
                if date_result.returncode == 0:
                    date_str = date_result.stdout.strip()[:10]

                versions.append(
                    DocVersion(
                        version=tag,
                        date=date_str,
                        files=[],
                        commit_hash=tag,
                    )
                )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return versions

    def _get_current_commit_hash(self) -> str:
        """获取当前 Git commit hash。

        Returns
        -------
        str
            commit hash，获取失败返回空字符串。
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

    @staticmethod
    def _parse_diff_files(diff_output: str) -> list[str]:
        """从 diff 输出中提取变更文件列表。

        Parameters
        ----------
        diff_output : str
            git diff 输出。

        Returns
        -------
        list[str]
            变更文件路径列表。
        """
        files: list[str] = []
        for line in diff_output.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    # 提取 b/path 格式的文件路径
                    file_path = parts[3]
                    if file_path.startswith("b/"):
                        file_path = file_path[2:]
                    files.append(file_path)
        return files

    @staticmethod
    def _extract_snippets(
        content: str,
        keyword: str,
        *,
        max_snippets: int = 3,
        context_lines: int = 1,
        case_sensitive: bool = False,
    ) -> list[str]:
        """从内容中提取匹配片段。

        Parameters
        ----------
        content : str
            文件内容。
        keyword : str
            搜索关键词。
        max_snippets : int
            最大片段数。
        context_lines : int
            上下文行数。
        case_sensitive : bool
            是否区分大小写。

        Returns
        -------
        list[str]
            匹配片段列表。
        """
        lines = content.splitlines()
        snippets: list[str] = []
        used_indices: set[int] = set()

        for i, line in enumerate(lines):
            if len(snippets) >= max_snippets:
                break

            # 检查是否匹配
            if case_sensitive:
                match = keyword in line
            else:
                match = keyword.lower() in line.lower()

            if not match:
                continue

            # 跳过已包含在之前片段中的行
            if i in used_indices:
                continue

            # 提取上下文
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)

            snippet_lines: list[str] = []
            for j in range(start, end):
                used_indices.add(j)
                prefix = ">>> " if j == i else "    "
                snippet_lines.append(f"{prefix}{lines[j]}")

            snippets.append("\n".join(snippet_lines))

        return snippets
