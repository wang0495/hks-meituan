"""CityFlow Locust 压力测试配置。

用法:
    locust -f backend/benchmarks/locustfile.py --host http://localhost:8000
    locust -f backend/benchmarks/locustfile.py --host http://localhost:8000 --headless -u 50 -r 10 -t 2m

Web UI:
    运行后访问 http://localhost:8089 查看实时仪表盘

场景说明:
    - CityFlowUser:   模拟普通用户 (健康检查 + POI搜索 + 路线规划)
    - PowerUser:      模拟高频用户 (更高频率的路线规划和对话)
    - BrowseOnlyUser: 模拟仅浏览的用户 (只查 POI，不规划路线)
"""

from __future__ import annotations

import random

from locust import HttpUser, between, events, tag, task

# ---------------------------------------------------------------------------
# 普通用户 -- 混合操作
# ---------------------------------------------------------------------------


class CityFlowUser(HttpUser):
    """模拟普通用户的典型行为。

    操作分布:
      - 健康检查  : 30%
      - POI 搜索  : 30%
      - POI 详情  : 15%
      - 路线规划  : 15%
      - Metrics   : 10%
    """

    wait_time = between(1, 3)

    @tag("health")
    @task(3)
    def health_check(self) -> None:
        """基础健康检查。"""
        self.client.get("/health")

    @tag("poi", "search")
    @task(3)
    def search_pois_zhuhai(self) -> None:
        """搜索珠海 POI。"""
        self.client.post(
            "/api/poi/search",
            json={"region": "珠海"},
        )

    @tag("poi", "search")
    @task(2)
    def search_pois_beijing(self) -> None:
        """搜索北京景点。"""
        self.client.post(
            "/api/poi/search",
            json={"region": "北京", "categories": ["景点"]},
        )

    @tag("poi", "detail")
    @task(1)
    def poi_detail(self) -> None:
        """查询 POI 详情。"""
        poi_id = random.choice(
            [
                "poi_001",
                "poi_002",
                "poi_003",
                "poi_004",
                "poi_005",
            ]
        )
        self.client.get(f"/api/poi/detail/{poi_id}")

    @tag("plan")
    @task(1)
    def plan_route_relax(self) -> None:
        """规划休闲路线。"""
        self.client.post(
            "/api/v1/plan",
            json={"user_input": "周末想一个人安静走走"},
        )

    @tag("metrics")
    @task(1)
    def check_metrics(self) -> None:
        """查看 Prometheus 指标。"""
        self.client.get("/metrics")


# ---------------------------------------------------------------------------
# 高频用户 -- 频繁规划路线
# ---------------------------------------------------------------------------


class PowerUser(HttpUser):
    """模拟高频用户的典型行为。

    更频繁地调用路线规划接口，模拟深度使用场景。
    """

    wait_time = between(0.5, 1.5)
    weight = 2  # 权重低，占比少

    _plan_inputs = [
        "周末想一个人安静走走",
        "带孩子去游乐园",
        "和朋友聚会找好吃的",
        "情侣约会浪漫路线",
        "退休老人慢节奏出行",
        "摄影爱好者打卡路线",
        "文艺青年一日游",
    ]

    @tag("health")
    @task(2)
    def health_check(self) -> None:
        self.client.get("/health")

    @tag("poi", "search")
    @task(3)
    def search_pois(self) -> None:
        region = random.choice(["珠海", "北京", "上海", "广州", "深圳"])
        self.client.post("/api/poi/search", json={"region": region})

    @tag("plan")
    @task(4)
    def plan_route(self) -> None:
        user_input = random.choice(self._plan_inputs)
        self.client.post("/api/v1/plan", json={"user_input": user_input})

    @tag("poi", "distance")
    @task(1)
    def distance_matrix(self) -> None:
        """随机请求距离矩阵。"""
        ids = random.sample(
            [f"poi_{i:03d}" for i in range(1, 21)],
            k=min(5, 20),
        )
        self.client.post(
            "/api/poi/distance-matrix",
            json={"poi_ids": ids},
        )


# ---------------------------------------------------------------------------
# 浏览用户 -- 只看不规划
# ---------------------------------------------------------------------------


class BrowseOnlyUser(HttpUser):
    """模拟仅浏览的用户。

    只查看 POI 信息和健康检查，不触发路线规划。
    """

    wait_time = between(2, 5)
    weight = 1  # 占比最少

    @tag("health")
    @task(2)
    def health_check(self) -> None:
        self.client.get("/health")

    @tag("poi", "search")
    @task(4)
    def search_pois(self) -> None:
        region = random.choice(["珠海", "北京", "上海", "成都", "杭州"])
        self.client.post("/api/poi/search", json={"region": region})

    @tag("poi", "detail")
    @task(3)
    def poi_detail(self) -> None:
        poi_id = random.choice(
            [
                "poi_001",
                "poi_002",
                "poi_003",
                "poi_004",
                "poi_005",
                "poi_006",
                "poi_007",
                "poi_008",
                "poi_009",
                "poi_010",
            ]
        )
        self.client.get(f"/api/poi/detail/{poi_id}")


# ---------------------------------------------------------------------------
# 事件钩子: 测试开始/结束时输出提示
# ---------------------------------------------------------------------------


@events.test_start.add_listener
def on_test_start(environment: object, **kwargs: object) -> None:
    print("\n" + "=" * 50)
    print("  CityFlow Locust 压力测试开始")
    print("=" * 50)


@events.test_stop.add_listener
def on_test_stop(environment: object, **kwargs: object) -> None:
    print("\n" + "=" * 50)
    print("  CityFlow Locust 压力测试结束")
    print("=" * 50)
