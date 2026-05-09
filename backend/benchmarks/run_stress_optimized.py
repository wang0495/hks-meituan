#!/usr/bin/env python
"""CityFlow 优化压力测试脚本。

运行方式::

    # 在项目根目录下
    python -m backend.benchmarks.run_stress_optimized

    # 指定参数
    python -m backend.benchmarks.run_stress_optimized --base-url http://localhost:8000
    python -m backend.benchmarks.run_stress_optimized --test progressive --max-users 200

测试模式：
    quick       -- 快速测试（低/中并发各 30 秒）
    progressive -- 渐进式测试（逐步增加用户数）
    endurance   -- 长时间稳定性测试
    all         -- 运行全部测试
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from backend.benchmarks.stress_optimizer import StressTestOptimizer

# ---------------------------------------------------------------------------
# 默认端点配置
# ---------------------------------------------------------------------------


DEFAULT_ENDPOINTS = [
    {"method": "GET", "path": "/health"},
    {"method": "POST", "path": "/api/poi/search", "payload": {"region": "珠海"}},
    {
        "method": "POST",
        "path": "/api/poi/search",
        "payload": {"region": "北京", "categories": ["景点"]},
    },
    {"method": "GET", "path": "/health/detailed"},
]


# ---------------------------------------------------------------------------
# 测试场景
# ---------------------------------------------------------------------------


async def run_quick_test(optimizer: StressTestOptimizer) -> None:
    """快速测试：低并发 + 中并发。"""
    print("\n--- 快速测试 ---")

    print("\n[1/2] 低并发 (10 用户, 30s)")
    result_low = await optimizer.run_test(
        concurrent_users=10,
        duration=30,
        endpoints=DEFAULT_ENDPOINTS,
    )
    StressTestOptimizer._print_result(result_low)

    print("\n[2/2] 中并发 (50 用户, 30s)")
    result_mid = await optimizer.run_test(
        concurrent_users=50,
        duration=30,
        endpoints=DEFAULT_ENDPOINTS,
    )
    StressTestOptimizer._print_result(result_mid)


async def run_progressive_test(
    optimizer: StressTestOptimizer,
    max_users: int = 100,
    duration_per_level: int = 30,
) -> None:
    """渐进式测试：逐步增加并发数。"""
    print("\n--- 渐进式测试 ---")

    # 根据 max_users 生成级别
    levels = []
    level = 10
    while level <= max_users:
        levels.append(level)
        level = level * 2 if level < 50 else level + 50

    await optimizer.run_progressive_test(
        user_levels=levels,
        duration_per_level=duration_per_level,
        endpoints=DEFAULT_ENDPOINTS,
    )


async def run_endurance_test(
    optimizer: StressTestOptimizer,
    concurrent_users: int = 20,
    duration_minutes: int = 5,
) -> None:
    """长时间稳定性测试。"""
    print(f"\n--- 稳定性测试 ({concurrent_users} 用户, {duration_minutes} 分钟) ---")

    duration_s = duration_minutes * 60
    sample_interval_s = 30

    # 启动测试任务
    result_container: list = []

    async def _run() -> None:
        result = await optimizer.run_test(
            concurrent_users=concurrent_users,
            duration=duration_s,
            endpoints=DEFAULT_ENDPOINTS,
        )
        result_container.append(result)

    async def _progress() -> None:
        """定期输出进度。"""
        elapsed = 0
        while elapsed < duration_s:
            await asyncio.sleep(sample_interval_s)
            elapsed += sample_interval_s
            # 简单输出进度
            print(f"  [{elapsed}s / {duration_s}s] 测试进行中...")

    run_task = asyncio.create_task(_run())
    progress_task = asyncio.create_task(_progress())

    await run_task
    progress_task.cancel()
    try:
        await progress_task
    except asyncio.CancelledError:
        pass

    if result_container:
        print("\n稳定性测试结果:")
        StressTestOptimizer._print_result(result_container[0])


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------


def print_summary(optimizer: StressTestOptimizer) -> None:
    """打印测试汇总。"""
    report = optimizer.generate_report()

    print("\n" + "=" * 60)
    print("  测试汇总")
    print("=" * 60)

    for i, r in enumerate(report["results"], 1):
        lat = r["latency"]
        print(
            f"  [{i}] {r['concurrent_users']:>4d} 用户 | "
            f"RPS={r['rps']:>8.1f} | "
            f"成功率={r['success_rate']:>5.1f}% | "
            f"p95={lat['p95_ms']:>7.1f}ms"
        )

    summary = report.get("summary", {})
    if summary:
        print("\n  峰值 RPS:      {:.1f}".format(summary.get("max_rps", 0)))
        print("  平均成功率:    {:.1f}%".format(summary.get("avg_success_rate", 0)))
        print("  平均 P95 延迟: {:.1f}ms".format(summary.get("overall_p95_ms", 0)))

    print("=" * 60)


def save_report(
    optimizer: StressTestOptimizer,
    output_dir: Path | None = None,
) -> Path:
    """保存报告到 JSON 文件。"""
    if output_dir is None:
        output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"stress_optimized_{timestamp}.json"

    report = optimizer.generate_report()
    filepath.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n报告已保存: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="CityFlow 优化压力测试",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API 基础地址 (默认 http://localhost:8000)",
    )
    parser.add_argument(
        "--test",
        choices=["quick", "progressive", "endurance", "all"],
        default="quick",
        help="测试模式 (默认 quick)",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=100,
        help="渐进式测试最大用户数 (默认 100)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="每级测试持续时间秒数 (默认 30)",
    )
    parser.add_argument(
        "--endurance-users",
        type=int,
        default=20,
        help="稳定性测试并发用户数 (默认 20)",
    )
    parser.add_argument(
        "--endurance-minutes",
        type=int,
        default=5,
        help="稳定性测试持续分钟数 (默认 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="报告输出目录",
    )
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    """主函数。"""
    optimizer = StressTestOptimizer(base_url=args.base_url)

    print("=" * 60)
    print("  CityFlow 优化压力测试")
    print(f"  目标: {args.base_url}")
    print(f"  模式: {args.test}")
    print("=" * 60)

    if args.test in ("quick", "all"):
        await run_quick_test(optimizer)

    if args.test in ("progressive", "all"):
        await run_progressive_test(
            optimizer,
            max_users=args.max_users,
            duration_per_level=args.duration,
        )

    if args.test in ("endurance", "all"):
        await run_endurance_test(
            optimizer,
            concurrent_users=args.endurance_users,
            duration_minutes=args.endurance_minutes,
        )

    # 汇总
    print_summary(optimizer)

    # 保存报告
    output_dir = Path(args.output_dir) if args.output_dir else None
    save_report(optimizer, output_dir)

    # 检查是否有失败
    has_failures = any(r.success_rate < 95.0 for r in optimizer._results)
    if has_failures:
        print("\n[WARNING] 部分测试成功率低于 95%，请检查上方详情")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
