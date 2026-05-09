"""CityFlow 压力测试优化器。

优化点：
    1. 修复 asyncio 并发下的竞态条件（使用 Lock 保护共享状态）
    2. 收集完整延迟分布（P50/P95/P99）
    3. 按端点分组统计
    4. 支持渐进式加压（ramp-up）
    5. 生成可序列化的详细报告

用法::

    from backend.benchmarks.stress_optimizer import StressTestOptimizer

    optimizer = StressTestOptimizer()
    result = await optimizer.run_test(concurrent_users=50, duration=30)
    report = optimizer.generate_report()
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class RequestMetric:
    """单次请求指标。"""

    latency_ms: float
    status_code: int
    success: bool
    endpoint: str
    error: str | None = None


@dataclass
class StressTestResult:
    """单次压力测试结果。"""

    concurrent_users: int
    duration_s: float
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status_code_dist: dict[int, int] = field(default_factory=dict)
    endpoint_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def rps(self) -> float:
        """每秒请求数。"""
        elapsed = self.end_time - self.start_time
        return self.total_requests / elapsed if elapsed > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """成功率（百分比）。"""
        if self.total_requests <= 0:
            return 0.0
        return self.successful_requests / self.total_requests * 100

    @property
    def avg_latency_ms(self) -> float:
        """平均延迟。"""
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

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
        return max(self.latencies_ms) if self.latencies_ms else 0.0

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化字典。"""
        return {
            "concurrent_users": self.concurrent_users,
            "duration_s": round(self.duration_s, 2),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
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
            "endpoint_stats": self.endpoint_stats,
            "unique_errors": list(set(self.errors))[:10],
        }


# ---------------------------------------------------------------------------
# 优化后的压力测试引擎
# ---------------------------------------------------------------------------


class StressTestOptimizer:
    """压力测试优化器。

    与 StressTestEngine 的区别：
    - 使用 asyncio.Lock 保护共享状态，避免竞态条件
    - 支持 ramp-up 渐进式加压
    - 收集按端点分组的统计
    - 结果对象可直接序列化
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._results: list[StressTestResult] = []
        self._lock = asyncio.Lock()

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> RequestMetric:
        """执行单次请求并返回指标。"""
        url = f"{self._base_url}{path}"
        start = time.perf_counter()
        try:
            if method.upper() == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=payload)

            latency_ms = (time.perf_counter() - start) * 1000
            return RequestMetric(
                latency_ms=latency_ms,
                status_code=resp.status_code,
                success=200 <= resp.status_code < 400,
                endpoint=path,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return RequestMetric(
                latency_ms=latency_ms,
                status_code=0,
                success=False,
                endpoint=path,
                error=str(exc),
            )

    async def _user_loop(
        self,
        user_id: int,
        duration_s: float,
        result: StressTestResult,
        endpoints: list[dict[str, Any]],
        think_time_range: tuple[float, float] = (0.05, 0.5),
    ) -> None:
        """单个虚拟用户的请求循环。"""
        import random

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout_s),
            limits=httpx.Limits(max_connections=10),
        ) as client:
            deadline = time.time() + duration_s
            while time.time() < deadline:
                # 轮询端点
                ep = endpoints[user_id % len(endpoints)]
                metric = await self._execute_request(
                    client,
                    method=ep["method"],
                    path=ep["path"],
                    payload=ep.get("payload"),
                )

                # 加锁更新共享状态
                async with self._lock:
                    result.total_requests += 1
                    if metric.success:
                        result.successful_requests += 1
                    else:
                        result.failed_requests += 1
                        if metric.error:
                            result.errors.append(metric.error)

                    result.latencies_ms.append(metric.latency_ms)
                    result.status_code_dist[metric.status_code] = (
                        result.status_code_dist.get(metric.status_code, 0) + 1
                    )

                    # 按端点统计
                    ep_stats = result.endpoint_stats.setdefault(
                        metric.endpoint,
                        {
                            "total": 0,
                            "success": 0,
                            "failed": 0,
                            "latencies": [],
                        },
                    )
                    ep_stats["total"] += 1
                    if metric.success:
                        ep_stats["success"] += 1
                    else:
                        ep_stats["failed"] += 1
                    ep_stats["latencies"].append(metric.latency_ms)

                await asyncio.sleep(random.uniform(*think_time_range))

    def _compute_endpoint_stats(
        self, result: StressTestResult
    ) -> dict[str, dict[str, Any]]:
        """计算各端点的统计摘要。"""
        summary: dict[str, dict[str, Any]] = {}
        for ep_name, stats in result.endpoint_stats.items():
            lats = stats["latencies"]
            total = stats["total"]
            summary[ep_name] = {
                "total": total,
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": (
                    round(stats["success"] / total * 100, 2) if total > 0 else 0.0
                ),
                "avg_ms": round(statistics.mean(lats), 2) if lats else 0.0,
                "p50_ms": round(statistics.median(lats), 2) if lats else 0.0,
                "p95_ms": (
                    round(sorted(lats)[int(len(lats) * 0.95)], 2) if lats else 0.0
                ),
            }
        return summary

    async def run_test(
        self,
        concurrent_users: int,
        duration: int,
        endpoints: list[dict[str, Any]] | None = None,
        ramp_up_s: float = 0.0,
    ) -> StressTestResult:
        """运行单次压力测试。

        Args:
            concurrent_users: 并发用户数
            duration: 测试持续时间（秒）
            endpoints: 测试端点列表，每项含 method/path/payload
            ramp_up_s: 渐进加压时间（秒），0 表示立即全部启动

        Returns:
            StressTestResult 包含完整测试结果
        """
        if endpoints is None:
            endpoints = [
                {"method": "GET", "path": "/health"},
                {
                    "method": "POST",
                    "path": "/api/poi/search",
                    "payload": {"region": "珠海"},
                },
            ]

        result = StressTestResult(
            concurrent_users=concurrent_users,
            duration_s=float(duration),
            start_time=time.time(),
        )

        if ramp_up_s > 0 and concurrent_users > 1:
            # 渐进式加压
            delay_per_user = ramp_up_s / (concurrent_users - 1)
            tasks: list[asyncio.Task[None]] = []
            for i in range(concurrent_users):
                task = asyncio.create_task(
                    self._user_loop(i, duration, result, endpoints)
                )
                tasks.append(task)
                if i < concurrent_users - 1:
                    await asyncio.sleep(delay_per_user)
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            # 立即全部启动
            tasks = [
                asyncio.create_task(self._user_loop(i, duration, result, endpoints))
                for i in range(concurrent_users)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        result.end_time = time.time()
        result.duration_s = result.end_time - result.start_time

        # 计算端点统计摘要
        result.endpoint_stats = self._compute_endpoint_stats(result)

        self._results.append(result)
        return result

    async def run_progressive_test(
        self,
        user_levels: list[int] | None = None,
        duration_per_level: int = 30,
        endpoints: list[dict[str, Any]] | None = None,
    ) -> list[StressTestResult]:
        """渐进式压力测试。

        逐步增加并发用户数，每级运行指定时间。

        Args:
            user_levels: 并发用户数列表，如 [10, 25, 50, 100]
            duration_per_level: 每级持续时间（秒）
            endpoints: 测试端点列表

        Returns:
            各级别的测试结果列表
        """
        if user_levels is None:
            user_levels = [10, 25, 50, 100]

        results: list[StressTestResult] = []
        for level in user_levels:
            print(f"  [压力测试] {level} 用户, {duration_per_level}s ...")
            result = await self.run_test(
                concurrent_users=level,
                duration=duration_per_level,
                endpoints=endpoints,
            )
            results.append(result)
            self._print_result(result)

        return results

    def generate_report(self) -> dict[str, Any]:
        """生成完整测试报告。"""
        return {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(self._results),
            "results": [r.to_dict() for r in self._results],
            "summary": self._generate_summary(),
        }

    def _generate_summary(self) -> dict[str, Any]:
        """生成汇总摘要。"""
        if not self._results:
            return {}

        return {
            "max_rps": max(r.rps for r in self._results),
            "max_concurrent_users": max(r.concurrent_users for r in self._results),
            "avg_success_rate": round(
                statistics.mean(r.success_rate for r in self._results), 2
            ),
            "overall_p95_ms": round(
                statistics.mean(r.p95_latency_ms for r in self._results), 2
            ),
        }

    @staticmethod
    def _print_result(result: StressTestResult) -> None:
        """打印单次测试结果。"""
        d = result.to_dict()
        lat = d["latency"]
        print(
            f"    RPS={d['rps']:.1f} | "
            f"成功率={d['success_rate']:.1f}% | "
            f"avg={lat['avg_ms']:.1f}ms "
            f"p95={lat['p95_ms']:.1f}ms "
            f"p99={lat['p99_ms']:.1f}ms"
        )
