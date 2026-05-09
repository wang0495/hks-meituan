"""代码审查入口脚本。"""

from __future__ import annotations

import argparse
import sys

from backend.tools.code_reviewer import CodeReviewer, ReviewReport


def _print_separator(title: str) -> None:
    """打印分隔线标题。"""
    width = 50
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}\n")


def _print_report(report: ReviewReport, verbose: bool = False) -> None:
    """格式化打印审查报告。"""
    _print_separator("CityFlow 代码审查报告")

    for idx, result in enumerate(report.results, 1):
        icon = "PASS" if result.success else "FAIL"
        print(f"{idx}. [{icon}] {result.summary}")

        if verbose and result.output:
            # 只打印前 800 字符，避免刷屏
            preview = result.output[:800]
            if len(result.output) > 800:
                preview += "\n... (输出已截断)"
            print(preview)

        if result.errors and verbose:
            print(f"   stderr: {result.errors[:300]}")

    # 汇总
    _print_separator("汇总")
    print(f"  通过: {report.passed_count} / {len(report.results)}")
    print(f"  失败: {report.failed_count} / {len(report.results)}")

    if report.all_passed:
        print("\n  所有检查通过，代码质量良好。")
    else:
        print("\n  存在未通过的检查项，请根据输出修复后重新审查。")


def main(argv: list[str] | None = None) -> int:
    """主函数，返回退出码。"""
    parser = argparse.ArgumentParser(description="CityFlow 代码审查工具")
    parser.add_argument(
        "--source-dir",
        default="backend",
        help="待审查的源码目录 (默认: backend)",
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
    parser.add_argument(
        "--complexity-only",
        action="store_true",
        help="只运行复杂度分析",
    )

    args = parser.parse_args(argv)

    try:
        reviewer = CodeReviewer(source_dir=args.source_dir)
    except FileNotFoundError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    # 按参数选择运行哪些检查
    report = ReviewReport()

    if args.ruff_only:
        report.results.append(reviewer.run_ruff_check())
    elif args.mypy_only:
        report.results.append(reviewer.run_mypy_check())
    elif args.black_only:
        report.results.append(reviewer.run_black_check())
    elif args.complexity_only:
        report.results.append(reviewer.analyze_complexity())
        report.results.append(reviewer.analyze_maintainability())
    else:
        report = reviewer.run_all()

    _print_report(report, verbose=args.verbose)

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
