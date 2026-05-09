"""CityFlow 覆盖率检查脚本。

运行 pytest 覆盖率测试，生成摘要和未覆盖文件报告，
并可选地输出 HTML 报告。

使用方式::

    python -m backend.tools.run_coverage
    python -m backend.tools.run_coverage --html
    python -m backend.tools.run_coverage --xml coverage.xml
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from backend.tools.coverage_analyzer import CoverageAnalyzer


def print_summary(analyzer: CoverageAnalyzer) -> None:
    """打印覆盖率摘要。"""
    summary = analyzer.get_summary()

    print("=== CityFlow 测试覆盖率报告 ===\n")
    print("1. 覆盖率摘要:")
    print(f"   总行数:     {summary['total_lines']}")
    print(f"   覆盖行数:   {summary['covered_lines']}")
    print(f"   未覆盖行数: {summary['missing_lines']}")
    print(f"   文件数:     {summary['file_count']}")
    print(f"   覆盖率:     {summary['coverage_percent']:.1f}%")


def print_uncovered_files(
    analyzer: CoverageAnalyzer,
    limit: int = 10,
) -> None:
    """打印覆盖率最低的文件。"""
    files = analyzer.get_uncovered_files()
    if not files:
        print("\n2. 所有文件均已覆盖。")
        return

    print(f"\n2. 覆盖率最低的文件 (前 {min(limit, len(files))} 个):")
    for fc in files[:limit]:
        print(
            f"   {fc.file_path}: "
            f"{fc.coverage_percent:.1f}% "
            f"({fc.uncovered_count} 行未覆盖)"
        )


def print_low_coverage_files(
    analyzer: CoverageAnalyzer,
    threshold: float = 50.0,
) -> None:
    """打印覆盖率低于阈值的文件。"""
    low = analyzer.get_low_coverage_files(threshold)
    if not low:
        print(f"\n3. 没有覆盖率低于 {threshold}% 的文件。")
        return

    print(f"\n3. 覆盖率低于 {threshold}% 的文件:")
    for fc in low:
        print(f"   {fc.file_path}: {fc.coverage_percent:.1f}%")


def generate_html_report() -> None:
    """生成 HTML 覆盖率报告。"""
    print("\n4. 生成 HTML 报告...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=backend",
            "--cov-report=html",
            "-q",
            "--tb=no",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        html_path = Path("htmlcov/index.html")
        if html_path.exists():
            print(f"   HTML 报告: {html_path.resolve()}")
        else:
            print("   HTML 报告生成完成，但未找到 htmlcov/index.html")
    else:
        print(f"   HTML 报告生成失败: {result.stderr[:200]}")


def main(argv: list[str] | None = None) -> int:
    """主入口函数。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 测试覆盖率检查工具",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="生成 HTML 覆盖率报告",
    )
    parser.add_argument(
        "--xml",
        type=str,
        default=None,
        help="从已有的 Cobertura XML 文件加载覆盖率数据",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=50.0,
        help="低覆盖率阈值 (默认 50%%)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="显示的未覆盖文件数量上限 (默认 10)",
    )
    args = parser.parse_args(argv)

    analyzer = CoverageAnalyzer()

    if args.xml:
        # 从 XML 文件加载
        xml_path = Path(args.xml)
        if not xml_path.exists():
            print(f"错误: XML 文件不存在: {xml_path}")
            return 1
        result = analyzer.load_xml(xml_path)
        if not result["success"]:
            print(f"错误: {result['error']}")
            return 1
    else:
        # 运行 pytest 覆盖率测试
        print("正在运行覆盖率测试...\n")
        result = analyzer.run_coverage()
        if not result["success"]:
            print(f"错误: {result['error']}")
            return 1

    # 输出报告
    print_summary(analyzer)
    print_uncovered_files(analyzer, limit=args.limit)
    print_low_coverage_files(analyzer, threshold=args.threshold)

    # 可选: 生成 HTML 报告
    if args.html:
        generate_html_report()

    return 0


if __name__ == "__main__":
    sys.exit(main())
