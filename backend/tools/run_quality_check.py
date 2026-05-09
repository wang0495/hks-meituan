"""代码质量检查入口脚本。"""

from __future__ import annotations

import argparse
import sys

from backend.tools.quality_checker import (QualityChecker, QualityCheckResult,
                                           QualityReport)


def _print_separator(title: str) -> None:
    """打印分隔线标题。"""
    width = 50
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


def _print_check_result(idx: int, result: QualityCheckResult, verbose: bool) -> None:
    """打印单项检查结果。"""
    icon = "PASS" if result.success else "FAIL"
    print(f"  {idx}. [{icon}] {result.summary}")

    if verbose and result.output:
        preview = result.output[:800]
        if len(result.output) > 800:
            preview += "\n... (输出已截断)"
        print(preview)

    if result.errors and verbose:
        print(f"     stderr: {result.errors[:300]}")


def _print_report(report: QualityReport, verbose: bool) -> None:
    """格式化打印质量报告。"""
    _print_separator("CityFlow 代码质量检查")

    for idx, result in enumerate(report.results, 1):
        _print_check_result(idx, result, verbose)

    _print_separator("汇总")
    print(f"  通过: {report.passed_count} / {len(report.results)}")
    print(f"  失败: {report.failed_count} / {len(report.results)}")
    print(f"  耗时: {report.total_duration_ms:.0f}ms")

    if report.overall_success:
        print("\n  所有检查通过，代码质量良好。")
    else:
        print("\n  存在未通过的检查项，请根据输出修复后重新检查。")


def main(argv: list[str] | None = None) -> int:
    """主函数，返回退出码。"""
    parser = argparse.ArgumentParser(description="CityFlow 代码质量检查工具")
    parser.add_argument(
        "--source-dir",
        default="backend",
        help="待检查的源码目录 (默认: backend)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示详细输出",
    )
    parser.add_argument(
        "--ruff-only",
        action="store_true",
        help="只运行 Ruff 检查",
    )
    parser.add_argument(
        "--mypy-only",
        action="store_true",
        help="只运行 Mypy 检查",
    )
    parser.add_argument(
        "--black-only",
        action="store_true",
        help="只运行 Black 检查",
    )

    args = parser.parse_args(argv)

    try:
        checker = QualityChecker(source_dir=args.source_dir)
    except FileNotFoundError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    # 按参数选择运行哪些检查
    if args.ruff_only:
        result = checker.run_ruff()
        report = QualityReport(ruff=result, results=[result])
    elif args.mypy_only:
        result = checker.run_mypy()
        report = QualityReport(mypy=result, results=[result])
    elif args.black_only:
        result = checker.run_black_check()
        report = QualityReport(black=result, results=[result])
    else:
        report = checker.generate_report()

    _print_report(report, verbose=args.verbose)

    return 0 if report.overall_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
