"""CityFlow 覆盖率分析器。

运行 pytest + coverage，解析覆盖率数据，定位未覆盖的代码行。
支持 JSON 和 Cobertura XML 两种格式的覆盖率报告。

使用方式::

    analyzer = CoverageAnalyzer()
    result = analyzer.run_coverage()
    if result["success"]:
        print(analyzer.get_summary())
        uncovered = analyzer.get_uncovered_lines()
"""

from __future__ import annotations

import json
import logging
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["CoverageAnalyzer", "FileCoverage"]


@dataclass
class FileCoverage:
    """单个文件的覆盖率数据。"""

    file_path: str
    total_lines: int
    covered_lines: int
    missing_lines: list[int] = field(default_factory=list)
    coverage_percent: float = 0.0

    @property
    def uncovered_count(self) -> int:
        return self.total_lines - self.covered_lines


class CoverageAnalyzer:
    """覆盖率分析器。

    支持两种模式：
    1. ``run_coverage()`` — 运行 pytest 并收集覆盖率数据（JSON 格式）
    2. ``load_xml(path)`` — 从已有的 Cobertura XML 文件加载覆盖率数据
    """

    def __init__(
        self,
        source: str = "backend",
        report_format: str = "json",
    ) -> None:
        self._source = source
        self._report_format = report_format
        self._coverage_data: dict[str, Any] | None = None
        self._files: dict[str, FileCoverage] = {}

    # ------------------------------------------------------------------
    # 运行覆盖率测试
    # ------------------------------------------------------------------

    def run_coverage(
        self,
        extra_args: list[str] | None = None,
    ) -> dict[str, Any]:
        """运行 pytest 覆盖率测试，返回执行结果。

        Args:
            extra_args: 传给 pytest 的额外参数。

        Returns:
            ``{"success": bool, "data": ..., "error": ...}``
        """
        cmd = [
            "python",
            "-m",
            "pytest",
            f"--cov={self._source}",
            f"--cov-report={self._report_format}",
            "--tb=short",
            "-q",
        ]
        if extra_args:
            cmd.extend(extra_args)

        logger.info("运行覆盖率测试: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
        )

        # 即使部分测试失败，coverage.json 仍然会生成
        try:
            coverage_file = Path("coverage.json")
            if coverage_file.exists():
                self._coverage_data = json.loads(
                    coverage_file.read_text(encoding="utf-8")
                )
                self._parse_json_data()
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("解析覆盖率数据失败: %s", exc)

        if result.returncode == 0:
            return {"success": True, "data": self._coverage_data}

        # 测试有失败，但覆盖率数据可能已解析
        if self._coverage_data:
            return {"success": True, "data": self._coverage_data}

        return {"success": False, "error": result.stderr}

    # ------------------------------------------------------------------
    # 从 XML 加载
    # ------------------------------------------------------------------

    def load_xml(self, xml_path: str | Path) -> dict[str, Any]:
        """从 Cobertura XML 文件加载覆盖率数据。

        Args:
            xml_path: coverage.xml 文件路径。

        Returns:
            摘要字典。
        """
        path = Path(xml_path)
        if not path.exists():
            return {"success": False, "error": f"文件不存在: {path}"}

        tree = ET.parse(str(path))
        root = tree.getroot()

        lines_valid = int(root.attrib.get("lines-valid", 0))
        lines_covered = int(root.attrib.get("lines-covered", 0))
        line_rate = float(root.attrib.get("line-rate", 0))

        self._files.clear()

        for cls in root.findall(".//class"):
            filename = cls.attrib.get("filename", cls.attrib.get("name", ""))
            rate = float(cls.attrib.get("line-rate", "0"))
            lines = cls.findall(".//line")
            total = len(lines)
            covered = sum(1 for line in lines if line.attrib.get("hits", "0") == "1")
            missing = [
                int(line.attrib["number"])
                for line in lines
                if line.attrib.get("hits", "0") == "0"
            ]

            self._files[filename] = FileCoverage(
                file_path=filename,
                total_lines=total,
                covered_lines=covered,
                missing_lines=missing,
                coverage_percent=round(rate * 100, 2),
            )

        return {
            "success": True,
            "total_lines": lines_valid,
            "covered_lines": lines_covered,
            "coverage_percent": round(line_rate * 100, 2),
            "file_count": len(self._files),
        }

    # ------------------------------------------------------------------
    # 解析 JSON
    # ------------------------------------------------------------------

    def _parse_json_data(self) -> None:
        """解析 pytest-cov 输出的 JSON 数据。"""
        if not self._coverage_data:
            return

        self._files.clear()

        for file_path, data in self._coverage_data.get("files", {}).items():
            summary = data.get("summary", {})
            missing = data.get("missing_lines", [])
            total = summary.get("num_statements", 0)
            covered = summary.get("covered_lines", 0)
            pct = summary.get("percent_covered", 0.0)

            self._files[file_path] = FileCoverage(
                file_path=file_path,
                total_lines=total,
                covered_lines=covered,
                missing_lines=missing,
                coverage_percent=round(pct, 2),
            )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_uncovered_lines(self) -> dict[str, list[int]]:
        """获取所有文件的未覆盖行号。

        Returns:
            ``{file_path: [line_numbers]}`` 仅包含有未覆盖行的文件。
        """
        return {
            fp: fc.missing_lines for fp, fc in self._files.items() if fc.missing_lines
        }

    def get_uncovered_files(self) -> list[FileCoverage]:
        """获取所有有未覆盖行的文件，按覆盖率从低到高排序。"""
        return sorted(
            [fc for fc in self._files.values() if fc.missing_lines],
            key=lambda fc: fc.coverage_percent,
        )

    def get_summary(self) -> dict[str, Any]:
        """获取覆盖率摘要。"""
        if self._coverage_data:
            totals = self._coverage_data.get("totals", {})
            return {
                "total_lines": totals.get("num_statements", 0),
                "covered_lines": totals.get("covered_lines", 0),
                "missing_lines": totals.get("missing_lines", 0),
                "coverage_percent": round(totals.get("percent_covered", 0.0), 2),
                "file_count": len(self._files),
            }

        # 从 XML 数据汇总
        total = sum(fc.total_lines for fc in self._files.values())
        covered = sum(fc.covered_lines for fc in self._files.values())
        pct = (covered / total * 100) if total > 0 else 0.0

        return {
            "total_lines": total,
            "covered_lines": covered,
            "missing_lines": total - covered,
            "coverage_percent": round(pct, 2),
            "file_count": len(self._files),
        }

    def get_file_coverage(self, file_path: str) -> FileCoverage | None:
        """获取指定文件的覆盖率详情。"""
        return self._files.get(file_path)

    def get_low_coverage_files(
        self,
        threshold: float = 50.0,
    ) -> list[FileCoverage]:
        """获取覆盖率低于阈值的文件。"""
        return sorted(
            [fc for fc in self._files.values() if fc.coverage_percent < threshold],
            key=lambda fc: fc.coverage_percent,
        )

    @property
    def files(self) -> dict[str, FileCoverage]:
        """所有文件的覆盖率数据。"""
        return self._files
