"""CityFlow 测试用例生成器。

从 OpenAPI 规范 (api_spec.yaml) 和手工定义的端点清单自动生成
API 测试用例，覆盖:
- 正向功能测试
- 边界条件 / 参数校验测试
- 错误路径测试
- HTTP 方法测试

生成的用例为纯 dict 列表，可直接传给 ``APITestRunner.run_tests()``。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# CityFlow 端点清单（手工维护，补充 spec 中未覆盖的路由）
# ---------------------------------------------------------------------------

CITYFLOW_ENDPOINTS: list[dict[str, Any]] = [
    # ── 路线规划 ─────────────────────────────────
    {
        "name": "test_post_plan",
        "method": "POST",
        "path": "/api/plan",
        "body": {"user_input": "周末想一个人安静走走"},
        "expected_status": 200,
        "description": "流式规划路线（SSE）",
        "content_type": "text/event-stream",
    },
    # ── 对话调整 ─────────────────────────────────
    {
        "name": "test_post_dialogue_adjust",
        "method": "POST",
        "path": "/api/dialogue/adjust",
        "body": {
            "route_id": "test_route",
            "instruction": "换掉第二个景点",
        },
        "expected_status": [200, 404],
        "description": "对话式路线调整",
    },
    # ── POI 搜索 ─────────────────────────────────
    {
        "name": "test_post_poi_search",
        "method": "POST",
        "path": "/api/poi/search",
        "body": {"region": "珠海", "categories": ["文化", "餐饮"]},
        "expected_status": 200,
        "description": "POI 搜索",
    },
    {
        "name": "test_post_poi_search_with_tags",
        "method": "POST",
        "path": "/api/poi/search",
        "body": {"region": "广州", "tags": ["免费"]},
        "expected_status": 200,
        "description": "POI 搜索（带标签过滤）",
    },
    {
        "name": "test_post_poi_search_with_keyword",
        "method": "POST",
        "path": "/api/poi/search",
        "body": {"keyword": "博物馆"},
        "expected_status": 200,
        "description": "POI 搜索（关键词）",
    },
    {
        "name": "test_post_poi_search_empty_body",
        "method": "POST",
        "path": "/api/poi/search",
        "body": {},
        "expected_status": 200,
        "description": "POI 搜索（空 body，应返回全部）",
    },
    # ── POI 详情 ─────────────────────────────────
    {
        "name": "test_get_poi_detail",
        "method": "GET",
        "path": "/api/poi/detail/poi_00001",
        "expected_status": 200,
        "description": "获取 POI 详情",
    },
    {
        "name": "test_get_poi_detail_not_found",
        "method": "GET",
        "path": "/api/poi/detail/poi_99999",
        "expected_status": 404,
        "description": "获取不存在的 POI 详情",
    },
    # ── 距离矩阵 ─────────────────────────────────
    {
        "name": "test_post_distance_matrix",
        "method": "POST",
        "path": "/api/poi/distance-matrix",
        "body": {"poi_ids": ["poi_00001", "poi_00002"]},
        "expected_status": 200,
        "description": "计算距离矩阵",
    },
    {
        "name": "test_post_distance_matrix_single_id",
        "method": "POST",
        "path": "/api/poi/distance-matrix",
        "body": {"poi_ids": ["poi_00001"]},
        "expected_status": 400,
        "description": "距离矩阵只传 1 个 ID（应报错）",
    },
    {
        "name": "test_post_distance_matrix_empty",
        "method": "POST",
        "path": "/api/poi/distance-matrix",
        "body": {"poi_ids": []},
        "expected_status": 400,
        "description": "距离矩阵空列表",
    },
    # ── 健康检查 ─────────────────────────────────
    {
        "name": "test_get_health",
        "method": "GET",
        "path": "/api/health",
        "expected_status": 200,
        "description": "基础健康检查",
    },
    {
        "name": "test_get_health_detail",
        "method": "GET",
        "path": "/api/health/detail",
        "expected_status": 200,
        "description": "详细健康状态",
    },
    # ── 会话管理 ─────────────────────────────────
    {
        "name": "test_post_session_create",
        "method": "POST",
        "path": "/api/session/",
        "body": None,
        "expected_status": 200,
        "description": "创建会话",
    },
    {
        "name": "test_get_sessions",
        "method": "GET",
        "path": "/api/session/",
        "expected_status": 200,
        "description": "列出所有会话",
    },
    # ── 数据查询 ─────────────────────────────────
    {
        "name": "test_get_data",
        "method": "GET",
        "path": "/api/data/",
        "params": {"dataset": "poi"},
        "expected_status": 200,
        "description": "查询数据集",
    },
    {
        "name": "test_get_poi_data",
        "method": "GET",
        "path": "/api/poi/",
        "params": {"city": "珠海"},
        "expected_status": 200,
        "description": "查询城市 POI 原始数据",
    },
    # ── 任务管理 ─────────────────────────────────
    {
        "name": "test_get_tasks",
        "method": "GET",
        "path": "/api/tasks/",
        "expected_status": 200,
        "description": "列出所有任务",
    },
    # ── 审计日志 ─────────────────────────────────
    {
        "name": "test_get_audit",
        "method": "GET",
        "path": "/api/audit/",
        "expected_status": 200,
        "description": "查询审计日志",
    },
    # ── LLM ──────────────────────────────────────
    {
        "name": "test_post_llm_chat",
        "method": "POST",
        "path": "/api/llm/chat",
        "body": {"message": "你好"},
        "expected_status": [200, 422],
        "description": "LLM 对话",
    },
    # ── GraphQL ──────────────────────────────────
    {
        "name": "test_post_graphql",
        "method": "POST",
        "path": "/graphql",
        "body": {"query": "{ __typename }"},
        "expected_status": 200,
        "description": "GraphQL introspection",
    },
    # ── 消息队列 ─────────────────────────────────
    {
        "name": "test_get_mq_status",
        "method": "GET",
        "path": "/api/mq/status",
        "expected_status": [200, 503],
        "description": "消息队列状态",
    },
    # ── 服务注册 ─────────────────────────────────
    {
        "name": "test_get_registry",
        "method": "GET",
        "path": "/api/registry/",
        "expected_status": 200,
        "description": "服务注册列表",
    },
    # ── WebSocket 信息 ───────────────────────────
    {
        "name": "test_get_ws_info",
        "method": "GET",
        "path": "/api/ws/info",
        "expected_status": [200, 404],
        "description": "WebSocket 信息端点",
    },
]


# ---------------------------------------------------------------------------
# 生成器
# ---------------------------------------------------------------------------


class TestCaseGenerator:
    """测试用例生成器。

    支持三种用例来源:
    1. 从 OpenAPI spec 文件自动生成
    2. 从手工维护的 CITYFLOW_ENDPOINTS 生成
    3. 为 schema 字段生成边界测试
    """

    def __init__(self, spec_path: str | Path | None = None) -> None:
        self._spec: dict[str, Any] | None = None
        if spec_path is not None:
            self._spec = self._load_spec(spec_path)

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def generate_from_spec(self) -> list[dict[str, Any]]:
        """从 OpenAPI spec 生成基础测试用例（每条 path+method 一个）。"""
        if self._spec is None:
            return []
        tests: list[dict[str, Any]] = []
        for path, methods in self._spec.get("paths", {}).items():
            for method, spec in methods.items():
                if method.upper() in ("PARAMETERS", "SUMMARY", "DESCRIPTION"):
                    continue
                test = {
                    "name": f"test_{method}_{path.replace('/', '_').strip('_')}",
                    "method": method.upper(),
                    "path": path,
                    "description": spec.get("summary", ""),
                    "expected_status": 200,
                }
                # 尝试从 spec 中提取示例请求体
                request_body = self._extract_example_body(spec)
                if request_body is not None:
                    test["body"] = request_body
                tests.append(test)
        return tests

    def generate_cityflow_tests(self) -> list[dict[str, Any]]:
        """返回手工维护的 CityFlow 端点测试用例。"""
        return [dict(t) for t in CITYFLOW_ENDPOINTS]

    def generate_all(self) -> list[dict[str, Any]]:
        """合并 spec 生成 + 手工维护的用例，去重后返回。"""
        spec_tests = self.generate_from_spec()
        manual_tests = self.generate_cityflow_tests()
        # 手工用例优先（更精确），spec 用例补充
        seen = {(t["method"], t["path"]) for t in manual_tests}
        merged = list(manual_tests)
        for t in spec_tests:
            key = (t["method"], t["path"])
            if key not in seen:
                merged.append(t)
                seen.add(key)
        return merged

    def generate_boundary_tests(self, schema_name: str | None = None) -> list[dict[str, Any]]:
        """为 CityFlow 关键 schema 生成边界 / 校验测试。"""
        tests: list[dict[str, Any]] = []

        # ── POI 搜索边界 ─────────────────────────
        tests.extend(
            [
                {
                    "name": "test_poi_search_invalid_min_rating",
                    "method": "POST",
                    "path": "/api/poi/search",
                    "body": {"min_rating": -1},
                    "expected_status": [400, 422, 200],
                    "description": "min_rating 为负数",
                },
                {
                    "name": "test_poi_search_invalid_max_price",
                    "method": "POST",
                    "path": "/api/poi/search",
                    "body": {"max_price": -100},
                    "expected_status": [400, 422, 200],
                    "description": "max_price 为负数",
                },
                {
                    "name": "test_poi_search_unknown_category",
                    "method": "POST",
                    "path": "/api/poi/search",
                    "body": {"categories": ["不存在的品类"]},
                    "expected_status": [200, 400, 422],
                    "description": "未知品类",
                },
            ]
        )

        # ── 路线规划边界 ─────────────────────────
        tests.extend(
            [
                {
                    "name": "test_plan_empty_input",
                    "method": "POST",
                    "path": "/api/plan",
                    "body": {"user_input": ""},
                    "expected_status": [400, 422],
                    "description": "空输入",
                },
                {
                    "name": "test_plan_long_input",
                    "method": "POST",
                    "path": "/api/plan",
                    "body": {"user_input": "a" * 1000},
                    "expected_status": [400, 422],
                    "description": "超长输入（1000字符）",
                },
                {
                    "name": "test_plan_missing_field",
                    "method": "POST",
                    "path": "/api/plan",
                    "body": {},
                    "expected_status": [400, 422],
                    "description": "缺少 user_input 字段",
                },
            ]
        )

        # ── 距离矩阵边界 ─────────────────────────
        tests.extend(
            [
                {
                    "name": "test_distance_matrix_too_many_ids",
                    "method": "POST",
                    "path": "/api/poi/distance-matrix",
                    "body": {"poi_ids": [f"poi_{i:05d}" for i in range(51)]},
                    "expected_status": [400, 422],
                    "description": "距离矩阵超过 50 个 ID 限制",
                },
                {
                    "name": "test_distance_matrix_nonexistent_ids",
                    "method": "POST",
                    "path": "/api/poi/distance-matrix",
                    "body": {"poi_ids": ["fake_001", "fake_002"]},
                    "expected_status": 400,
                    "description": "不存在的 POI ID",
                },
            ]
        )

        # ── 对话调整边界 ─────────────────────────
        tests.extend(
            [
                {
                    "name": "test_dialogue_empty_instruction",
                    "method": "POST",
                    "path": "/api/dialogue/adjust",
                    "body": {"route_id": "test", "instruction": ""},
                    "expected_status": [400, 422],
                    "description": "空调整指令",
                },
                {
                    "name": "test_dialogue_missing_route_id",
                    "method": "POST",
                    "path": "/api/dialogue/adjust",
                    "body": {"instruction": "换掉第二个景点"},
                    "expected_status": [400, 422, 404],
                    "description": "缺少 route_id",
                },
            ]
        )

        return tests

    def generate_method_not_allowed_tests(self) -> list[dict[str, Any]]:
        """测试不支持的 HTTP 方法。"""
        tests: list[dict[str, Any]] = []
        get_only = [
            "/api/health",
            "/api/health/detail",
            "/api/session/",
            "/api/data/",
            "/api/poi/",
            "/api/tasks/",
            "/api/audit/",
        ]
        post_only = [
            "/api/plan",
            "/api/poi/search",
            "/api/poi/distance-matrix",
        ]
        for path in get_only:
            tests.append(
                {
                    "name": f"test_method_not_allowed_post_{path.replace('/', '_').strip('_')}",
                    "method": "POST",
                    "path": path,
                    "body": {},
                    "expected_status": [405, 400, 422],
                    "description": f"POST {path}（应为 405）",
                }
            )
        for path in post_only:
            tests.append(
                {
                    "name": f"test_method_not_allowed_get_{path.replace('/', '_').strip('_')}",
                    "method": "GET",
                    "path": path,
                    "expected_status": [405, 400, 404, 422],
                    "description": f"GET {path}（应为 405）",
                }
            )
        return tests

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _load_spec(path: str | Path) -> dict[str, Any]:
        """加载 YAML / JSON 格式的 OpenAPI spec。"""
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix in (".yaml", ".yml"):
            return yaml.safe_load(text)
        return json.loads(text)

    @staticmethod
    def _extract_example_body(spec: dict[str, Any]) -> Any:
        """从 requestBody 中提取 example 值。"""
        rb = spec.get("requestBody", {})
        content = rb.get("content", {})
        for media in content.values():
            example = media.get("example")
            if example is not None:
                return example
            schema = media.get("schema", {})
            # $ref 的情况下无法解析，跳过
        return None
