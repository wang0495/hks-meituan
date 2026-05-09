"""CityFlow 压力测试 (Locust)。

使用方法：
    # 安装 locust（如未安装）
    pip install locust

    # 启动压力测试（Web UI 模式）
    locust -f tests/locustfile.py --host=http://localhost:8000

    # 命令行模式（无 UI）
    locust -f tests/locustfile.py --host=http://localhost:8000 \
        --headless -u 50 -r 10 --run-time 60s

    # 参数说明：
    #   -u 50     : 最大并发用户数 50
    #   -r 10     : 每秒启动 10 个用户
    #   --run-time: 运行 60 秒
"""

from __future__ import annotations

import random

from locust import HttpUser, between, events, tag, task

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

REGIONS = ["珠海", "北京", "上海", "广州", "深圳", "成都", "杭州"]
CATEGORIES = ["文化", "美食", "景点", "公园", "购物", "娱乐"]
KEYWORDS = ["公园", "博物馆", "餐厅", "商场", "书店", "咖啡"]


# ---------------------------------------------------------------------------
# 用户行为定义
# ---------------------------------------------------------------------------


class CityFlowUser(HttpUser):
    """模拟 CityFlow 用户行为。

    权重分配：
    - 健康检查: 1（运维探活）
    - POI 搜索: 4（最常用）
    - POI 详情: 2
    - 距离矩阵: 1
    - 数据查询: 2
    - 路线规划: 1（最重，低频）
    """

    wait_time = between(0.5, 2.0)
    connection_timeout = 10.0
    network_timeout = 30.0

    # ---------------------------------------------------------------
    # 系统
    # ---------------------------------------------------------------

    @tag("system")
    @task(1)
    def health_check(self) -> None:
        """健康检查 — 轻量级，高频。"""
        self.client.get("/api/health", name="/api/health")

    # ---------------------------------------------------------------
    # POI 相关
    # ---------------------------------------------------------------

    @tag("poi")
    @task(4)
    def search_pois(self) -> None:
        """POI 搜索 — 随机筛选条件。"""
        payload: dict = {}
        if random.random() < 0.8:
            payload["region"] = random.choice(REGIONS)
        if random.random() < 0.5:
            payload["categories"] = [random.choice(CATEGORIES)]
        if random.random() < 0.2:
            payload["keyword"] = random.choice(KEYWORDS)
        if random.random() < 0.15:
            payload["min_rating"] = round(random.uniform(3.0, 4.5), 1)
        if random.random() < 0.1:
            payload["max_price"] = random.choice([0, 50, 100, 200, 500])

        self.client.post(
            "/api/poi/search",
            json=payload,
            name="/api/poi/search",
        )

    @tag("poi")
    @task(2)
    def poi_detail(self) -> None:
        """POI 详情 — 先搜索再查详情（模拟真实行为）。"""
        region = random.choice(REGIONS)
        resp = self.client.post(
            "/api/poi/search",
            json={"region": region},
            name="/api/poi/search [for detail]",
        )
        if resp.status_code == 200:
            pois = resp.json().get("pois", [])
            if pois:
                poi_id = random.choice(pois)["id"]
                self.client.get(
                    f"/api/poi/detail/{poi_id}",
                    name="/api/poi/detail/[id]",
                )

    @tag("poi")
    @task(1)
    def distance_matrix(self) -> None:
        """距离矩阵 — 随机选 3-8 个 POI。"""
        resp = self.client.post(
            "/api/poi/search",
            json={"region": random.choice(REGIONS)},
            name="/api/poi/search [for matrix]",
        )
        if resp.status_code == 200:
            pois = resp.json().get("pois", [])
            if len(pois) >= 3:
                count = min(random.randint(3, 8), len(pois))
                sample = random.sample(pois, count)
                self.client.post(
                    "/api/poi/distance-matrix",
                    json={"poi_ids": [p["id"] for p in sample]},
                    name="/api/poi/distance-matrix",
                )

    # ---------------------------------------------------------------
    # 数据查询
    # ---------------------------------------------------------------

    @tag("data")
    @task(2)
    def query_data(self) -> None:
        """数据查询 — 随机端点。"""
        endpoints = [
            "/api/data/",
            "/api/datasets",
            f"/api/poi/?city={random.choice(REGIONS)}",
            f"/api/order/?city={random.choice(REGIONS)}&hour={random.randint(0, 23)}",
            f"/api/road-traffic/?city={random.choice(REGIONS)}&hour={random.randint(0, 23)}",
        ]
        url = random.choice(endpoints)
        self.client.get(url, name=url.split("?")[0])

    # ---------------------------------------------------------------
    # 路线规划（SSE，最重的端点）
    # ---------------------------------------------------------------

    @tag("plan")
    @task(1)
    def plan_route(self) -> None:
        """路线规划 — SSE 流式请求，模拟真实用户输入。"""
        inputs = [
            "周末想一个人安静走走",
            "和朋友一起吃喝玩乐",
            "带孩子出去玩，不要太累",
            "想看看珠海的文化景点",
            "预算200以内，想逛逛公园",
            "浪漫约会路线",
        ]
        with self.client.post(
            "/api/plan",
            json={"user_input": random.choice(inputs)},
            name="/api/plan (SSE)",
            stream=True,
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                # 读取流直到 done 或 error
                for line in resp.iter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    if "event: done" in line or "event: error" in line:
                        break
                resp.success()
            else:
                resp.failure(f"Status code: {resp.status_code}")


# ---------------------------------------------------------------------------
# 事件钩子：统计输出
# ---------------------------------------------------------------------------


@events.test_start.add_listener
def on_test_start(environment: object, **kwargs: object) -> None:
    print("=" * 60)
    print("CityFlow 压力测试开始")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment: object, **kwargs: object) -> None:
    print("=" * 60)
    print("CityFlow 压力测试结束")
    print("=" * 60)
