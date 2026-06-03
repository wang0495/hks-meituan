"""CityFlow 性能基准测试脚本。

独立运行：python tests/test_benchmark.py

功能：
1. 对各 API 端点进行多轮基准测试
2. 统计 avg / p50 / p95 / p99 / min / max
3. 结果保存到 tests/benchmark_results.json
4. 与 tests/baseline.json 比较，检测性能回归
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------

RESULTS_FILE = Path(__file__).parent / "benchmark_results.json"
BASELINE_FILE = Path(__file__).parent / "baseline.json"

# ---------------------------------------------------------------------------
# 统计辅助
# ---------------------------------------------------------------------------


def _calc_stats(times: list[float], iterations: int) -> dict[str, float]:
    """根据原始耗时列表计算统计数据，返回毫秒值。"""
    sorted_t = sorted(times)
    result: dict[str, float] = {
        "iterations": iterations,
        "avg_ms": round(statistics.mean(sorted_t) * 1000, 2),
        "p50_ms": round(statistics.median(sorted_t) * 1000, 2),
        "p95_ms": round(sorted_t[int(iterations * 0.95)] * 1000, 2),
        "p99_ms": round(sorted_t[int(iterations * 0.99)] * 1000, 2),
        "min_ms": round(sorted_t[0] * 1000, 2),
        "max_ms": round(sorted_t[-1] * 1000, 2),
    }
    if iterations > 1:
        result["stdev_ms"] = round(statistics.stdev(sorted_t) * 1000, 2)
    return result


# ---------------------------------------------------------------------------
# 核心类
# ---------------------------------------------------------------------------


class PerformanceBenchmark:
    """性能基准测试。"""

    def __init__(self) -> None:
        self.results: dict[str, object] = {}

    # ---- 入口 ----

    async def run_all_benchmarks(self) -> None:
        """运行所有基准测试。"""
        print("=== CityFlow 性能基准测试 ===\n")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await self.benchmark_health_check(client)
            await self.benchmark_poi_search(client)
            await self.benchmark_distance_matrix(client)
            await self.benchmark_route_planning(client)
            await self.benchmark_concurrency(client)

        self.save_results()
        self.compare_with_baseline()

    # ---- 1. 健康检查 ----

    async def benchmark_health_check(self, client: AsyncClient, iterations: int = 100) -> None:
        """健康检查基准。"""
        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            resp = await client.get("/api/health")
            times.append(time.perf_counter() - start)
            assert resp.status_code == 200, f"健康检查失败: {resp.status_code}"

        self.results["health_check"] = _calc_stats(times, iterations)
        avg = self.results["health_check"]["avg_ms"]  # type: ignore[index]
        print(f"  健康检查: avg={avg:.2f}ms")

    # ---- 2. POI 搜索 ----

    async def benchmark_poi_search(self, client: AsyncClient, iterations: int = 50) -> None:
        """POI 搜索基准。"""
        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            resp = await client.post(
                "/api/poi/search", json={"region": "珠海", "categories": ["文化"]}
            )
            times.append(time.perf_counter() - start)
            assert resp.status_code == 200, f"POI搜索失败: {resp.status_code}"

        self.results["poi_search"] = _calc_stats(times, iterations)
        avg = self.results["poi_search"]["avg_ms"]  # type: ignore[index]
        print(f"  POI搜索: avg={avg:.2f}ms")

    # ---- 3. 距离矩阵 ----

    async def benchmark_distance_matrix(self, client: AsyncClient, iterations: int = 20) -> None:
        """距离矩阵基准。"""
        # 先获取一些 POI
        resp = await client.post("/api/poi/search", json={"region": "珠海"})
        data = resp.json()
        pois = data.get("pois", [])
        if len(pois) < 3:
            print("  距离矩阵: 跳过（POI 数据不足）")
            return

        poi_ids = [p["id"] for p in pois[:10]]

        times: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            resp = await client.post("/api/poi/distance-matrix", json={"poi_ids": poi_ids})
            times.append(time.perf_counter() - start)
            assert resp.status_code == 200, f"距离矩阵失败: {resp.status_code}"

        stats = _calc_stats(times, iterations)
        stats["poi_count"] = len(poi_ids)
        self.results["distance_matrix"] = stats
        avg = stats["avg_ms"]
        print(f"  距离矩阵: avg={avg:.2f}ms ({len(poi_ids)} POIs)")

    # ---- 4. 路线规划（SSE） ----

    async def benchmark_route_planning(self, client: AsyncClient, iterations: int = 5) -> None:
        """路线规划基准（SSE 流式端点）。"""
        times: list[float] = []
        first_event_times: list[float] = []
        errors = 0

        for _ in range(iterations):
            start = time.perf_counter()
            first_event: float | None = None
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://testserver",
                ) as sse_client:
                    async with sse_client.stream(
                        "POST",
                        "/api/plan",
                        json={"user_input": "周末想一个人安静走走"},
                        timeout=30.0,
                    ) as resp:
                        async for line in resp.aiter_lines():
                            if line.startswith("event:") and first_event is None:
                                first_event = time.perf_counter() - start
                            if line.startswith("event: done") or line.startswith("event: error"):
                                break
            except Exception:
                errors += 1
                times.append(time.perf_counter() - start)
                continue

            elapsed = time.perf_counter() - start
            times.append(elapsed)
            if first_event is not None:
                first_event_times.append(first_event)

        if not times:
            print("  路线规划: 跳过（无有效数据）")
            return

        stats = _calc_stats(times, iterations)
        stats["errors"] = errors
        if first_event_times:
            sorted_fe = sorted(first_event_times)
            stats["first_event_avg_ms"] = round(statistics.mean(sorted_fe) * 1000, 2)
            stats["first_event_p50_ms"] = round(statistics.median(sorted_fe) * 1000, 2)
        self.results["route_planning"] = stats
        avg = stats["avg_ms"]
        print(f"  路线规划: avg={avg:.2f}ms ({errors} errors)")

    # ---- 5. 并发 ----

    async def benchmark_concurrency(self, client: AsyncClient, concurrent_users: int = 10) -> None:
        """并发基准。"""

        async def _single_request() -> float:
            start = time.perf_counter()
            await client.get("/api/health")
            return time.perf_counter() - start

        wall_start = time.perf_counter()
        tasks = [_single_request() for _ in range(concurrent_users)]
        times = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - wall_start

        self.results["concurrency"] = {
            "concurrent_users": concurrent_users,
            "total_time_ms": round(total_time * 1000, 2),
            "avg_response_ms": round(statistics.mean(times) * 1000, 2),
            "throughput_rps": round(concurrent_users / total_time, 2),
        }
        rps = self.results["concurrency"]["throughput_rps"]  # type: ignore[index]
        print(f"  并发测试: {concurrent_users}用户, 吞吐量={rps:.2f} req/s")

    # ---- 持久化 ----

    def save_results(self) -> None:
        """保存测试结果到 JSON 文件。"""
        self.results["timestamp"] = datetime.now(UTC).isoformat()
        RESULTS_FILE.write_text(
            json.dumps(self.results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n结果已保存到 {RESULTS_FILE}")

    def compare_with_baseline(self) -> None:
        """与基线比较，检测性能回归。"""
        if not BASELINE_FILE.exists():
            print("未找到基线文件，当前结果将作为基线")
            self._save_as_baseline()
            return

        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))

        print("\n=== 性能比较 ===")
        regression_detected = False
        for key in ["health_check", "poi_search", "distance_matrix", "route_planning"]:
            if key not in self.results or key not in baseline:
                continue

            current_ms: float = self.results[key]["avg_ms"]  # type: ignore[index]
            base_ms: float = baseline[key]["avg_ms"]  # type: ignore[index]
            if base_ms == 0:
                continue
            change = (current_ms - base_ms) / base_ms * 100

            if abs(change) < 10:
                status = "OK"
            elif abs(change) < 20:
                status = "WARN"
            else:
                status = "FAIL"
                regression_detected = True

            print(
                f"  [{status}] {key}: {current_ms:.2f}ms "
                f"(基线: {base_ms:.2f}ms, 变化: {change:+.1f}%)"
            )

        if regression_detected:
            print("\n检测到性能回归！")
        else:
            print("\n性能检查通过")

    def _save_as_baseline(self) -> None:
        """将当前结果保存为基线。"""
        BASELINE_FILE.write_text(
            json.dumps(self.results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"基线已保存到 {BASELINE_FILE}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main() -> None:
    benchmark = PerformanceBenchmark()
    asyncio.run(benchmark.run_all_benchmarks())


if __name__ == "__main__":
    main()
