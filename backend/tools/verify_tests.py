"""CityFlow 测试验证脚本：运行全部测试，生成报告，验证覆盖率。

功能：
1. 运行全部测试（复用 TestRunner）
2. 解析 pytest 输出，展示测试结果
3. 生成并展示覆盖率报告
4. 输出总体验证结论

用法：
    python -m backend.tools.verify_tests
    python -m backend.tools.verify_tests --coverage-threshold 70
    python -m backend.tools.verify_tests --include-slow
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass

from backend.tools.test_config import TestConfig
from backend.tools.test_runner import TestRunner, TestRunResult


@dataclass
class VerifyReport:
    """验证报告数据。"""

    test_result: TestRunResult
    coverage_result: TestRunResult | None
    coverage_pct: float
    coverage_threshold: float
    overall_pass: bool

    @property
    def tests_passed(self) -> bool:
        return self.test_result.success

    @property
    def coverage_passed(self) -> bool:
        return self.coverage_pct >= self.coverage_threshold


def parse_coverage_pct(output: str) -> float:
    """从 pytest --cov 输出中解析总覆盖率百分比。

    匹配形如：
        TOTAL                    1234    567    54%
    或：
        TOTAL                                   54%
    """
    for line in output.splitlines():
        if line.strip().startswith("TOTAL"):
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
            if m:
                return float(m.group(1))
    return 0.0


async def run_verify(
    *,
    coverage_threshold: float = 60.0,
    include_slow: bool = False,
) -> VerifyReport:
    """执行完整验证流程。

    Args:
        coverage_threshold: 覆盖率通过阈值（百分比）
        include_slow: 是否包含慢速测试

    Returns:
        VerifyReport 实例
    """
    cfg = TestConfig(
        coverage=True,
        exclude_slow=not include_slow,
    )
    runner = TestRunner(config=cfg)

    # 1. 运行全部测试（带覆盖率）
    print("=" * 60)
    print("  CityFlow 测试验证")
    print("=" * 60)

    print("\n[1/2] 运行全部测试（含覆盖率）...")
    test_result = await runner.run_with_coverage()

    # 解析覆盖率
    coverage_pct = parse_coverage_pct(test_result.stdout)

    # 覆盖率单独再跑一次（如果第一次没拿到覆盖率数据）
    coverage_result: TestRunResult | None = None
    if coverage_pct == 0.0 and not test_result.success:
        print("\n[2/2] 重新运行覆盖率收集...")
        coverage_result = await runner.run_with_coverage()
        coverage_pct = parse_coverage_pct(coverage_result.stdout)
    else:
        coverage_result = test_result

    overall = test_result.success and coverage_pct >= coverage_threshold

    return VerifyReport(
        test_result=test_result,
        coverage_result=coverage_result,
        coverage_pct=coverage_pct,
        coverage_threshold=coverage_threshold,
        overall_pass=overall,
    )


def print_report(report: VerifyReport) -> None:
    """打印验证报告。"""
    print("\n" + "=" * 60)
    print("  验证报告")
    print("=" * 60)

    # 测试结果
    print("\n[1] 测试结果")
    r = report.test_result
    if r.success:
        print("    状态: 通过")
    else:
        print("    状态: 失败")
    print(f"    总计: {r.test_count}")
    print(f"    通过: {r.passed}")
    print(f"    失败: {r.failed}")
    print(f"    错误: {r.errors}")
    print(f"    跳过: {r.skipped}")
    print(f"    耗时: {r.duration:.2f}s")

    if r.report_html:
        print(f"    报告: {r.report_html}")

    # 覆盖率
    print("\n[2] 代码覆盖率")
    pct = report.coverage_pct
    threshold = report.coverage_threshold
    passed = report.coverage_passed
    print(f"    覆盖率: {pct:.1f}%")
    print(f"    阈值:   {threshold:.1f}%")
    print(f"    状态:   {'通过' if passed else '未达标'}")

    # 总体结论
    print("\n" + "=" * 60)
    status = "通过" if report.overall_pass else "失败"
    print(f"  总体结论: {status}")
    print("=" * 60)


async def _cli_main() -> None:
    """CLI 异步入口。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 测试验证脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.verify_tests                          # 默认验证
  python -m backend.tools.verify_tests --coverage-threshold 70  # 覆盖率阈值 70%
  python -m backend.tools.verify_tests --include-slow           # 包含慢速测试
        """,
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=60.0,
        help="覆盖率通过阈值（百分比，默认 60）",
    )
    parser.add_argument(
        "--include-slow",
        action="store_true",
        help="包含慢速测试",
    )

    args = parser.parse_args()

    report = await run_verify(
        coverage_threshold=args.coverage_threshold,
        include_slow=args.include_slow,
    )

    print_report(report)
    sys.exit(0 if report.overall_pass else 1)


def main() -> None:
    """CLI 同步入口。"""
    asyncio.run(_cli_main())


if __name__ == "__main__":
    main()
