"""CityFlow API 自动化测试入口。

用法::

    # 确保服务已启动
    python -m tests.run_api_tests

    # 指定服务地址
    python -m tests.run_api_tests --base-url http://192.168.1.100:8000

    # 只跑边界测试
    python -m tests.run_api_tests --suite boundary

    # 并发执行
    python -m tests.run_api_tests --concurrency 4

    # 失败即停
    python -m tests.run_api_tests --fail-fast
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from tests.api_test_runner import APITestRunner
from tests.test_generator import CaseGenerator

SPEC_PATH = Path(__file__).parent.parent / "backend" / "api_spec.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CityFlow API 自动化测试")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API 服务地址 (默认 http://localhost:8000)",
    )
    parser.add_argument(
        "--suite",
        choices=["all", "functional", "boundary", "method", "spec"],
        default="all",
        help="测试套件: all=全部, functional=功能, boundary=边界, method=HTTP方法, spec=OpenAPI",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="并发数 (默认 1 = 串行)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="遇到失败立即停止",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="报告输出路径 (默认 api_test_report.json)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细日志",
    )
    return parser.parse_args()


def build_tests(suite: str) -> list[dict]:
    """根据 suite 参数选择用例。"""
    gen = CaseGenerator(SPEC_PATH if SPEC_PATH.exists() else None)

    if suite == "functional":
        return gen.generate_cityflow_tests()
    elif suite == "boundary":
        return gen.generate_boundary_tests()
    elif suite == "method":
        return gen.generate_method_not_allowed_tests()
    elif suite == "spec":
        return gen.generate_from_spec()
    else:  # all
        tests = gen.generate_cityflow_tests()
        tests.extend(gen.generate_boundary_tests())
        tests.extend(gen.generate_method_not_allowed_tests())
        return tests


async def main() -> int:
    args = parse_args()

    # 配置日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 构建用例
    tests = build_tests(args.suite)
    if not tests:
        print("没有测试用例可执行")
        return 1

    print(f"加载 {len(tests)} 条测试用例 (suite={args.suite})")
    print(f"目标服务: {args.base_url}")

    # 执行
    runner = APITestRunner(
        base_url=args.base_url,
        concurrency=args.concurrency,
        fail_fast=args.fail_fast,
    )

    report = await runner.run_tests(tests)

    # 输出报告
    runner.print_report(report)

    output_path = args.output or "api_test_report.json"
    saved = runner.save_report(report, output_path)
    print(f"JSON 报告已保存至: {saved}")

    # 返回退出码
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
