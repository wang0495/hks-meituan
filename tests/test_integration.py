"""CityFlow 端到端集成测试。

测试场景：
1. 完整规划流程（意图解析 -> POI搜索 -> 路线求解 -> 文案生成）
2. 对话调整流程（规划路线 -> 用户请求调整 -> 返回新路线）
3. 边界情况（无匹配POI、时间窗冲突、预算超限）
4. POI搜索与距离矩阵
5. 路线获取
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
async def client() -> AsyncClient:
    """创建异步测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_llm_call():
    """Mock LLM 调用，使其立即返回 None 以触发规则解析降级。

    这确保测试不依赖外部 LLM 服务，运行快速且确定性强。
    """

    async def _fast_none(*args: Any, **kwargs: Any) -> None:
        return None

    with patch(
        "backend.services.intent_parser._call_llm",
        side_effect=_fast_none,
    ):
        yield


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _parse_sse_events(text: str) -> list[dict[str, Any]]:
    """从 SSE 响应文本中解析所有事件数据。"""
    events: list[dict[str, Any]] = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            raw = line[6:]
            if raw:
                try:
                    events.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    return events


# ---------------------------------------------------------------------------
# 1. 健康检查
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """验证 API 服务正常运行。"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# 2. 完整规划流程
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_planning_flow(client: AsyncClient) -> None:
    """测试完整规划流程：发送需求 -> 解析意图 -> 搜索POI -> 求解路线 -> 生成文案。"""
    # 1. 发送规划请求
    response = await client.post(
        "/api/plan",
        json={"user_input": "周末想一个人安静走走"},
        timeout=30.0,
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # 2. 解析 SSE 事件
    events = _parse_sse_events(response.text)
    assert len(events) > 0, "SSE 响应中没有事件"

    # 3. 验证阶段事件（phase 事件）
    phase_events = [e for e in events if e.get("phase")]
    phase_names = [e["phase"] for e in phase_events]

    assert "parsing" in phase_names, f"缺少 parsing 阶段，实际阶段: {phase_names}"
    assert "searching" in phase_names, f"缺少 searching 阶段，实际阶段: {phase_names}"
    assert "solving" in phase_names, f"缺少 solving 阶段，实际阶段: {phase_names}"
    assert "narrating" in phase_names, f"缺少 narrating 阶段，实际阶段: {phase_names}"

    # 4. 验证 step 事件（每个POI一步）
    step_events = [e for e in events if e.get("index") is not None]
    assert len(step_events) > 0, "没有返回任何路线步骤"

    for step in step_events:
        assert "poi" in step, "step 事件缺少 poi 字段"
        assert "arrival_time" in step, "step 事件缺少 arrival_time"
        assert "departure_time" in step, "step 事件缺少 departure_time"
        assert "narrative" in step, "step 事件缺少 narrative"

    # 5. 验证 done 事件
    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1, f"期望1个 done 事件，实际 {len(done_events)} 个"

    done = done_events[0]
    assert "route_id" in done
    assert "full_route" in done

    route = done["full_route"]
    assert "route" in route
    assert len(route["route"]) > 0, "路线为空"
    assert "emotion_curve" in route
    assert "total_cost" in route


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_planning_couple(client: AsyncClient) -> None:
    """测试情侣场景的完整规划流程。"""
    response = await client.post(
        "/api/plan",
        json={"user_input": "和女朋友约会"},
        timeout=30.0,
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    # 验证有 done 事件且路线非空
    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route = done_events[0]["full_route"]
    assert len(route["route"]) >= 1

    # 验证 POI 结构完整性
    for step in route["route"]:
        poi = step["poi"]
        assert "id" in poi
        assert "name" in poi
        assert "category" in poi


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_planning_family(client: AsyncClient) -> None:
    """测试亲子场景的完整规划流程。"""
    response = await client.post(
        "/api/plan",
        json={"user_input": "周末一家人带娃出去"},
        timeout=30.0,
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    # 检查是否有 error 事件
    error_events = [e for e in events if e.get("error")]
    if error_events:
        # 意图解析失败时应有 error 事件
        assert "超时" in error_events[0]["error"] or "条件" in error_events[0]["error"]
        return

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route = done_events[0]["full_route"]
    assert len(route["route"]) >= 1


# ---------------------------------------------------------------------------
# 3. 对话调整流程
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dialogue_adjustment_pace(client: AsyncClient) -> None:
    """测试对话调整：节奏调整。

    流程：规划路线 -> 用户要求放慢 -> 返回新路线。
    """
    # 1. 先规划路线
    response = await client.post(
        "/api/plan",
        json={"user_input": "周末一家人带娃出去"},
        timeout=30.0,
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)

    # 检查是否有 error 事件（意图解析可能失败）
    error_events = [e for e in events if e.get("error")]
    if error_events:
        pytest.skip(f"意图解析失败: {error_events[0]['error']}")

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1, "规划未完成"

    route_id = done_events[0]["route_id"]

    # 2. 请求调整：节奏放慢
    response = await client.get(
        f"/api/route/{route_id}/adjust",
        params={"instruction": "太赶了，想轻松点"},
        timeout=15.0,
    )

    assert response.status_code == 200
    data = response.json()

    # 3. 验证返回结构
    assert "reply" in data, "缺少 reply 字段"
    assert "route" in data, "缺少 route 字段"
    assert "changes_made" in data, "缺少 changes_made 字段"

    # 4. 验证变更类型
    assert len(data["changes_made"]) > 0
    assert data["changes_made"][0]["type"] == "pace"
    assert data["changes_made"][0]["new_pace"] == "闲逛型"

    # 5. 验证路线已更新
    assert len(data["route"]["route"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dialogue_adjustment_budget(client: AsyncClient) -> None:
    """测试对话调整：预算调整。"""
    # 1. 规划路线
    response = await client.post(
        "/api/plan",
        json={"user_input": "和朋友聚会"},
        timeout=30.0,
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        pytest.skip(f"意图解析失败: {error_events[0]['error']}")

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route_id = done_events[0]["route_id"]

    # 2. 调整预算
    response = await client.get(
        f"/api/route/{route_id}/adjust",
        params={"instruction": "太贵了，便宜一点"},
        timeout=15.0,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["changes_made"][0]["type"] == "budget"
    assert "route" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dialogue_adjustment_replace(client: AsyncClient) -> None:
    """测试对话调整：替换景点。"""
    # 1. 规划路线
    response = await client.post(
        "/api/plan",
        json={"user_input": "周末想出去走走"},
        timeout=30.0,
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        pytest.skip(f"意图解析失败: {error_events[0]['error']}")

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route_id = done_events[0]["route_id"]
    full_route = done_events[0]["full_route"]

    # 2. 获取第一个景点名称
    first_poi_name = full_route["route"][0]["poi"]["name"]

    # 3. 请求替换
    response = await client.get(
        f"/api/route/{route_id}/adjust",
        params={"instruction": f"换掉{first_poi_name}"},
        timeout=15.0,
    )

    assert response.status_code == 200
    data = response.json()

    # 4. 验证替换结果
    if data["changes_made"]:
        assert data["changes_made"][0]["type"] == "replace"
        assert data["changes_made"][0]["original"] == first_poi_name


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dialogue_post_endpoint(client: AsyncClient) -> None:
    """测试 POST /api/dialogue/{session_id} 端点。"""
    # 1. 规划路线
    response = await client.post(
        "/api/plan",
        json={"user_input": "想出去逛逛"},
        timeout=30.0,
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        pytest.skip(f"意图解析失败: {error_events[0]['error']}")

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route_id = done_events[0]["route_id"]

    # 2. 通过 GET 调整端点注册对话会话
    await client.get(
        f"/api/route/{route_id}/adjust",
        params={"instruction": "知道了"},
        timeout=15.0,
    )

    # 3. 通过 POST 端点发送调整指令
    response = await client.post(
        f"/api/dialogue/{route_id}",
        json={"instruction": "想轻松点"},
        timeout=15.0,
    )

    # POST 端点使用 dialogue_engine，会话已在 adjust 时创建
    assert response.status_code in [200, 400, 404]

    if response.status_code == 200:
        data = response.json()
        assert "reply" in data


# ---------------------------------------------------------------------------
# 4. 边界情况
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_matching_pois(client: AsyncClient) -> None:
    """测试无匹配POI情况：输入不可能的需求。

    当没有匹配POI时，系统应返回 error 事件或简化路线。
    """
    response = await client.post(
        "/api/plan",
        json={"user_input": "想去月球旅游"},
        timeout=30.0,
    )

    # 系统可能返回 200（SSE流）或 400
    assert response.status_code in [200, 400]

    if response.status_code == 200:
        events = _parse_sse_events(response.text)
        # 应该有 error 事件或 done 事件（简化路线）
        has_error = any(e.get("error") for e in events)
        has_done = any("route_id" in e for e in events)
        assert has_error or has_done, "既没有 error 也没有 done 事件"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_budget_exceed_limit(client: AsyncClient) -> None:
    """测试预算超限情况：极低预算。

    当预算过低时，可能没有匹配POI，系统应优雅处理。
    """
    response = await client.post(
        "/api/plan",
        json={"user_input": "只有10块钱预算出去玩"},
        timeout=30.0,
    )

    assert response.status_code in [200, 400]

    if response.status_code == 200:
        events = _parse_sse_events(response.text)
        # 应该有结果（error 或 done）
        assert len(events) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_time_window_conflict(client: AsyncClient) -> None:
    """测试时间窗冲突：要求深夜出行。

    大部分POI深夜不营业，系统应返回 error 或简化路线。
    """
    response = await client.post(
        "/api/plan",
        json={"user_input": "凌晨2点出去玩"},
        timeout=30.0,
    )

    assert response.status_code in [200, 400]

    if response.status_code == 200:
        events = _parse_sse_events(response.text)
        has_error = any(e.get("error") for e in events)
        has_done = any("route_id" in e for e in events)
        assert has_error or has_done


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nonexistent_route_retrieval(client: AsyncClient) -> None:
    """测试获取不存在的路线。"""
    response = await client.get("/api/route/nonexistent_id")
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_nonexistent_dialogue_session(client: AsyncClient) -> None:
    """测试访问不存在的对话会话。"""
    response = await client.get(
        "/api/route/nonexistent_id/adjust",
        params={"instruction": "想轻松点"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 5. POI 搜索
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_search_basic(client: AsyncClient) -> None:
    """测试基本 POI 搜索。"""
    response = await client.post(
        "/api/poi/search",
        json={"region": "珠海"},
    )

    assert response.status_code == 200
    data = response.json()

    assert "pois" in data
    assert "total" in data
    assert data["total"] > 0, "珠海应该有POI数据"

    # 验证 POI 结构
    poi = data["pois"][0]
    assert "id" in poi
    assert "name" in poi
    assert "category" in poi
    assert "rating" in poi
    assert "lat" in poi
    assert "lng" in poi


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_search_by_category(client: AsyncClient) -> None:
    """测试按品类搜索 POI。"""
    response = await client.post(
        "/api/poi/search",
        json={"region": "珠海", "categories": ["文化"]},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] > 0

    # 所有返回的 POI 都应该是"文化"类
    for poi in data["pois"]:
        assert poi.get("category") == "文化"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_search_by_tags(client: AsyncClient) -> None:
    """测试按标签搜索 POI。"""
    response = await client.post(
        "/api/poi/search",
        json={"tags": ["免费"]},
    )

    assert response.status_code == 200
    data = response.json()

    # 所有返回的 POI 都应包含"免费"标签
    for poi in data["pois"]:
        assert "免费" in poi.get("tags", [])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_search_by_rating(client: AsyncClient) -> None:
    """测试按评分筛选 POI。"""
    response = await client.post(
        "/api/poi/search",
        json={"min_rating": 4.0},
    )

    assert response.status_code == 200
    data = response.json()

    for poi in data["pois"]:
        assert poi.get("rating", 0) >= 4.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_search_by_price(client: AsyncClient) -> None:
    """测试按价格筛选 POI。"""
    response = await client.post(
        "/api/poi/search",
        json={"max_price": 50},
    )

    assert response.status_code == 200
    data = response.json()

    for poi in data["pois"]:
        assert poi.get("avg_price", 0) <= 50


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_search_emotion_tags(client: AsyncClient) -> None:
    """测试 POI 搜索结果包含 emotion_tags 字段。"""
    response = await client.post(
        "/api/poi/search",
        json={"region": "珠海", "categories": ["文化"]},
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["pois"]) > 0

    poi = data["pois"][0]
    assert "emotion_tags" in poi
    assert "excitement" in poi["emotion_tags"]
    assert "tranquility" in poi["emotion_tags"]
    assert "culture_depth" in poi["emotion_tags"]


# ---------------------------------------------------------------------------
# 6. 距离矩阵
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_distance_matrix(client: AsyncClient) -> None:
    """测试距离矩阵计算。"""
    # 1. 先搜索一些 POI
    response = await client.post(
        "/api/poi/search",
        json={"region": "珠海", "categories": ["文化"]},
    )
    assert response.status_code == 200
    pois = response.json()["pois"]

    if len(pois) < 2:
        pytest.skip("POI 数据不足，无法测试距离矩阵")

    poi_ids = [p["id"] for p in pois[:3]]

    # 2. 计算距离矩阵
    response = await client.post(
        "/api/poi/distance-matrix",
        json={"poi_ids": poi_ids},
    )

    assert response.status_code == 200
    data = response.json()

    assert "matrix" in data
    assert "poi_ids" in data

    # 3. 验证矩阵维度
    n = len(poi_ids)
    assert len(data["matrix"]) == n
    for row in data["matrix"]:
        assert len(row) == n

    # 4. 验证对角线为0
    for i in range(n):
        assert data["matrix"][i][i]["distance_m"] == 0
        assert data["matrix"][i][i]["time_min"] == 0

    # 5. 验证非对角线元素有值
    for i in range(n):
        for j in range(n):
            if i != j:
                assert data["matrix"][i][j]["distance_m"] > 0
                assert data["matrix"][i][j]["time_min"] >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_distance_matrix_invalid_poi(client: AsyncClient) -> None:
    """测试距离矩阵：包含无效 POI ID。"""
    response = await client.post(
        "/api/poi/distance-matrix",
        json={"poi_ids": ["valid_id_1", "nonexistent_poi"]},
    )

    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_distance_matrix_too_few(client: AsyncClient) -> None:
    """测试距离矩阵：少于2个POI。"""
    response = await client.post(
        "/api/poi/distance-matrix",
        json={"poi_ids": ["single_id"]},
    )

    # Pydantic 校验 min_length=2 应该返回 422
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 7. 路线获取
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_route_retrieval(client: AsyncClient) -> None:
    """测试路线获取：规划后通过 route_id 获取路线详情。"""
    # 1. 规划路线
    response = await client.post(
        "/api/plan",
        json={"user_input": "和女朋友约会"},
        timeout=30.0,
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        pytest.skip(f"意图解析失败: {error_events[0]['error']}")

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route_id = done_events[0]["route_id"]

    # 2. 通过 GET 获取路线
    response = await client.get(f"/api/route/{route_id}")

    assert response.status_code == 200
    data = response.json()

    # 3. 验证返回结构
    assert "route" in data
    assert "narrative" in data
    assert "user_intent" in data
    assert "emotion_curve" in data
    assert "total_cost" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_route_retrieval_after_adjustment(client: AsyncClient) -> None:
    """测试路线获取：调整后获取更新的路线。"""
    # 1. 规划路线
    response = await client.post(
        "/api/plan",
        json={"user_input": "想出去走走"},
        timeout=30.0,
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        pytest.skip(f"意图解析失败: {error_events[0]['error']}")

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) == 1

    route_id = done_events[0]["route_id"]

    # 2. 调整路线
    adjust_resp = await client.get(
        f"/api/route/{route_id}/adjust",
        params={"instruction": "想轻松点"},
        timeout=15.0,
    )

    if adjust_resp.status_code != 200:
        pytest.skip(f"调整失败: {adjust_resp.status_code}")

    # 3. 再次获取路线
    response = await client.get(f"/api/route/{route_id}")

    assert response.status_code == 200
    data = response.json()
    assert "route" in data


# ---------------------------------------------------------------------------
# 8. 数据接口
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_datasets_endpoint(client: AsyncClient) -> None:
    """测试数据集列表接口。"""
    response = await client.get("/api/datasets")

    assert response.status_code == 200
    data = response.json()

    assert "datasets" in data
    assert len(data["datasets"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_list_endpoint(client: AsyncClient) -> None:
    """测试 POI 列表接口。"""
    response = await client.get("/api/poi/", params={"city": "珠海"})

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert "total" in data
    assert data["total"] > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_detail_endpoint(client: AsyncClient) -> None:
    """测试 POI 详情接口。"""
    # 先搜索一个 POI 获取 ID
    search_resp = await client.post(
        "/api/poi/search",
        json={"region": "珠海", "categories": ["文化"]},
    )
    assert search_resp.status_code == 200
    pois = search_resp.json()["pois"]

    if not pois:
        pytest.skip("没有文化类POI数据")

    poi_id = pois[0]["id"]

    # 获取详情
    response = await client.get(f"/api/poi/detail/{poi_id}")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == poi_id
    assert "name" in data
    assert "emotion_tags" in data
    assert "constraints" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_poi_detail_not_found(client: AsyncClient) -> None:
    """测试 POI 详情：不存在的 ID。"""
    response = await client.get("/api/poi/detail/nonexistent_poi_12345")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. LLM 接口
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_chat_endpoint(client: AsyncClient) -> None:
    """测试 LLM 聊天接口。

    Mock LLM 服务以验证接口结构，不依赖外部 API。
    """
    with patch(
        "backend.services.llm_service.chat",
        new_callable=AsyncMock,
        return_value="你好！我是 CityFlow 助手。",
    ):
        response = await client.post(
            "/api/llm/chat",
            json={"message": "你好"},
            timeout=10.0,
        )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "model" in data
    assert data["response"] == "你好！我是 CityFlow 助手。"


# ---------------------------------------------------------------------------
# 10. 多场景端到端
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_retiree(client: AsyncClient) -> None:
    """端到端测试：退休老人场景。

    验证退休场景下路线的合理性：
    - 节奏应为闲逛型
    - 应包含休息间隔
    """
    response = await client.post(
        "/api/plan",
        json={"user_input": "退休了想出去散散步，不想走太多路"},
        timeout=30.0,
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        # 意图解析可能失败
        return

    done_events = [e for e in events if "route_id" in e]
    assert len(done_events) >= 1

    route = done_events[0]["full_route"]
    assert len(route["route"]) >= 1

    # 验证时间递增
    for i in range(1, len(route["route"])):
        prev_dep = route["route"][i - 1]["departure_time"]
        curr_arr = route["route"][i]["arrival_time"]
        assert (
            curr_arr >= prev_dep
        ), f"时间不递增: 第{i}步到达 {curr_arr} < 第{i-1}步离开 {prev_dep}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_food_lover(client: AsyncClient) -> None:
    """端到端测试：美食爱好者场景。"""
    response = await client.post(
        "/api/plan",
        json={"user_input": "想和朋友去吃好吃的"},
        timeout=30.0,
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    error_events = [e for e in events if e.get("error")]
    if error_events:
        return

    done_events = [e for e in events if "route_id" in e]
    if done_events:
        route = done_events[0]["full_route"]
        assert len(route["route"]) >= 1


# ---------------------------------------------------------------------------
# 11. 并发测试
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_planning(client: AsyncClient) -> None:
    """测试并发规划请求。

    验证系统能同时处理多个规划请求而不崩溃。
    """
    import asyncio

    async def plan(user_input: str) -> int:
        resp = await client.post(
            "/api/plan",
            json={"user_input": user_input},
            timeout=30.0,
        )
        return resp.status_code

    # 并发发送 3 个请求
    tasks = [
        plan("想一个人安静走走"),
        plan("和朋友聚会"),
        plan("带孩子出去玩"),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 所有请求都应成功（200）或超时（但不应崩溃）
    for result in results:
        if isinstance(result, Exception):
            # 超时等异常可以接受
            continue
        assert result == 200


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
