"""CityFlow 压力测试脚本。

包含三类测试场景：
1. 并发测试 -- 模拟多用户同时访问，逐步增加并发数
2. 长时间测试 -- 固定并发下持续运行一段时间，检测内存泄漏和性能退化
3. 峰值测试 -- 短时间内突发大量请求，测试系统峰值承载能力

用法:
    python -m backend.benchmarks.stress_test                     # 运行全部测试
    python -m backend.benchmarks.stress_test --test concurrent   # 仅并发测试
    python -m backend.benchmarks.stress_test --test endurance    # 仅长时间测试
    python -m backend.benchmarks.stress_test --test spike        # 仅峰值测试
    python -m backend.benchmarks.stress_test --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class RequestResult:
    """单次请求结果。"""

    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    success: bool
    error: str | None = None


@dataclass
class TestReport:
    """测试报告。"""

    test_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_s: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status_code_dist: dict[int, int] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def rps(self) -> float:
        """每秒请求数。"""
        if self.total_duration_s <= 0:
            return 0.0
        return self.total_requests / self.total_duration_s

    @property
    def success_rate(self) -> float:
        """成功率 (百分比)。"""
        if self.total_requests <= 0:
            return 0.0
        return self.successful_requests / self.total_requests * 100

    @property
    def avg_latency_ms(self) -> float:
        """平均延迟。"""
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    @property
    def p50_latency_ms(self) -> float:
        """P50 延迟。"""
        if not self.latencies_ms:
            return 0.0
        return statistics.median(self.latencies_ms)

    @property
    def p95_latency_ms(self) -> float:
        """P95 延迟。"""
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def p99_latency_ms(self) -> float:
        """P99 延迟。"""
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def max_latency_ms(self) -> float:
        """最大延迟。"""
        if not self.latencies_ms:
            return 0.0
        return max(self.latencies_ms)

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            "test_name": self.test_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_duration_s": round(self.total_duration_s, 2),
            "rps": round(self.rps, 2),
            "success_rate": round(self.success_rate, 2),
            "latency": {
                "avg_ms": round(self.avg_latency_ms, 2),
                "p50_ms": round(self.p50_latency_ms, 2),
                "p95_ms": round(self.p95_latency_ms, 2),
                "p99_ms": round(self.p99_latency_ms, 2),
                "max_ms": round(self.max_latency_ms, 2),
            },
            "status_code_distribution": self.status_code_dist,
            "unique_errors": list(set(self.errors))[:10],
        }


# ---------------------------------------------------------------------------
# 端点定义
# ---------------------------------------------------------------------------


@dataclass
class Endpoint:
    """测试端点配置。"""

    name: str
    method: str
    path: str
    payload: dict[str, Any] | None = None
    weight: int = 1  # 被选中的权重


ENDPOINTS: list[Endpoint] = [
    Endpoint(name="health", method="GET", path="/health", weight=3),
    Endpoint(
        name="poi_search",
        method="POST",
        path="/api/poi/search",
        payload={"region": "珠海"},
        weight=2,
    ),
    Endpoint(
        name="poi_search_beijing",
        method="POST",
        path="/api/poi/search",
        payload={"region": "北京", "categories": ["景点"]},
        weight=2,
    ),
    Endpoint(
        name="poi_detail",
        method="GET",
        path="/api/poi/detail/poi_001",
        weight=1,
    ),
    Endpoint(
        name="plan_v1",
        method="POST",
        path="/api/v1/plan",
        payload={"user_input": "周末想一个人安静走走"},
        weight=1,
    ),
    Endpoint(
        name="plan_v1_family",
        method="POST",
        path="/api/v1/plan",
        payload={"user_input": "带孩子去游乐园"},
        weight=1,
    ),
    Endpoint(
        name="metrics",
        method="GET",
        path="/metrics",
        weight=1,
    ),
]


def _pick_endpoint() -> Endpoint:
    """按权重随机选择一个端点。"""
    pool: list[Endpoint] = []
    for ep in ENDPOINTS:
        pool.extend([ep] * ep.weight)
    return random.choice(pool)


# ---------------------------------------------------------------------------
# 核心测试引擎
# ---------------------------------------------------------------------------


class StressTestEngine:
    """压力测试引擎。"""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base_url = base_url.rstrip("/")
        self._results_lock = asyncio.Lock()

    async def _make_request(
        self,
        client: httpx.AsyncClient,
        endpoint: Endpoint,
    ) -> RequestResult:
        """发送单次请求并记录结果。"""
        url = f"{self._base_url}{endpoint.path}"
        start = time.perf_counter()
        try:
            if endpoint.method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=endpoint.payload)
            latency_ms = (time.perf_counter() - start) * 1000
            return RequestResult(
                endpoint=endpoint.name,
                method=endpoint.method,
                status_code=resp.status_code,
                latency_ms=latency_ms,
                success=200 <= resp.status_code < 400,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return RequestResult(
                endpoint=endpoint.name,
                method=endpoint.method,
                status_code=0,
                latency_ms=latency_ms,
                success=False,
                error=str(exc),
            )

    async def _user_loop(
        self,
        user_id: int,
        duration_s: float,
        report: TestReport,
        think_time_range: tuple[float, float] = (0.1, 1.0),
    ) -> None:
        """单个虚拟用户的请求循环。"""
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=10),
        ) as client:
            deadline = time.time() + duration_s
            while time.time() < deadline:
                endpoint = _pick_endpoint()
                result = await self._make_request(client, endpoint)

                async with self._results_lock:
                    report.total_requests += 1
                    if result.success:
                        report.successful_requests += 1
                    else:
                        report.failed_requests += 1
                        if result.error:
                            report.errors.append(result.error)
                    report.latencies_ms.append(result.latency_ms)
                    report.status_code_dist[result.status_code] = (
                        report.status_code_dist.get(result.status_code, 0) + 1
                    )

                # 思考时间
                await asyncio.sleep(random.uniform(*think_time_range))

    # ------------------------------------------------------------------
    # 并发测试: 逐步增加并发用户数
    # ------------------------------------------------------------------

    async def run_concurrent_test(
        self,
        user_counts: list[int] | None = None,
        duration_per_level: int = 30,
    ) -> list[TestReport]:
        """并发测试。

        按 user_counts 中的并发数逐级测试，每级持续 duration_per_level 秒。
        """
        if user_counts is None:
            user_counts = [5, 10, 25, 50, 100]

        reports: list[TestReport] = []
        for count in user_counts:
            report = TestReport(
                test_name=f"concurrent_{count}_users",
                start_time=time.time(),
            )
            print(f"\n[并发测试] {count} 用户, {duration_per_level}s ...")

            tasks = [
                asyncio.create_task(self._user_loop(i, duration_per_level, report))
                for i in range(count)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            report.end_time = time.time()
            report.total_duration_s = report.end_time - report.start_time
            reports.append(report)
            self._print_report(report)

        return reports

    # ------------------------------------------------------------------
    # 长时间测试: 固定并发，持续运行
    # ------------------------------------------------------------------

    async def run_endurance_test(
        self,
        concurrent_users: int = 20,
        duration_minutes: int = 5,
        sample_interval_s: int = 30,
    ) -> TestReport:
        """长时间测试。

        检测内存泄漏、连接泄漏、性能退化。每 sample_interval_s 秒输出一次中间统计。
        """
        duration_s = duration_minutes * 60
        report = TestReport(
            test_name=f"endurance_{concurrent_users}users_{duration_minutes}min",
            start_time=time.time(),
        )
        print(f"\n[长时间测试] {concurrent_users} 用户, {duration_minutes} 分钟 ...")

        # 启动用户任务
        tasks = [
            asyncio.create_task(
                self._user_loop(i, duration_s, report, think_time_range=(0.5, 2.0))
            )
            for i in range(concurrent_users)
        ]

        # 定期输出中间统计
        async def _sample_loop() -> None:
            elapsed = 0.0
            while elapsed < duration_s:
                await asyncio.sleep(sample_interval_s)
                elapsed = time.time() - report.start_time
                async with self._results_lock:
                    n = report.total_requests
                print(
                    f"  [{elapsed:.0f}s] 已完成 {n} 请求, "
                    f"当前 RPS={n / elapsed:.1f}"
                )

        sample_task = asyncio.create_task(_sample_loop())
        await asyncio.gather(*tasks, return_exceptions=True)
        sample_task.cancel()
        try:
            await sample_task
        except asyncio.CancelledError:
            pass

        report.end_time = time.time()
        report.total_duration_s = report.end_time - report.start_time
        self._print_report(report)
        return report

    # ------------------------------------------------------------------
    # 峰值测试: 瞬间爆发大量请求
    # ------------------------------------------------------------------

    async def run_spike_test(
        self,
        spike_users: int = 200,
        spike_duration_s: int = 10,
        cooldown_s: int = 5,
        rounds: int = 3,
    ) -> list[TestReport]:
        """峰值测试。

        多轮突发请求，每轮 spike_users 个用户同时发起请求，持续 spike_duration_s 秒。
        轮间有 cooldown_s 冷却期。
        """
        reports: list[TestReport] = []
        for r in range(1, rounds + 1):
            report = TestReport(
                test_name=f"spike_round{r}_{spike_users}users",
                start_time=time.time(),
            )
            print(
                f"\n[峰值测试] 第 {r}/{rounds} 轮: "
                f"{spike_users} 用户, {spike_duration_s}s ..."
            )

            tasks = [
                asyncio.create_task(self._user_loop(i, spike_duration_s, report))
                for i in range(spike_users)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            report.end_time = time.time()
            report.total_duration_s = report.end_time - report.start_time
            reports.append(report)
            self._print_report(report)

            if r < rounds:
                print(f"  冷却 {cooldown_s}s ...")
                await asyncio.sleep(cooldown_s)

        return reports

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------

    @staticmethod
    def _print_report(report: TestReport) -> None:
        d = report.to_dict()
        lat = d["latency"]
        print(
            f"  结果: {d['total_requests']} 请求 | "
            f"RPS={d['rps']} | 成功率={d['success_rate']}%"
        )
        print(
            f"  延迟: avg={lat['avg_ms']:.1f}ms "
            f"p50={lat['p50_ms']:.1f}ms "
            f"p95={lat['p95_ms']:.1f}ms "
            f"p99={lat['p99_ms']:.1f}ms "
            f"max={lat['max_ms']:.1f}ms"
        )
        print(f"  状态码: {d['status_code_distribution']}")
        if d["unique_errors"]:
            print(f"  错误: {d['unique_errors'][:3]}")


# ---------------------------------------------------------------------------
# 报告导出
# ---------------------------------------------------------------------------


def save_reports(reports: list[TestReport], output_dir: Path | None = None) -> Path:
    """将测试报告保存为 JSON 文件。"""
    if output_dir is None:
        output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"stress_report_{timestamp}.json"

    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reports": [r.to_dict() for r in reports],
    }
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n报告已保存: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="CityFlow 压力测试")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API 基础地址 (默认 http://localhost:8000)",
    )
    parser.add_argument(
        "--test",
        choices=["concurrent", "endurance", "spike", "all"],
        default="all",
        help="要运行的测试类型 (默认 all)",
    )
    args = parser.parse_args()

    engine = StressTestEngine(base_url=args.base_url)
    all_reports: list[TestReport] = []

    print("=" * 60)
    print("  CityFlow 压力测试")
    print(f"  目标: {args.base_url}")
    print("=" * 60)

    if args.test in ("concurrent", "all"):
        reports = await engine.run_concurrent_test(
            user_counts=[5, 10, 25, 50, 100],
            duration_per_level=30,
        )
        all_reports.extend(reports)

    if args.test in ("endurance", "all"):
        report = await engine.run_endurance_test(
            concurrent_users=20,
            duration_minutes=5,
            sample_interval_s=30,
        )
        all_reports.append(report)

    if args.test in ("spike", "all"):
        reports = await engine.run_spike_test(
            spike_users=200,
            spike_duration_s=10,
            cooldown_s=5,
            rounds=3,
        )
        all_reports.extend(reports)

    # 汇总
    if all_reports:
        print("\n" + "=" * 60)
        print("  汇总")
        print("=" * 60)
        for r in all_reports:
            d = r.to_dict()
            print(
                f"  {d['test_name']:40s} | "
                f"RPS={d['rps']:8.1f} | "
                f"成功率={d['success_rate']:5.1f}% | "
                f"p95={d['latency']['p95_ms']:7.1f}ms"
            )

        save_reports(all_reports)


if __name__ == "__main__":
    asyncio.run(main())
