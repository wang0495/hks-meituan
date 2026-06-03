"""CityFlow 性能测试脚本。

测试内容：
1. 各 API 端点的响应时间（单次 + 统计）
2. 并发请求处理能力
3. 内存泄漏检测
4. 缓存命中率对性能的影响
"""

from __future__ import annotations

import asyncio
import gc
import statistics
import time
from dataclasses import dataclass, field

import psutil
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

HEALTH_CHECK_ROUNDS = 50
POI_SEARCH_ROUNDS = 20
DATA_QUERY_ROUNDS = 20
DISTANCE_MATRIX_ROUNDS = 10
CONCURRENT_HEALTH_COUNT = 100
CONCURRENT_SEARCH_COUNT = 30
MEMORY_LEAK_ROUNDS = 100

# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


@dataclass
class EndpointStats:
    """单个端点的性能统计。"""

    name: str
    times: list[float] = field(default_factory=list)
    errors: int = 0
    status_codes: dict[int, int] = field(default_factory=dict)

    def record(self, elapsed: float, status_code: int) -> None:
        self.times.append(elapsed)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        if status_code >= 400:
            self.errors += 1

    @property
    def count(self) -> int:
        return len(self.times)

    def report(self) -> dict:
        if not self.times:
            return {"name": self.name, "count": 0, "error": "no data"}
        sorted_times = sorted(self.times)
        return {
            "name": self.name,
            "count": self.count,
            "errors": self.errors,
            "min_ms": round(sorted_times[0] * 1000, 2),
            "max_ms": round(sorted_times[-1] * 1000, 2),
            "avg_ms": round(statistics.mean(sorted_times) * 1000, 2),
            "median_ms": round(statistics.median(sorted_times) * 1000, 2),
            "p95_ms": round(sorted_times[int(len(sorted_times) * 0.95)] * 1000, 2),
            "p99_ms": round(sorted_times[int(len(sorted_times) * 0.99)] * 1000, 2),
            "stdev_ms": (
                round(statistics.stdev(sorted_times) * 1000, 2) if len(sorted_times) > 1 else 0
            ),
            "status_codes": self.status_codes,
        }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _measure(client: AsyncClient, method: str, url: str, **kwargs) -> tuple[float, int]:
    """发送请求并计时，返回 (耗时秒, 状态码)。"""
    start = time.perf_counter()
    if method == "get":
        resp = await client.get(url, **kwargs)
    else:
        resp = await client.post(url, **kwargs)
    elapsed = time.perf_counter() - start
    return elapsed, resp.status_code


def _print_report(stats: EndpointStats) -> None:
    """打印单个端点的统计报告。"""
    r = stats.report()
    print(f"\n--- {r['name']} ({r['count']} requests, {r['errors']} errors) ---")
    if r.get("error"):
        print(f"  {r['error']}")
        return
    print(f"  Min:     {r['min_ms']:.2f} ms")
    print(f"  Max:     {r['max_ms']:.2f} ms")
    print(f"  Avg:     {r['avg_ms']:.2f} ms")
    print(f"  Median:  {r['median_ms']:.2f} ms")
    print(f"  P95:     {r['p95_ms']:.2f} ms")
    print(f"  P99:     {r['p99_ms']:.2f} ms")
    print(f"  Stdev:   {r['stdev_ms']:.2f} ms")
    print(f"  Status:  {r['status_codes']}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """创建 ASGI 测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# 1. 单端点响应时间测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_response_time(client: AsyncClient) -> None:
    """测试健康检查端点的响应时间。"""
    stats = EndpointStats(name="GET /api/health")
    for _ in range(HEALTH_CHECK_ROUNDS):
        elapsed, status = await _measure(client, "get", "/api/health")
        stats.record(elapsed, status)
    _print_report(stats)
    r = stats.report()
    assert r["errors"] == 0, f"健康检查有 {r['errors']} 个错误"
    assert r["avg_ms"] < 50, f"健康检查平均响应过慢: {r['avg_ms']:.2f}ms"


@pytest.mark.asyncio
async def test_poi_search_response_time(client: AsyncClient) -> None:
    """测试 POI 搜索端点的响应时间（不同筛选条件）。"""
    payloads = [
        {"region": "珠海"},
        {"region": "珠海", "categories": ["文化"]},
        {"region": "珠海", "categories": ["美食"]},
        {"categories": ["景点"]},
        {"keyword": "公园"},
        {"min_rating": 4.0},
        {"max_price": 100},
        {"region": "珠海", "categories": ["文化"], "min_rating": 3.5},
    ]

    stats = EndpointStats(name="POST /api/poi/search")
    for i in range(POI_SEARCH_ROUNDS):
        payload = payloads[i % len(payloads)]
        elapsed, status = await _measure(client, "post", "/api/poi/search", json=payload)
        stats.record(elapsed, status)
    _print_report(stats)
    r = stats.report()
    assert r["errors"] == 0, f"POI搜索有 {r['errors']} 个错误"
    assert r["avg_ms"] < 200, f"POI搜索平均响应过慢: {r['avg_ms']:.2f}ms"


@pytest.mark.asyncio
async def test_poi_detail_response_time(client: AsyncClient) -> None:
    """测试 POI 详情端点的响应时间。"""
    # 先获取一个有效的 POI ID
    resp = await client.post("/api/poi/search", json={"region": "珠海", "categories": ["文化"]})
    data = resp.json()
    if not data.get("pois"):
        pytest.skip("没有可用的 POI 数据")

    poi_id = data["pois"][0]["id"]
    stats = EndpointStats(name=f"GET /api/poi/detail/{poi_id}")

    for _ in range(POI_SEARCH_ROUNDS):
        elapsed, status = await _measure(client, "get", f"/api/poi/detail/{poi_id}")
        stats.record(elapsed, status)
    _print_report(stats)
    r = stats.report()
    assert r["errors"] == 0
    assert r["avg_ms"] < 100, f"POI详情平均响应过慢: {r['avg_ms']:.2f}ms"


@pytest.mark.asyncio
async def test_distance_matrix_response_time(client: AsyncClient) -> None:
    """测试距离矩阵端点的响应时间。"""
    # 获取一些 POI ID
    resp = await client.post("/api/poi/search", json={"region": "珠海"})
    data = resp.json()
    pois = data.get("pois", [])
    if len(pois) < 3:
        pytest.skip("POI 数据不足")

    poi_ids = [p["id"] for p in pois[:10]]
    stats = EndpointStats(name="POST /api/poi/distance-matrix")

    for _ in range(DISTANCE_MATRIX_ROUNDS):
        elapsed, status = await _measure(
            client, "post", "/api/poi/distance-matrix", json={"poi_ids": poi_ids}
        )
        stats.record(elapsed, status)
    _print_report(stats)
    r = stats.report()
    assert r["errors"] == 0
    assert r["avg_ms"] < 500, f"距离矩阵平均响应过慢: {r['avg_ms']:.2f}ms"


@pytest.mark.asyncio
async def test_data_endpoint_response_time(client: AsyncClient) -> None:
    """测试数据查询端点的响应时间。"""
    endpoints = [
        ("GET /api/data/", "get", "/api/data/"),
        ("GET /api/datasets", "get", "/api/datasets"),
        ("GET /api/poi/?city=珠海", "get", "/api/poi/?city=珠海"),
        (
            "GET /api/order/?city=珠海&hour=12",
            "get",
            "/api/order/?city=珠海&hour=12",
        ),
        (
            "GET /api/road-traffic/?city=珠海&hour=12",
            "get",
            "/api/road-traffic/?city=珠海&hour=12",
        ),
    ]

    all_stats: list[EndpointStats] = []
    for name, method, url in endpoints:
        stats = EndpointStats(name=name)
        for _ in range(DATA_QUERY_ROUNDS):
            elapsed, status = await _measure(client, method, url)
            stats.record(elapsed, status)
        all_stats.append(stats)
        _print_report(stats)

    for stats in all_stats:
        r = stats.report()
        assert r["errors"] == 0, f"{r['name']} 有 {r['errors']} 个错误"


@pytest.mark.asyncio
async def test_plan_sse_response_time(client: AsyncClient) -> None:
    """测试路线规划 SSE 流式端点的响应时间。

    注意：此端点返回 SSE 流，需要特殊处理。
    我们测量到第一个事件的时间和总耗时。
    """
    stats = EndpointStats(name="POST /api/plan (SSE)")
    first_event_stats = EndpointStats(name="POST /api/plan (first event)")

    for _ in range(3):  # 路线规划较重，少跑几轮
        start = time.perf_counter()
        first_event_time: float | None = None
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
                        if line.startswith("event:") and first_event_time is None:
                            first_event_time = time.perf_counter() - start
                        if line.startswith("event: done") or line.startswith("event: error"):
                            break
        except Exception as e:
            stats.record(time.perf_counter() - start, 500)
            print(f"  SSE 请求异常: {e}")
            continue

        elapsed = time.perf_counter() - start
        stats.record(elapsed, 200)
        if first_event_time is not None:
            first_event_stats.record(first_event_time, 200)

    _print_report(stats)
    _print_report(first_event_stats)
    r = stats.report()
    assert r["errors"] == 0, f"路线规划有 {r['errors']} 个错误"


# ---------------------------------------------------------------------------
# 2. 并发处理能力测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_health_checks(client: AsyncClient) -> None:
    """测试并发健康检查的处理能力。"""

    async def _check() -> int:
        resp = await client.get("/api/health")
        return resp.status_code

    start = time.perf_counter()
    tasks = [_check() for _ in range(CONCURRENT_HEALTH_COUNT)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if isinstance(r, int) and r == 200)
    exceptions = sum(1 for r in results if isinstance(r, Exception))

    print(f"\n--- 并发健康检查 ({CONCURRENT_HEALTH_COUNT} 并发) ---")
    print(f"  成功: {success}/{CONCURRENT_HEALTH_COUNT}")
    print(f"  异常: {exceptions}")
    print(f"  总耗时: {elapsed:.3f}s")
    print(f"  吞吐量: {CONCURRENT_HEALTH_COUNT / elapsed:.1f} req/s")

    assert (
        success >= CONCURRENT_HEALTH_COUNT * 0.95
    ), f"并发健康检查成功率过低: {success}/{CONCURRENT_HEALTH_COUNT}"


@pytest.mark.asyncio
async def test_concurrent_poi_search(client: AsyncClient) -> None:
    """测试并发 POI 搜索的处理能力。"""
    search_payloads = [
        {"region": "珠海"},
        {"region": "珠海", "categories": ["文化"]},
        {"categories": ["美食"]},
        {"keyword": "公园"},
    ]

    async def _search(i: int) -> int:
        payload = search_payloads[i % len(search_payloads)]
        resp = await client.post("/api/poi/search", json=payload)
        return resp.status_code

    start = time.perf_counter()
    tasks = [_search(i) for i in range(CONCURRENT_SEARCH_COUNT)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if isinstance(r, int) and r == 200)
    exceptions = sum(1 for r in results if isinstance(r, Exception))

    print(f"\n--- 并发 POI 搜索 ({CONCURRENT_SEARCH_COUNT} 并发) ---")
    print(f"  成功: {success}/{CONCURRENT_SEARCH_COUNT}")
    print(f"  异常: {exceptions}")
    print(f"  总耗时: {elapsed:.3f}s")
    print(f"  吞吐量: {CONCURRENT_SEARCH_COUNT / elapsed:.1f} req/s")

    assert (
        success >= CONCURRENT_SEARCH_COUNT * 0.90
    ), f"并发POI搜索成功率过低: {success}/{CONCURRENT_SEARCH_COUNT}"


@pytest.mark.asyncio
async def test_concurrent_mixed_requests(client: AsyncClient) -> None:
    """测试混合并发请求（模拟真实场景）。"""

    async def _health() -> tuple[str, int]:
        resp = await client.get("/api/health")
        return "health", resp.status_code

    async def _search() -> tuple[str, int]:
        resp = await client.post("/api/poi/search", json={"region": "珠海"})
        return "search", resp.status_code

    async def _data() -> tuple[str, int]:
        resp = await client.get("/api/datasets")
        return "data", resp.status_code

    # 50 health + 30 search + 20 data = 100 total
    tasks = (
        [_health() for _ in range(50)]
        + [_search() for _ in range(30)]
        + [_data() for _ in range(20)]
    )

    start = time.perf_counter()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    success = sum(1 for r in results if isinstance(r, tuple) and r[1] == 200)
    by_type: dict[str, dict[str, int]] = {}
    for r in results:
        if isinstance(r, tuple):
            name, status = r
            if name not in by_type:
                by_type[name] = {"success": 0, "fail": 0}
            if status == 200:
                by_type[name]["success"] += 1
            else:
                by_type[name]["fail"] += 1

    print("\n--- 混合并发请求 (100 总计) ---")
    print(f"  总成功: {success}/100")
    print(f"  总耗时: {elapsed:.3f}s")
    print(f"  吞吐量: {100 / elapsed:.1f} req/s")
    for name, counts in by_type.items():
        print(f"  {name}: {counts['success']} 成功, {counts['fail']} 失败")

    assert success >= 90, f"混合并发请求成功率过低: {success}/100"


# ---------------------------------------------------------------------------
# 3. 内存泄漏检测
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_leak_detection(client: AsyncClient) -> None:
    """检测反复请求是否导致内存持续增长。"""
    gc.collect()
    process = psutil.Process()
    initial_mem = process.memory_info().rss / 1024 / 1024  # MB

    mem_samples: list[float] = []

    for i in range(MEMORY_LEAK_ROUNDS):
        await client.post("/api/poi/search", json={"region": "珠海"})
        if i % 20 == 0:
            gc.collect()
            current_mem = process.memory_info().rss / 1024 / 1024
            mem_samples.append(current_mem)

    final_mem = process.memory_info().rss / 1024 / 1024
    mem_increase = final_mem - initial_mem

    print(f"\n--- 内存泄漏检测 ({MEMORY_LEAK_ROUNDS} 轮) ---")
    print(f"  初始内存: {initial_mem:.1f} MB")
    print(f"  最终内存: {final_mem:.1f} MB")
    print(f"  内存增长: {mem_increase:.1f} MB")
    print(f"  采样点: {[f'{m:.1f}' for m in mem_samples]}")

    # 内存增长不应超过 50MB
    assert mem_increase < 50, f"疑似内存泄漏: 内存增长 {mem_increase:.1f} MB"


# ---------------------------------------------------------------------------
# 4. 缓存效果测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_effectiveness(client: AsyncClient) -> None:
    """测试缓存命中对响应时间的影响。"""
    poi_ids_resp = await client.post(
        "/api/poi/search", json={"region": "珠海", "categories": ["文化"]}
    )
    pois = poi_ids_resp.json().get("pois", [])
    if len(pois) < 5:
        pytest.skip("POI 数据不足")

    poi_ids = [p["id"] for p in pois[:10]]

    # 冷请求（第一次，缓存未命中）
    cold_times: list[float] = []
    for _ in range(5):
        from backend.services.cache import distance_cache

        distance_cache.clear()  # 清空缓存
        elapsed, _ = await _measure(
            client,
            "post",
            "/api/poi/distance-matrix",
            json={"poi_ids": poi_ids},
        )
        cold_times.append(elapsed)

    # 热请求（缓存命中）
    hot_times: list[float] = []
    for _ in range(5):
        elapsed, _ = await _measure(
            client,
            "post",
            "/api/poi/distance-matrix",
            json={"poi_ids": poi_ids},
        )
        hot_times.append(elapsed)

    cold_avg = statistics.mean(cold_times) * 1000
    hot_avg = statistics.mean(hot_times) * 1000
    speedup = cold_avg / hot_avg if hot_avg > 0 else float("inf")

    print("\n--- 缓存效果 (距离矩阵) ---")
    print(f"  冷请求平均: {cold_avg:.2f} ms")
    print(f"  热请求平均: {hot_avg:.2f} ms")
    print(f"  加速比: {speedup:.1f}x")


# ---------------------------------------------------------------------------
# 5. 数据量对性能的影响
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_scalability(client: AsyncClient) -> None:
    """测试不同筛选条件返回数据量对响应时间的影响。"""
    tests = [
        ("全量查询 (无筛选)", {}),
        ("城市筛选", {"region": "珠海"}),
        ("品类筛选", {"categories": ["文化"]}),
        ("复合筛选", {"region": "珠海", "categories": ["文化"], "min_rating": 4.0}),
        ("关键词搜索", {"keyword": "公园"}),
    ]

    print("\n--- 搜索可扩展性 ---")
    for name, payload in tests:
        times = []
        total = 0
        for _ in range(10):
            elapsed, status = await _measure(client, "post", "/api/poi/search", json=payload)
            times.append(elapsed)
            if not total:
                resp = await client.post("/api/poi/search", json=payload)
                total = resp.json().get("total", 0)
        avg_ms = statistics.mean(times) * 1000
        print(f"  {name}: {avg_ms:.2f}ms (返回 {total} 条)")
