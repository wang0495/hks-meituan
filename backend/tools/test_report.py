"""测试报告生成器：收集 pytest 结果并输出 HTML 报告。

支持两种数据来源：
1. pytest-json-report 生成的 JSON 文件（推荐）
2. 手动调用 add_result() 逐条添加

用法：
    generator = TestReportGenerator()
    generator.load_from_json("test_results.json")
    generator.save_report("test_report.html")
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TestResult:
    """单条测试结果。"""

    name: str
    nodeid: str
    passed: bool
    duration: float
    details: str = ""
    marker: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def status(self) -> str:
        return "通过" if self.passed else "失败"

    @property
    def status_class(self) -> str:
        return "passed" if self.passed else "failed"


@dataclass
class TestSummary:
    """测试结果摘要。"""

    total: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    total_duration: float = 0.0

    @classmethod
    def from_results(cls, results: list[TestResult]) -> TestSummary:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        return cls(
            total=total,
            passed=passed,
            failed=failed,
            pass_rate=passed / total if total > 0 else 0.0,
            total_duration=sum(r.duration for r in results),
        )


class TestReportGenerator:
    """测试报告生成器。

    收集测试结果，生成 HTML 格式的测试报告。
    """

    def __init__(self, project_name: str = "CityFlow") -> None:
        self._project_name = project_name
        self._results: list[TestResult] = []
        self._coverage_data: dict[str, Any] | None = None
        self._generated_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_result(
        self,
        test_name: str,
        passed: bool,
        duration: float,
        details: str = "",
        nodeid: str = "",
        marker: str = "",
    ) -> None:
        """手动添加一条测试结果。"""
        self._results.append(
            TestResult(
                name=test_name,
                nodeid=nodeid or test_name,
                passed=passed,
                duration=duration,
                details=details,
                marker=marker,
            )
        )

    def load_from_json(self, json_path: str | Path) -> None:
        """从 pytest-json-report 输出的 JSON 文件加载结果。

        需要安装 pytest-json-report: pip install pytest-json-report
        运行: pytest --json-report --json-report-file=test_results.json
        """
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
        for test in data.get("tests", []):
            outcome = test.get("outcome", "unknown")
            self.add_result(
                test_name=test.get("nodeid", "unknown").split("::")[-1],
                passed=outcome == "passed",
                duration=test.get("duration", 0.0),
                details=self._extract_call_repr(test),
                nodeid=test.get("nodeid", ""),
                marker=self._extract_marker(test),
            )

    def load_from_xml(self, xml_path: str | Path) -> None:
        """从 pytest 生成的 JUnit XML 报告加载结果。

        运行: pytest --junitxml=test_results.xml
        """
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        for suite in root.iter("testcase"):
            failure = suite.find("failure")
            error = suite.find("error")
            skipped = suite.find("skipped")
            passed = failure is None and error is None and skipped is None
            details = ""
            if failure is not None:
                details = failure.get("message", "")
            elif error is not None:
                details = error.get("message", "")

            self.add_result(
                test_name=suite.get("name", "unknown"),
                passed=passed,
                duration=float(suite.get("time", "0")),
                details=details,
                nodeid=suite.get("classname", "").replace(".", "/")
                + "::"
                + suite.get("name", ""),
            )

    def load_coverage_xml(self, coverage_path: str | Path) -> None:
        """加载 coverage.xml 覆盖率数据。"""
        tree = ET.parse(str(coverage_path))
        root = tree.getroot()
        packages: list[dict[str, Any]] = []
        for package in root.iter("package"):
            pkg_name = package.get("name", "")
            line_rate = float(package.get("line-rate", "0"))
            branch_rate = float(package.get("branch-rate", "0"))
            lines_valid = int(package.get("lines-valid", "0"))
            lines_covered = int(package.get("lines-covered", "0"))
            packages.append(
                {
                    "name": pkg_name,
                    "line_rate": line_rate,
                    "branch_rate": branch_rate,
                    "lines_valid": lines_valid,
                    "lines_covered": lines_covered,
                }
            )

        coverage_rate = (
            float(root.get("line-rate", "0")) if root.tag == "coverage" else 0.0
        )
        self._coverage_data = {
            "line_rate": coverage_rate,
            "packages": packages,
        }

    @property
    def results(self) -> list[TestResult]:
        return self._results

    def generate_summary(self) -> TestSummary:
        """生成结果摘要。"""
        return TestSummary.from_results(self._results)

    def generate_html_report(self) -> str:
        """生成完整的 HTML 测试报告。"""
        summary = self.generate_summary()
        return (
            self._html_header()
            + self._html_summary(summary)
            + self._html_coverage_section()
            + self._html_detail_table()
            + self._html_footer()
        )

    def save_report(self, filename: str | Path = "test_report.html") -> Path:
        """将报告写入文件，返回文件路径。"""
        path = Path(filename)
        path.write_text(self.generate_html_report(), encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_call_repr(test: dict[str, Any]) -> str:
        """从 pytest-json-report 的 test 对象中提取失败详情。"""
        call = test.get("call", {})
        if call.get("outcome") != "passed":
            longrepr = call.get("longrepr", "")
            if isinstance(longrepr, str):
                return longrepr[:500]
        return ""

    @staticmethod
    def _extract_marker(test: dict[str, Any]) -> str:
        """提取测试标记（slow / integration 等）。"""
        markers = test.get("keywords", {})
        if isinstance(markers, dict):
            return ", ".join(k for k in markers if k not in ("test", "parametrize"))
        return ""

    def _html_header(self) -> str:
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self._project_name} 测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
               background: #f4f6f9; color: #333; padding: 24px; }}
        h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .meta {{ color: #888; font-size: 13px; margin-bottom: 20px; }}
        .card {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 20px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                         gap: 12px; }}
        .summary-item {{ text-align: center; }}
        .summary-item .number {{ font-size: 28px; font-weight: 700; }}
        .summary-item .label {{ font-size: 13px; color: #888; }}
        .passed  {{ color: #22c55e; }}
        .failed  {{ color: #ef4444; }}
        .skipped {{ color: #f59e0b; }}
        .error   {{ color: #8b5cf6; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8fafc; font-weight: 600; position: sticky; top: 0; }}
        tr:hover {{ background: #f8fafc; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
                  font-size: 12px; font-weight: 600; }}
        .badge-passed {{ background: #dcfce7; color: #166534; }}
        .badge-failed {{ background: #fee2e2; color: #991b1b; }}
        .badge-slow {{ background: #fef3c7; color: #92400e; }}
        .badge-integration {{ background: #dbeafe; color: #1e40af; }}
        .details {{ font-size: 12px; color: #666; max-width: 400px;
                     white-space: pre-wrap; word-break: break-word; }}
        .progress-bar {{ background: #e5e7eb; border-radius: 4px; height: 8px;
                         overflow: hidden; }}
        .progress-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
        .coverage-table {{ margin-top: 10px; }}
        .coverage-table td {{ font-family: "Cascadia Code", "Fira Code", monospace; font-size: 13px; }}
    </style>
</head>
<body>
    <h1>{self._project_name} 测试报告</h1>
    <p class="meta">生成时间: {self._generated_at}</p>
"""

    def _html_summary(self, summary: TestSummary) -> str:
        rate_pct = summary.pass_rate * 100
        rate_color = (
            "#22c55e" if rate_pct >= 80 else "#f59e0b" if rate_pct >= 60 else "#ef4444"
        )
        return f"""
    <div class="card">
        <h2 style="margin-bottom: 12px;">测试摘要</h2>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="number">{summary.total}</div>
                <div class="label">总测试数</div>
            </div>
            <div class="summary-item">
                <div class="number passed">{summary.passed}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-item">
                <div class="number failed">{summary.failed}</div>
                <div class="label">失败</div>
            </div>
            <div class="summary-item">
                <div class="number" style="color: {rate_color};">{rate_pct:.1f}%</div>
                <div class="label">通过率</div>
            </div>
            <div class="summary-item">
                <div class="number">{summary.total_duration:.2f}s</div>
                <div class="label">总耗时</div>
            </div>
        </div>
        <div class="progress-bar" style="margin-top: 12px;">
            <div class="progress-fill"
                 style="width: {rate_pct}%; background: {rate_color};"></div>
        </div>
    </div>
"""

    def _html_coverage_section(self) -> str:
        if self._coverage_data is None:
            return ""

        line_rate = self._coverage_data["line_rate"] * 100
        rate_color = (
            "#22c55e"
            if line_rate >= 80
            else "#f59e0b" if line_rate >= 60 else "#ef4444"
        )

        rows = ""
        for pkg in sorted(self._coverage_data["packages"], key=lambda p: p["name"]):
            pkg_rate = pkg["line_rate"] * 100
            pkg_color = (
                "#22c55e"
                if pkg_rate >= 80
                else "#f59e0b" if pkg_rate >= 60 else "#ef4444"
            )
            rows += f"""
            <tr>
                <td>{pkg['name']}</td>
                <td style="color: {pkg_color};">{pkg_rate:.1f}%</td>
                <td>{pkg['lines_covered']}/{pkg['lines_valid']}</td>
                <td>{pkg['branch_rate'] * 100:.1f}%</td>
            </tr>"""

        return f"""
    <div class="card">
        <h2 style="margin-bottom: 12px;">代码覆盖率</h2>
        <p style="margin-bottom: 10px;">
            整体行覆盖率:
            <strong style="color: {rate_color};">{line_rate:.1f}%</strong>
        </p>
        <div class="progress-bar" style="margin-bottom: 12px;">
            <div class="progress-fill"
                 style="width: {line_rate}%; background: {rate_color};"></div>
        </div>
        <table class="coverage-table">
            <thead>
                <tr>
                    <th>模块</th><th>行覆盖率</th><th>覆盖行数</th><th>分支覆盖率</th>
                </tr>
            </thead>
            <tbody>{rows}
            </tbody>
        </table>
    </div>
"""

    def _html_detail_table(self) -> str:
        rows = ""
        for r in self._results:
            badge_class = f"badge-{r.status_class}"
            marker_badge = ""
            if r.marker:
                for m in r.marker.split(","):
                    m = m.strip()
                    if m in ("slow", "integration"):
                        marker_badge += f' <span class="badge badge-{m}">{m}</span>'

            details_html = (
                f'<span class="details">{r.details}</span>' if r.details else ""
            )
            rows += f"""
            <tr>
                <td>{r.name}{marker_badge}</td>
                <td><span class="badge {badge_class}">{r.status}</span></td>
                <td>{r.duration:.3f}s</td>
                <td>{details_html}</td>
            </tr>"""

        return f"""
    <div class="card">
        <h2 style="margin-bottom: 12px;">详细结果</h2>
        <table>
            <thead>
                <tr>
                    <th>测试名称</th><th>状态</th><th>耗时</th><th>详情</th>
                </tr>
            </thead>
            <tbody>{rows}
            </tbody>
        </table>
    </div>
"""

    @staticmethod
    def _html_footer() -> str:
        return """
</body>
</html>
"""


def generate_report_from_files(
    xml_path: str | Path | None = None,
    coverage_path: str | Path | None = None,
    output_path: str | Path = "test_report.html",
    project_name: str = "CityFlow",
) -> Path:
    """便捷函数：从 JUnit XML 和 coverage XML 生成报告。

    Args:
        xml_path: pytest --junitxml 生成的 XML 文件路径
        coverage_path: coverage xml 生成的 XML 文件路径
        output_path: 输出 HTML 文件路径
        project_name: 项目名称

    Returns:
        生成的报告文件路径
    """
    generator = TestReportGenerator(project_name=project_name)

    if xml_path and Path(xml_path).exists():
        generator.load_from_xml(xml_path)

    if coverage_path and Path(coverage_path).exists():
        generator.load_coverage_xml(coverage_path)

    return generator.save_report(output_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成 CityFlow 测试报告")
    parser.add_argument("--xml", help="pytest JUnit XML 文件路径", default=None)
    parser.add_argument("--coverage", help="coverage.xml 文件路径", default=None)
    parser.add_argument(
        "--output", "-o", help="输出 HTML 文件路径", default="test_report.html"
    )
    args = parser.parse_args()

    report_path = generate_report_from_files(
        xml_path=args.xml,
        coverage_path=args.coverage,
        output_path=args.output,
    )
    print(f"报告已生成: {report_path}")
