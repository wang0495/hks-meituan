#!/usr/bin/env python
"""CityFlow 基准测试套件 -- 命令行入口。

运行方式::

    # 默认配置
    python -m backend.benchmarks.run_suite

    # 自定义迭代和并发
    python -m backend.benchmarks.run_suite --iterations 200 --concurrency 5

    # 指定报告输出路径
    python -m backend.benchmarks.run_suite --output report.json

    # 只运行指定场景
    python -m backend.benchmarks.run_suite --only health,poi

测试场景：
    1. health   -- GET  /health           健康检查（轻量基准）
    2. poi      -- POST /api/poi/search   POI搜索（核心业务基准）
    3. detail   -- GET  /health/detailed   详细健康检查（中等负载基准）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx

from backend.benchmarks.suite import BenchmarkSuite, ScenarioResult

# ---------------------------------------------------------------------------
# 测试场景
# ---------------------------------------------------------------------------

_SCENARIO_NAMES: dict[str, str] = {
    "health": "健康检查 (/health)",
    "poi": "POI搜索 (/api/poi/search)",
    "detail": "详细健康检查 (/health/detailed)",
}


def _create_client() -> httpx.AsyncClient:
    """创建测试用 AsyncClient。"""
    from backend.main import app

    return httpx.AsyncClient(app=app, base_url="http://testserver")


async def _health_check() -> None:
    """健康检查端点。"""
    async with _create_client() as client:
        resp = await client.get("/health")
        resp.raise_for_status()


async def _poi_search() -> None:
    """POI搜索端点。"""
    async with _create_client() as client:
        resp = await client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )
        resp.raise_for_status()


async def _detailed_health() -> None:
    """详细健康检查端点。"""
    async with _create_client() as client:
        resp = await client.get("/health/detailed")
        resp.raise_for_status()


# 场景注册表：key -> (显示名, 异步函数)
_SCENARIOS: dict[str, tuple[str, Any]] = {
    "health": (_SCENARIO_NAMES["health"], _health_check),
    "poi": (_SCENARIO_NAMES["poi"], _poi_search),
    "detail": (_SCENARIO_NAMES["detail"], _detailed_health),
}


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------


def _print_header(title: str) -> None:
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def _on_start(name: str, idx: int) -> None:
    print(f"\n  [{idx + 1}] {name} ...")


def _on_end(result: ScenarioResult) -> None:
    m = result.metrics
    status = "PASS" if result.passed else "FAIL"
    print(
        f"       [{status}] avg={m.avg_response_time:.1f}ms, "
        f"p95={m.p95_response_time:.1f}ms, "
        f"rps={m.requests_per_second:.1f}, "
        f"errors={m.error_rate:.1f}%"
    )
    if result.violations:
        for v in result.violations:
            print(f"         -> {v}")


def _print_summary(report: Any) -> None:
    _print_header("汇总")
    for s in report.scenarios:
        m = s.metrics
        status = "PASS" if s.passed else "FAIL"
        print(
            f"  [{status}] {s.name:30s} | "
            f"avg={m.avg_response_time:7.1f}ms | "
            f"p95={m.p95_response_time:7.1f}ms | "
            f"rps={m.requests_per_second:6.1f} | "
            f"err={m.error_rate:5.1f}%"
        )

    print(f"\n{'=' * 60}")
    summary = report.to_dict()["summary"]
    print(
        f"  总场景: {summary['total_scenarios']} | "
        f"通过: {summary['passed']} | "
        f"失败: {summary['failed']} | "
        f"总耗时: {summary['total_duration_seconds']:.1f}s"
    )
    if report.all_passed:
        print("  结果: 全部通过")
    else:
        print("  结果: 存在未达标项，请检查上方详情")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    """主函数。"""
    # 确定要运行的场景
    if args.only:
        selected = [s.strip() for s in args.only.split(",")]
        unknown = [s for s in selected if s not in _SCENARIOS]
        if unknown:
            print(f"未知场景: {unknown}")
            print(f"可用场景: {list(_SCENARIOS.keys())}")
            sys.exit(1)
    else:
        selected = list(_SCENARIOS.keys())

    # 构建套件
    suite = BenchmarkSuite("CityFlow API 基准测试")

    for key in selected:
        name, func = _SCENARIOS[key]
        suite.add_scenario(
            name,
            func,
            iterations=args.iterations,
            concurrency=args.concurrency,
            warmup=min(5, args.iterations // 10),
        )

    # 运行
    _print_header("CityFlow 基准测试套件")
    print(f"  迭代次数: {args.iterations}")
    print(f"  并发数:   {args.concurrency}")
    print(f"  场景:     {', '.join(selected)}")

    report = await suite.run_all(
        on_scenario_start=_on_start,
        on_scenario_end=_on_end,
    )

    # 汇总输出
    _print_summary(report)

    # 保存报告
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = None  # 使用默认路径

    saved = suite.save_report(out_path, report=report)
    print(f"报告已保存: {saved}")

    # 退出码
    sys.exit(0 if report.all_passed else 1)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 基准测试套件",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=50,
        help="每个场景的测试迭代次数（默认 50）",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="并发数（默认 1，即顺序执行）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="报告输出路径（默认 backend/benchmarks/results/）",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="只运行指定场景，逗号分隔（如 health,poi）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
