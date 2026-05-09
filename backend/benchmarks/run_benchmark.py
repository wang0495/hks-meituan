#!/usr/bin/env python
"""CityFlow 性能基准测试脚本。

运行方式::

    # 在项目根目录下
    python -m backend.benchmarks.run_benchmark

    # 或指定迭代次数和并发数
    python -m backend.benchmarks.run_benchmark --iterations 200 --concurrency 10

测试端点：
    1. GET  /health          - 健康检查（轻量基准）
    2. POST /api/poi/search  - POI搜索（核心业务基准）
    3. GET  /health/detailed  - 详细健康检查（中等负载基准）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import httpx

from backend.benchmarks.baseline import BaselineBenchmark
from backend.benchmarks.metrics import PerformanceMetrics, check_thresholds

# ---------------------------------------------------------------------------
# 测试场景
# ---------------------------------------------------------------------------


def _create_client() -> httpx.AsyncClient:
    """创建测试用 AsyncClient。"""
    from backend.main import app

    return httpx.AsyncClient(app=app, base_url="http://testserver")


async def benchmark_health_check() -> None:
    """健康检查端点基准。"""
    async with _create_client() as client:
        resp = await client.get("/health")
        resp.raise_for_status()


async def benchmark_poi_search() -> None:
    """POI搜索端点基准。"""
    async with _create_client() as client:
        resp = await client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )
        resp.raise_for_status()


async def benchmark_detailed_health() -> None:
    """详细健康检查端点基准。"""
    async with _create_client() as client:
        resp = await client.get("/health/detailed")
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# 输出格式化
# ---------------------------------------------------------------------------


def _print_header(title: str) -> None:
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")


def _print_metrics(metrics: PerformanceMetrics) -> None:
    d = metrics.to_dict()
    print(f"  总请求数:      {d['total_requests']}")
    print(f"  成功:          {d['successful_requests']}")
    print(f"  失败:          {d['failed_requests']}")
    print(f"  总耗时:        {d['total_duration_seconds']:.2f}s")
    print(f"  吞吐量:        {d['requests_per_second']:.1f} req/s")
    print()
    print(f"  平均响应时间:  {d['avg_response_time_ms']:.2f} ms")
    print(f"  P50:           {d['p50_response_time_ms']:.2f} ms")
    print(f"  P95:           {d['p95_response_time_ms']:.2f} ms")
    print(f"  P99:           {d['p99_response_time_ms']:.2f} ms")
    print(f"  最小:          {d['min_response_time_ms']:.2f} ms")
    print(f"  最大:          {d['max_response_time_ms']:.2f} ms")
    print(f"  错误率:        {d['error_rate_percent']:.2f}%")


def _print_threshold_check(metrics: PerformanceMetrics) -> bool:
    """检查阈值，打印违规信息。返回 True 表示全部通过。"""
    violations = check_thresholds(metrics)
    if not violations:
        print("\n  [PASS] 所有指标均在阈值范围内")
        return True

    print(f"\n  [FAIL] 发现 {len(violations)} 项指标超限:")
    for v in violations:
        print(f"    {v}")
    return False


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


async def run_scenario(
    benchmark: BaselineBenchmark,
    name: str,
    func: Any,
    iterations: int,
    concurrency: int,
) -> tuple[PerformanceMetrics, bool]:
    """运行单个测试场景。"""
    _print_header(name)

    metrics = await benchmark.run_full(
        func,
        iterations=iterations,
        concurrency=concurrency,
        warmup=min(5, iterations // 10),
    )

    _print_metrics(metrics)
    passed = _print_threshold_check(metrics)

    return metrics, passed


async def main(args: argparse.Namespace) -> None:
    """主函数。"""
    benchmark = BaselineBenchmark()
    all_passed = True

    _print_header("CityFlow 性能基准测试")
    print(f"  迭代次数: {args.iterations}")
    print(f"  并发数:   {args.concurrency}")

    scenarios = [
        ("1. 健康检查 (/health)", benchmark_health_check),
        ("2. 详细健康检查 (/health/detailed)", benchmark_detailed_health),
        ("3. POI搜索 (/api/poi/search)", benchmark_poi_search),
    ]

    results: dict[str, PerformanceMetrics] = {}

    for name, func in scenarios:
        metrics, passed = await run_scenario(
            benchmark,
            name,
            func,
            iterations=args.iterations,
            concurrency=args.concurrency,
        )
        results[name] = metrics
        if not passed:
            all_passed = False

    # 汇总
    _print_header("汇总")
    for name, metrics in results.items():
        status = "PASS" if check_thresholds(metrics) == [] else "FAIL"
        print(
            f"  [{status}] {name}: "
            f"avg={metrics.avg_response_time:.1f}ms, "
            f"p95={metrics.p95_response_time:.1f}ms, "
            f"rps={metrics.requests_per_second:.1f}"
        )

    print(f"\n{'=' * 60}")
    if all_passed:
        print("  结果: 全部通过")
    else:
        print("  结果: 存在未达标项，请检查上方详情")
    print(f"{'=' * 60}\n")

    # 退出码：有失败则返回 1
    sys.exit(0 if all_passed else 1)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 性能基准测试",
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
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
