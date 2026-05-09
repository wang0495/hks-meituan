"""测试运行器：执行 pytest 并生成 HTML 报告和覆盖率报告。

功能：
1. 运行 pytest（支持选择标记过滤）
2. 生成 JUnit XML 报告
3. 生成 coverage 覆盖率报告
4. 调用 TestReportGenerator 生成 HTML 报告

用法：
    python -m backend.tools.run_tests
    python -m backend.tools.run_tests --slow          # 包含慢测试
    python -m backend.tools.run_tests --no-coverage    # 跳过覆盖率
    python -m backend.tools.run_tests --module backend.services.geo  # 只测某个模块
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent

# 输出文件路径
JUNIT_XML = ROOT / "test_results.xml"
COVERAGE_XML = ROOT / "coverage.xml"
REPORT_HTML = ROOT / "test_report.html"


def run_command(cmd: list[str], label: str) -> subprocess.CompletedProcess[str]:
    """运行子进程命令并打印状态。"""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  命令: {' '.join(cmd)}\n")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result


def run_tests(
    include_slow: bool = False,
    use_coverage: bool = True,
    module: str | None = None,
    output_html: str | Path = REPORT_HTML,
    verbose: bool = True,
) -> int:
    """运行测试并生成报告。

    Args:
        include_slow: 是否包含 @pytest.mark.slow 标记的测试
        use_coverage: 是否生成覆盖率报告
        module: 指定测试模块（如 backend.services.geo）
        output_html: HTML 报告输出路径
        verbose: 是否显示详细输出

    Returns:
        pytest 退出码（0=全部通过, 1=有失败, 2=运行错误）
    """
    # 构建 pytest 命令
    pytest_cmd = [sys.executable, "-m", "pytest"]

    # 测试路径
    if module:
        pytest_cmd.append(module)
    else:
        pytest_cmd.append("tests/")

    # JUnit XML 输出（供报告生成器解析）
    pytest_cmd.extend(["--junitxml", str(JUNIT_XML)])

    # 覆盖率
    if use_coverage:
        pytest_cmd.extend(
            [
                "--cov=backend",
                "--cov-report=xml:" + str(COVERAGE_XML),
                "--cov-report=term-missing",
            ]
        )

    # 标记过滤
    if not include_slow:
        pytest_cmd.extend(["-m", "not slow"])

    # 详细模式
    if verbose:
        pytest_cmd.append("-v")
    pytest_cmd.append("--tb=short")

    # 运行 pytest
    result = run_command(pytest_cmd, "运行 pytest 测试")

    # 生成 HTML 报告
    print(f"\n{'='*60}")
    print("  生成 HTML 测试报告")
    print(f"{'='*60}")

    try:
        from backend.tools.test_report import TestReportGenerator

        generator = TestReportGenerator(project_name="CityFlow")

        # 加载 JUnit XML 结果
        if JUNIT_XML.exists():
            generator.load_from_xml(JUNIT_XML)
            print(f"  [OK] 已加载测试结果: {JUNIT_XML}")
        else:
            print(f"  [WARN] JUnit XML 文件不存在: {JUNIT_XML}")

        # 加载覆盖率数据
        if use_coverage and COVERAGE_XML.exists():
            generator.load_coverage_xml(COVERAGE_XML)
            print(f"  [OK] 已加载覆盖率数据: {COVERAGE_XML}")

        # 生成 HTML 报告
        report_path = generator.save_report(output_html)
        print(f"  [OK] HTML 报告已生成: {report_path}")

        # 打印摘要
        summary = generator.generate_summary()
        print("\n  测试摘要:")
        print(f"    总数:   {summary.total}")
        print(f"    通过:   {summary.passed}")
        print(f"    失败:   {summary.failed}")
        print(f"    通过率: {summary.pass_rate:.1%}")
        print(f"    耗时:   {summary.total_duration:.2f}s")

    except ImportError as exc:
        print(f"  [ERROR] 无法导入报告生成器: {exc}")
    except Exception as exc:
        print(f"  [ERROR] 生成报告时出错: {exc}")

    return result.returncode


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.tools.run_tests                  # 运行全部测试
  python -m backend.tools.run_tests --slow           # 包含慢测试
  python -m backend.tools.run_tests --no-coverage    # 跳过覆盖率
  python -m backend.tools.run_tests --module tests/test_geo.py  # 指定模块
  python -m backend.tools.run_tests -o report.html   # 自定义报告路径
        """,
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        help="包含 @pytest.mark.slow 标记的测试",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="跳过覆盖率收集",
    )
    parser.add_argument(
        "--module",
        type=str,
        default=None,
        help="指定测试模块或文件（如 tests/test_geo.py）",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=str(REPORT_HTML),
        help=f"HTML 报告输出路径（默认: {REPORT_HTML}）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="静默模式（减少输出）",
    )

    args = parser.parse_args()

    exit_code = run_tests(
        include_slow=args.slow,
        use_coverage=not args.no_coverage,
        module=args.module,
        output_html=args.output,
        verbose=not args.quiet,
    )

    # 使用 pytest 的退出码
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
