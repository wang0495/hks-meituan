"""代码格式化检查脚本 - 运行 Black、Ruff、isort 检查或自动修复。"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Tuple

from backend.tools.code_formatter import CodeFormatter


def print_report(report: Dict[str, object]) -> None:
    """打印格式化检查报告。

    Args:
        report: 检查结果字典
    """
    black_result = report["black"]  # type: ignore[index]
    ruff_result = report["ruff"]  # type: ignore[index]
    isort_result = report["isort"]  # type: ignore[index]

    print("=" * 50)
    print("  CityFlow 代码格式化检查报告")
    print("=" * 50)

    # Black 检查
    print("\n1. Black 格式检查")
    print("-" * 30)
    if black_result["success"]:  # type: ignore[index]
        print("   [PASS] 代码格式正确")
    else:
        print("   [FAIL] 代码格式需要调整")
        output = str(black_result["output"])  # type: ignore[index]
        if output:
            print(f"   详情: {output[:300]}")

    # Ruff 检查
    print("\n2. Ruff 代码检查")
    print("-" * 30)
    if ruff_result["success"]:  # type: ignore[index]
        print("   [PASS] 代码规范检查通过")
    else:
        print("   [FAIL] 发现代码规范问题:")
        output = str(ruff_result["output"])  # type: ignore[index]
        if output:
            print(f"   详情: {output[:300]}")

    # isort 检查
    print("\n3. isort 导入检查")
    print("-" * 30)
    if isort_result["success"]:  # type: ignore[index]
        print("   [PASS] 导入排序正确")
    else:
        print("   [FAIL] 导入需要重新排序")
        output = str(isort_result["output"])  # type: ignore[index]
        if output:
            print(f"   详情: {output[:300]}")

    # 总体结果
    print("\n" + "=" * 50)
    overall = report["overall"]  # type: ignore[index]
    if overall:
        print("  结果: ALL PASSED - 代码格式规范")
    else:
        print("  结果: ISSUES FOUND - 需要修复")
    print("=" * 50)


def run_check(formatter: CodeFormatter) -> Tuple[Dict[str, object], bool]:
    """运行代码格式检查。

    Args:
        formatter: CodeFormatter 实例

    Returns:
        Tuple[Dict, bool]: (检查报告, 是否通过)
    """
    print("正在检查代码格式...\n")
    report = formatter.check_all()
    print_report(report)
    return report, bool(report["overall"])


def run_fix(formatter: CodeFormatter) -> Dict[str, object]:
    """运行自动格式化修复。

    Args:
        formatter: CodeFormatter 实例

    Returns:
        Dict: 格式化结果
    """
    print("正在自动修复代码格式...\n")
    report = formatter.format_all()
    print_report(report)
    return report


def main() -> None:
    """主函数入口。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 代码格式化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.run_formatter          # 检查代码格式
  python -m backend.tools.run_formatter --fix    # 自动修复格式问题
  python -m backend.tools.run_formatter --dirs backend/ # 指定目录
        """,
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="自动修复代码格式问题（默认仅检查）",
    )

    parser.add_argument(
        "--dirs",
        nargs="+",
        default=["backend/", "tests/"],
        help="要检查的目录（默认: backend/ tests/）",
    )

    args = parser.parse_args()

    formatter = CodeFormatter(target_dirs=args.dirs)

    if args.fix:
        run_fix(formatter)
    else:
        _, passed = run_check(formatter)
        if not passed:
            print("\n提示: 运行以下命令自动修复:")
            print("  python -m backend.tools.run_formatter --fix")
            sys.exit(1)


if __name__ == "__main__":
    main()
