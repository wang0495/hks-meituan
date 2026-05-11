"""路线规划 + 对话调整路由。"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.errors import CityFlowException, ErrorCode
from backend.models.schemas import (
    AdjustRequest,
    DialogueResult,
    PlanRequest,
)
from backend.services.cache import route_cache
from backend.services.data_service import get_data

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _with_timeout(coro, timeout_seconds: float = 12.0, fallback=None):
    """给协程加超时，超时返回 fallback。"""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning("操作超时 (%.1fs)，使用兜底", timeout_seconds)
        return fallback


def _generate_simplified_route(
    pois: list[dict[str, Any]], count: int = 3, start_time: str = "09:00"
) -> dict[str, Any]:
    """生成简化路线（兜底方案）。"""
    sorted_pois = sorted(pois, key=lambda p: p.get("rating", 0), reverse=True)[:count]
    try:
        sh, sm = start_time.split(":")
        start_h = int(sh)
        start_m = int(sm)
    except Exception:
        start_h, start_m = 9, 0
    return {
        "route": [
            {
                "poi": poi,
                "arrival_time": f"{(start_h + i) % 24:02d}:{start_m:02d}",
                "departure_time": f"{(start_h + i + 1) % 24:02d}:{start_m:02d}",
                "travel_from_prev": {"distance_m": 0, "time_min": 0},
            }
            for i, poi in enumerate(sorted_pois)
        ],
        "emotion_curve": [],
        "total_cost": {"time_min": 180, "budget_used": 0, "step_estimate": 3000},
        "unused_candidates": [],
        "breathing_spots": [],
    }


def _sse(event: str, data_obj: Any) -> str:
    """构造一条 SSE 消息。"""
    return f"event: {event}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# POST /api/plan -- 流式路线规划
# ---------------------------------------------------------------------------


@router.post(
    "/api/plan",
    summary="流式规划路线",
    description=(
        "根据用户自然语言描述，以SSE（Server-Sent Events）流式返回规划结果。\n\n"
        "## 处理流程\n\n"
        "1. **解析意图** (`phase: parsing`) - 理解用户需求，匹配用户画像\n"
        "2. **搜索候选** (`phase: searching`) - 根据意图筛选合适POI\n"
        "3. **求解路线** (`phase: solving`) - TSPTW算法优化路线顺序与时间\n"
        "4. **生成文案** (`phase: narrating`) - 为每个站点生成描述文案\n"
        "5. **逐步返回** (`step`) - 逐个返回路线步骤\n"
        "6. **完成** (`done`) - 返回路线ID和完整数据\n\n"
        "## SSE 事件类型\n\n"
        "| 事件 | data 字段 | 说明 |\n"
        "|------|-----------|------|\n"
        "| `phase` | `{phase, message}` | 当前处理阶段 |\n"
        "| `step` | `{index, poi, arrival_time, departure_time, narrative}` | 单个路线步骤 |\n"
        "| `done` | `{route_id, full_route}` | 规划完成，route_id 可用于后续对话 |\n"
        "| `error` | `{error}` | 错误信息 |\n\n"
        "## 阶段标识\n\n"
        "| phase 值 | 含义 |\n"
        "|-----------|------|\n"
        "| `parsing` | 正在解析用户意图 |\n"
        "| `searching` | 正在搜索候选POI |\n"
        "| `solving` | 正在求解最优路线 |\n"
        "| `narrating` | 正在生成文案 |\n\n"
        "## 超时与兜底\n\n"
        "- 意图解析超时（8s）→ 返回错误\n"
        "- 候选为空 → 返回错误\n"
        "- 路线求解超时（10s）→ 使用简化路线兜底\n"
        "- 文案生成超时（5s）→ 使用空白文案兜底"
    ),
    response_description="SSE 事件流（text/event-stream），事件格式为 `event: <type>\\ndata: <json>\\n\\n`",
    responses={
        200: {
            "description": "SSE事件流",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "examples": {
                        "phase": {
                            "summary": "阶段事件",
                            "value": 'event: phase\ndata: {"phase":"parsing","message":"正在理解你的需求..."}\n\n',
                        },
                        "step": {
                            "summary": "步骤事件",
                            "value": (
                                'event: step\ndata: {"index":1,"poi":{"id":"poi_001",'
                                '"name":"故宫","category":"景点"},'
                                '"arrival_time":"09:00","departure_time":"11:00",'
                                '"narrative":"走进六百年的紫禁城..."}\n\n'
                            ),
                        },
                        "done": {
                            "summary": "完成事件",
                            "value": 'event: done\ndata: {"route_id":"a1b2c3d4","full_route":{...}}\n\n',
                        },
                        "error": {
                            "summary": "错误事件",
                            "value": 'event: error\ndata: {"error":"意图解析超时，请重试"}\n\n',
                        },
                    },
                }
            },
        }
    },
    tags=["路线规划"],
)
async def plan_route(request: PlanRequest):
    """
    流式规划路线。

    根据用户自然语言输入，经过意图解析、候选搜索、路线求解、文案生成四个阶段，
    以 SSE 事件流的形式逐步返回结果。

    返回的 `route_id` 可用于后续的 `/api/route/{route_id}` 查询和
    `/api/dialogue/{session_id}` 对话调整。
    """

    async def event_stream():
        try:
            # Phase 1: 解析意图
            yield _sse("phase", {"phase": "parsing", "message": "正在理解你的需求..."})

            from backend.services.intent_parser import parse_intent
            from backend.services.user_profiles import USER_PROFILES

            user_intent = await _with_timeout(
                parse_intent(request.user_input, USER_PROFILES),
                timeout_seconds=35.0,
            )
            if user_intent is None:
                yield _sse("error", {"error": "意图解析超时，请重试"})
                return

            # Debug: LLM 调用详情
            llm_used = user_intent.get("_llm_used", False)
            llm_err = user_intent.get("_llm_error", "")
            llm_debug = {
                "used": llm_used,
                "method": "llm" if llm_used else f"rule（{llm_err or '未配置'}）",
            }
            if user_intent.get("_llm_raw_response"):
                llm_debug["raw_response"] = user_intent["_llm_raw_response"][:300]
            if user_intent.get("_llm_model"):
                llm_debug["model"] = user_intent["_llm_model"]
            yield _sse("debug_llm", llm_debug)

            # Debug: 画像匹配 TOP3
            top3 = user_intent.get("_profile_top3", [])
            if top3:
                yield _sse("debug_profile", {
                    "top3": top3,
                    "selected": user_intent.get("matched_profile_id", "?"),
                })

            # V2: PreferenceManager 偏好融合 + 权重计算
            dynamic_weights = None
            demand_vector = user_intent.get("_demand_vector", {})
            pref_manager = None
            if request.user_id:
                yield _sse("phase", {"phase": "identifying", "message": "正在识别用户身份..."})
                from backend.services.preference_manager import PreferenceManager
                from backend.services.holiday_utils import build_context
                from backend.services.perception import PerceptionService

                pref_manager = PreferenceManager.from_user_id(request.user_id)

                # 构建当前上下文
                if request.current_context:
                    current_context = request.current_context
                else:
                    # 自动采集
                    perception = PerceptionService()
                    pctx = await perception.get_context()
                    current_context = build_context(
                        weather=pctx.weather,
                        temperature=pctx.temperature,
                        hour_of_day=pctx.hour_of_day,
                        day_of_week=pctx.day_of_week,
                        season=pctx.season,
                    )

                # 获取用户状态用于调试
                user_status = await pref_manager.get_user_status(current_context)
                yield _sse("debug_preference", {
                    "user_id": request.user_id,
                    "is_new": user_status.get("is_new", True),
                    "interaction_count": user_status.get("interaction_count", 0),
                    "context_info": user_status.get("context_info", ""),
                    "context_hints": user_status.get("context_hints", []),
                    "greeting": user_status.get("greeting", ""),
                })

                # Phase: LTM 预测
                yield _sse("phase", {"phase": "ltm_predict", "message": "正在根据历史预测偏好..."})

                # 用 LTM 预测合并偏好
                prediction = await pref_manager.ltm.predict_preferences(
                    request.user_id, current_context
                )
                if prediction.get("data_points", 0) > 0:
                    from backend.services.intent_parser import merge_user_preference
                    user_intent = merge_user_preference(
                        user_intent,
                        user_stated_prefs=None,
                        ltm_prediction=prediction,
                    )

                yield _sse("debug_ltm", {
                    "data_points": prediction.get("data_points", 0),
                    "confidence": prediction.get("confidence", 0.0),
                    "predicted_pace": prediction.get("predicted_pace"),
                    "predicted_budget": prediction.get("predicted_budget", 0),
                    "predicted_categories": prediction.get("predicted_categories", []),
                    "predicted_emotion_need": prediction.get("predicted_emotion_need"),
                    "context_matched": prediction.get("data_points", 0) > 0,
                })

                # Phase: 权重映射
                yield _sse("phase", {"phase": "weight_mapping", "message": "正在计算求解权重..."})

                # 用 WeightMapper 算动态权重（demand_vector 已在 parse_intent 中提取）
                demand_vector = user_intent.get("_demand_vector", {})
                dynamic_weights = pref_manager.compute_solver_weights(demand_vector)
                yield _sse("debug_weight_mapper", {
                    "demand_vector": demand_vector,
                    "computed_weights": dynamic_weights,
                    "user_deltas": pref_manager.mapper._deltas if pref_manager.mapper else {},
                    "summary": pref_manager.mapper.summary() if pref_manager.mapper else "默认（新用户）",
                    "confidence": {},
                })

            # 在 user_intent 中保存动态权重、需求向量、用户ID和出发位置（供对话阶段使用）
            user_intent["_dynamic_weights"] = dynamic_weights
            user_intent["_demand_vector"] = demand_vector
            if request.user_id:
                user_intent["_user_id"] = request.user_id
            if request.start_location:
                user_intent["start_location"] = request.start_location
            user_intent["_raw_input"] = request.user_input

            # Phase 2: 搜索候选 + 城市过滤
            yield _sse("phase", {"phase": "searching", "message": f"正在为你寻找合适的地方..."})

            # ── Agent Phase: IntentAgent不可能需求检测 ──
            # 在solver之前调用，利用主event loop
            import sys
            sys.stdout.flush()
            print("=" * 50, flush=True)
            print(f"[AGENT_DEBUG] Agent Phase开始, user_input={request.user_input[:30]}", flush=True)
            print("=" * 50, flush=True)
            try:
                from backend.agents import IntentAgent, get_llm as get_agent_llm
                print("[DEBUG] Agent import成功")
                logger.info("[Agent] 开始调用IntentAgent")
                agent = IntentAgent(get_agent_llm())
                intent_agent_result = await agent.analyze(request.user_input)
                logger.info(f"[Agent] 结果: is_impossible={intent_agent_result.get('is_impossible')}")

                # 如果是不可能需求，直接返回
                if intent_agent_result.get("is_impossible"):
                    yield _sse("agent_impossible", {
                        "phase": "Agent检测",
                        "reason": intent_agent_result.get("impossible_reason", ""),
                        "suggestion": intent_agent_result.get("alternative_suggestion", ""),
                    })
                    yield _sse("done", {
                        "route_id": "impossible_" + str(uuid.uuid4())[:8],
                        "full_route": {
                            "route": [],
                            "impossible": True,
                            "impossible_reason": intent_agent_result.get("impossible_reason", ""),
                            "alternative_suggestion": intent_agent_result.get("alternative_suggestion", ""),
                        }
                    })
                    return

                # Agent增强user_intent
                scene_keywords = intent_agent_result.get("scene_keywords", [])
                preferred_zones = intent_agent_result.get("preferred_zones", [])
                if scene_keywords:
                    existing_sr = user_intent.get("scene_requirements", [])
                    user_intent["scene_requirements"] = list(set(existing_sr + scene_keywords))
                    yield _sse("agent_intent", {
                        "phase": "Agent意图增强",
                        "keywords": scene_keywords[:5],
                        "zones": preferred_zones[:3],
                    })
                if preferred_zones:
                    user_intent["_preferred_zones"] = preferred_zones
                user_intent["_intent_agent_result"] = intent_agent_result
            except Exception as e:
                logger.error(f"[Agent] 调用失败: {e}")
                import traceback
                logger.error(traceback.format_exc())

            all_pois = get_data("city_poi_db")

            # 按城市过滤
            target_city = user_intent.get("city", "珠海")
            city_pois = [p for p in all_pois if p.get("city", "").strip() == target_city]
            if not city_pois:
                city_pois = all_pois
                logger.warning(f"城市 {target_city} 无 POI，使用全量数据")
            yield _sse("debug_filter", {
                "before": len(all_pois), "after": len(city_pois),
                "city": target_city,
            })

            # 感知上下文（天气/时间/体力 + 城市特色）
            from backend.services.perception import PerceptionService

            perception = PerceptionService()
            perception_ctx = await perception.get_context(city=target_city)
            yield _sse("debug_perception", {
                "weather": perception_ctx.weather,
                "temperature": perception_ctx.temperature,
                "hour": perception_ctx.hour_of_day,
                "season": perception_ctx.season,
                "fatigue": perception_ctx.fatigue_level,
                "city": perception_ctx.city,
                "city_vibe": perception_ctx.city_vibe,
            })

            # 异常检测
            anomalies = await perception.detect_anomaly(perception_ctx)
            for anom in anomalies:
                yield _sse("anomaly", {
                    "type": anom.type.value, "message": anom.message,
                    "severity": "warning" if anom.severity > 0.5 else "information",
                })

            # 如果检测到异常，生成调整建议
            if anomalies:
                # 先生成一个初步路线（用于调整建议）
                preliminary_plan = {"route": [], "user_intent": user_intent}
                adjustment = await perception.adjust_suggestions(
                    perception_ctx, preliminary_plan, anomalies
                )
                if adjustment.action_type:
                    yield _sse("adjustment_suggestion", {
                        "action_type": adjustment.action_type.value,
                        "target_poi_ids": adjustment.target_poi_ids,
                        "reasoning": adjustment.reasoning,
                        "suggestions": adjustment.suggestions,
                    })

            # Phase 2.5: 矛盾需求检测
            contradiction_warnings = []
            budget = user_intent.get("budget", {})
            time_info = user_intent.get("time", {})
            group = user_intent.get("group", {})
            raw_input = request.user_input

            # 预算 vs 需求矛盾
            if budget.get("per_person", 500) < 100:
                if any(kw in raw_input for kw in ["五星", "豪华", "高端", "酒店", "住"]):
                    contradiction_warnings.append(
                        f"预算仅¥{budget.get('per_person', 0)}，无法满足高端住宿需求，建议调整预算或需求"
                    )
                if any(kw in raw_input for kw in ["长隆", "海洋王国"]):
                    contradiction_warnings.append(
                        "长隆门票约¥300+，当前预算可能不足"
                    )

            # 时间 vs 需求矛盾
            start_str = time_info.get("start", "09:00")
            end_str = time_info.get("end", "22:00")
            try:
                sh, sm = start_str.split(":")
                eh, em = end_str.split(":")
                total_hours = (int(eh) * 60 + int(em) - int(sh) * 60 - int(sm)) / 60
                if total_hours <= 3 and any(kw in raw_input for kw in ["遍", "吃遍", "玩遍", "打卡"]):
                    contradiction_warnings.append(
                        f"仅{total_hours:.0f}小时，可能无法覆盖所有想去的地方，建议减少景点数量"
                    )
            except Exception:
                pass

            # 群体 vs 需求矛盾
            if group.get("type") == "亲子" and any(kw in raw_input for kw in ["蹦迪", "酒吧", "夜店", "喝酒"]):
                contradiction_warnings.append("带孩子去酒吧/夜店可能不适合，建议选择亲子友好的娱乐场所")

            if contradiction_warnings:
                user_intent["_contradiction_warnings"] = contradiction_warnings
                yield _sse("contradiction", {"warnings": contradiction_warnings})

            # Phase 2.6: LLM智能路线策划
            try:
                from backend.services.llm_planner import plan_route as llm_plan_route

                llm_plan = await _with_timeout(
                    llm_plan_route(request.user_input, user_intent, city_pois, perception_ctx),
                    timeout_seconds=10.0,
                )
                if llm_plan:
                    user_intent["_llm_plan"] = llm_plan
                    yield _sse("llm_plan", {
                        "recommended_pois": llm_plan.get("recommended_pois", []),
                        "reasoning": llm_plan.get("reasoning", ""),
                        "warnings": llm_plan.get("warnings", []),
                    })
                    logger.info("LLM Planner: %d POIs recommended", len(llm_plan.get("recommended_pois", [])))
                else:
                    logger.info("LLM Planner: no plan returned")
            except Exception as e:
                logger.warning("LLM Planner error: %s", e)

            # Phase 3: 求解路线
            yield _sse("phase", {"phase": "solving", "message": "正在编排最佳路线..."})

            from backend.services.solver import solve_route

            start_time = user_intent.get("time", {}).get("start")
            if not start_time:
                # 深夜场景默认22:00，其他默认09:00
                if "late_night" in user_intent.get("hard_constraints", []):
                    start_time = "22:00"
                else:
                    start_time = "09:00"
            # 收集求解器阶段事件（通过线程安全列表在线程中收集）
            solver_events: list[dict] = []
            def _on_solver_progress(stage: str, data: dict) -> None:
                solver_events.append({"stage": stage, **data})

            route_result = await _with_timeout(
                asyncio.to_thread(
                    solve_route, city_pois, user_intent, start_time, perception_ctx,
                    dynamic_weights,
                    progress_callback=_on_solver_progress,
                ),
                timeout_seconds=15.0,
            )

            # 发射求解器阶段事件
            for evt in solver_events:
                yield _sse("solver_stage", evt)

            
            # 兜底：求解失败或超时
            if route_result is None or not route_result.get("route"):
                logger.warning("路线求解失败/超时，使用简化路线")
                route_result = _generate_simplified_route(all_pois, start_time=start_time)

            # Debug: 求解器阶段 + 路线审核
            solver_route = route_result.get("route", [])
            audit_issues = route_result.get("audit_issues", [])
            yield _sse("debug_solver", {
                "total_candidates": len(all_pois),
                "selected_count": len(solver_route),
                "unused_count": len(route_result.get("unused_candidates", [])),
                "total_time_min": route_result.get("total_cost", {}).get("time_min", 0),
                "total_budget": route_result.get("total_cost", {}).get("budget_used", 0),
                "stages": [
                    {"name": "TW-NN贪心初始化", "status": "done", "result": f"初始路线 {len(solver_route)} 站"},
                    {"name": "2-opt局部优化", "status": "done", "result": f"优化完成"},
                    {"name": "呼吸空间插入", "status": "done", "result": f"插入 {len(route_result.get('breathing_spots', []))} 个休息点"},
                    {"name": "高潮收尾", "status": "done", "result": f"末站: {solver_route[-1]['poi']['name'] if solver_route else '-'}"},
                ],
                "audit_issues": audit_issues,
                "start_location": route_result.get("start_location", "未指定"),
            })

            # Debug: POI 筛选详情
            excluded = route_result.get("unused_candidates", [])
            yield _sse("debug_filter", {
                "before": len(all_pois),
                "after": len(solver_route) + len(excluded),
                "selected": len(solver_route),
                "top_excluded": [
                    {"name": p.get("name", "?"), "category": p.get("category", "?"),
                     "price": p.get("avg_price", 0), "rating": p.get("rating", 0)}
                    for p in excluded[:5]
                ],
            })

            # 路线求解后：基于情绪曲线的异常检测
            emotion_curve = route_result.get("emotion_curve", [])
            if emotion_curve:
                post_anomalies = await perception.detect_anomaly(
                    perception_ctx, emotion_curve
                )
                for anom in post_anomalies:
                    # 只推送新发现的异常（避免重复）
                    if anom.type.value not in [a.type.value for a in anomalies]:
                        yield _sse("anomaly", {
                            "type": anom.type.value,
                            "message": anom.message,
                            "severity": "warning" if anom.severity > 0.5 else "information",
                        })
                        anomalies.append(anom)

                # 如果有新异常，生成调整建议
                if post_anomalies:
                    adjustment = await perception.adjust_suggestions(
                        perception_ctx, route_result, post_anomalies
                    )
                    if adjustment.action_type:
                        yield _sse("adjustment_suggestion", {
                            "action_type": adjustment.action_type.value,
                            "target_poi_ids": adjustment.target_poi_ids,
                            "reasoning": adjustment.reasoning,
                            "suggestions": adjustment.suggestions,
                        })

            # Phase 4: 生成文案
            yield _sse(
                "phase", {"phase": "narrating", "message": "正在为你写一段行程说明..."}
            )

            from backend.services.narrator import generate_narrative

            city = user_intent.get("city", "")

            narrative = await _with_timeout(
                generate_narrative(route_result, user_intent, city=city),
                timeout_seconds=30.0,
                fallback={
                    "opening": "",
                    "steps": [],
                    "closing": "",
                    "emotion_highlights": [],
                    "budget_breakdown": {},
                },
            )

            # 逐步返回每个 POI（包含情绪设计和设计意图）
            steps_list = route_result.get("route", [])
            narrative_steps = narrative.get("steps", [])
            for i, step in enumerate(steps_list):
                ns = narrative_steps[i] if i < len(narrative_steps) else {}
                step_data = {
                    "index": i + 1,
                    "poi": step["poi"],
                    "arrival_time": step.get("arrival_time"),
                    "departure_time": step.get("departure_time"),
                    "narrative": ns.get("description", "") if isinstance(ns, dict) else str(ns),
                    "emotion_design": ns.get("emotion_design", "") if isinstance(ns, dict) else "",
                    "design_intent": ns.get("design_intent", "") if isinstance(ns, dict) else "",
                    "leverage": ns.get("leverage", "中") if isinstance(ns, dict) else "中",
                    "cost": ns.get("cost", 0) if isinstance(ns, dict) else 0,
                    "scene_tags": step["poi"].get("_scene_tags", []),
                }
                yield _sse("step", step_data)
                # 发送 step_update 事件（含叙事详情）
                yield _sse("step_update", {"index": i + 1, "description": step_data["narrative"]})
                await asyncio.sleep(0.05)

            # 文案生成完成
            yield _sse("polish_done", {"message": "路线描述已生成"})

            # 生成路由 ID 并缓存
            route_id = uuid.uuid4().hex[:8]
            route_result["narrative"] = narrative
            route_result["user_intent"] = user_intent
            route_cache.set(route_id, route_result)

            # 创建对话会话（用于后续调整）
            try:
                from backend.services.dialogue import dialogue_engine
                await dialogue_engine.create_session(route_id, route_result, user_intent)
            except Exception as de_err:
                logger.warning(f"创建对话会话失败（不影响主流程）: {de_err}")

            # 发送预算汇总事件（含额外开销估算）
            budget = narrative.get("budget_breakdown", {})
            if budget:
                # 估算额外开销：餐饮/饮品/文创
                steps_list = route_result.get("route", [])
                meal_count = sum(1 for s in steps_list if s.get("poi", {}).get("category") == "餐饮")
                extra_costs = {
                    "meals": meal_count * 50,       # 每餐预估 ¥50
                    "drinks": len(steps_list) * 8,   # 每站饮品 ¥8
                    "souvenirs": len(steps_list) * 15,  # 每站文创 ¥15
                    "total_extra": meal_count * 50 + len(steps_list) * 23,
                }
                budget["extra_costs"] = extra_costs
                yield _sse("budget", budget)

            # 记忆系统：保存行程到工作记忆
            try:
                from backend.services.memory import MemoryOrchestrator

                memory = MemoryOrchestrator()
                wm = await memory.get_working(route_id)
                await wm.set(route_id, "user_input", request.user_input)
                await wm.set(route_id, "user_intent", json.dumps(user_intent, ensure_ascii=False))
                await wm.set(route_id, "target_city", target_city)
                await wm.set(route_id, "poi_count", len(steps_list))
                await wm.set(route_id, "weather", perception_ctx.weather)
            except Exception as mem_err:
                logger.warning(f"记忆系统写入失败（不影响主流程）: {mem_err}")

            # V2: 通过 PreferenceManager 保存行程到 LTM
            if pref_manager:
                yield _sse("phase", {"phase": "saving", "message": "正在保存偏好记忆..."})
                try:
                    from backend.services.holiday_utils import build_context

                    # 构建上下文
                    context = build_context(
                        weather=perception_ctx.weather,
                        temperature=perception_ctx.temperature,
                        hour_of_day=perception_ctx.hour_of_day,
                        day_of_week=perception_ctx.day_of_week,
                        season=perception_ctx.season,
                        source="user_initiated",
                    )
                    await pref_manager.save_trip_to_memory(
                        route_result, user_intent, context
                    )
                    trip_history = user_status.get("interaction_count", 0) + 1
                    yield _sse("memory_saved", {
                        "message": f"已记住{pref_manager.user_id}的偏好，下次会更懂你！",
                        "trip_count": trip_history,
                        "route_summary": route_result.get("route", [])[:1],
                        "user_id": pref_manager.user_id,
                    })
                    yield _sse("debug_ltm", {
                        "action": "saved",
                        "user_id": pref_manager.user_id,
                        "trip_count": trip_history,
                        "categories": list(dict.fromkeys(
                            s.get("poi", {}).get("category", "") for s in route_result.get("route", [])
                        )),
                        "mapper_deltas": pref_manager.mapper.summary() if pref_manager.mapper else "未调整",
                    })
                except Exception as mem_err2:
                    logger.warning(f"LTM 写入失败（不影响主流程）: {mem_err2}")

            # 完成
            yield _sse(
                "done",
                {"route_id": route_id, "full_route": route_result},
            )

        except Exception:
            logger.exception("规划路线时出错")
            # 不向客户端暴露内部错误详情
            yield _sse("error", {"error": "服务器内部错误，请稍后重试"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /api/route/{route_id} -- 获取路线详情
# ---------------------------------------------------------------------------


@router.get(
    "/api/route/{route_id}",
    summary="获取路线详情",
    description=(
        "根据路线ID获取已规划路线的完整数据。\n\n"
        "路线数据由 `/api/plan` 接口生成并缓存，`route_id` 在规划完成时返回。\n\n"
        "返回内容包括：路线步骤、情绪曲线、费用估算、未使用候选、文案等。"
    ),
    response_description="完整路线数据",
    responses={
        200: {
            "description": "路线详情",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/RouteResult"},
                }
            },
        },
        404: {
            "description": "路线不存在",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {"detail": "Route not found"},
                }
            },
        },
    },
    tags=["路线管理"],
)
async def get_route(route_id: str):
    """
    获取已规划路线的完整数据。

    路线数据保存在内存缓存中，服务重启后失效。
    """
    route_data = route_cache.get(route_id)
    if route_data is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Route not found",
            details={"route_id": route_id},
        )
    return route_data


# ---------------------------------------------------------------------------
# GET /api/route/{route_id}/adjust -- 调整路线（query param）
# ---------------------------------------------------------------------------


@router.get(
    "/api/route/{route_id}/adjust",
    summary="通过指令调整路线（快捷方式）",
    description=(
        "通过GET请求的query参数传入指令来调整已规划的路线。\n\n"
        "这是 `/api/dialogue/{session_id}` 的快捷方式，session_id 即 route_id。\n\n"
        "## 支持的指令\n\n"
        "| 类型 | 示例 |\n"
        "|------|------|\n"
        '| 替换景点 | "换掉故宫"、"不要第二个" |\n'
        '| 调整节奏 | "太赶了"、"轻松一点" |\n'
        '| 调整预算 | "太贵了"、"便宜点" |\n'
        '| 调整时间 | "早一点"、"5点前结束" |\n'
        '| 重新规划 | "重新来"、"再来一次" |'
    ),
    response_description="调整结果，包含系统回复、更新后的路线和变更记录",
    responses={
        200: {
            "description": "调整成功",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/DialogueResult"},
                }
            },
        },
        400: {
            "description": "指令无法识别或对话轮次超限",
        },
        404: {
            "description": "路线不存在",
        },
    },
    tags=["对话"],
)
async def adjust_route(route_id: str, instruction: str):
    """
    通过对话指令调整路线（GET快捷方式）。

    自动创建对话会话（如果不存在），然后处理用户的调整指令。
    """
    route = route_cache.get(route_id)
    if route is None:
        raise CityFlowException(
            code=ErrorCode.NOT_FOUND,
            message="Route not found",
            details={"route_id": route_id},
        )
    user_intent = route.get("user_intent", {})

    from backend.services.dialogue import dialogue_engine

    # 确保有会话
    session = await dialogue_engine.get_session(route_id)
    if not session:
        session = await dialogue_engine.create_session(route_id, route, user_intent)

    result = await dialogue_engine.process_instruction(route_id, instruction)

    # 更新缓存
    if "route" in result:
        route_cache.set(route_id, result["route"])

    # 记录反馈到 LTM
    if result.get("changes_made") and user_intent.get("_user_id"):
        try:
            from backend.services.preference_manager import PreferenceManager
            pref_mgr = PreferenceManager.from_user_id(user_intent["_user_id"])
            await pref_mgr._ensure_init()
            await pref_mgr.record_feedback(
                demand_vector=user_intent.get("_demand_vector", {}),
                applied_weights=user_intent.get("_dynamic_weights", {}),
                feedback="modified",
                modification_hint=instruction,
            )
        except Exception as fb_err:
            logger.warning(f"反馈记录失败（不影响主流程）: {fb_err}")

    return result


# ---------------------------------------------------------------------------
# POST /api/dialogue/{session_id} -- 对话接口
# ---------------------------------------------------------------------------


@router.post(
    "/api/dialogue/{session_id}",
    summary="对话式路线调整",
    description=(
        "通过多轮对话对已规划路线进行调整。\n\n"
        "`session_id` 通常为 `/api/plan` 返回的 `route_id`。\n\n"
        "## 指令分类\n\n"
        "系统基于关键词自动分类用户指令：\n\n"
        "### 替换指令\n"
        "触发词：换、替换、不喜欢、不要、去掉\n\n"
        '- "换掉第二个景点" → 按序号替换\n'
        '- "不喜欢故宫" → 按名称替换\n'
        "- 替换时自动选择同类目、情绪标签最相似的候选项\n\n"
        "### 节奏调整\n"
        "触发词：赶、累、轻松、慢、快、紧凑\n\n"
        '- "太赶了" / "想轻松点" → 切换为闲逛型\n'
        '- "太慢了" / "紧凑一些" → 切换为特种兵型\n'
        "- 调整后自动重新求解路线\n\n"
        "### 预算调整\n"
        "触发词：贵、便宜、省钱、预算\n\n"
        '- "太贵了" / "便宜点" → 预算降低20%\n'
        '- "可以多花点" → 预算提高30%\n'
        "- 调整后重新筛选候选并求解\n\n"
        "### 时间调整\n"
        "触发词：早、晚、时间、点之前\n\n"
        '- "早上8点出发" → 设置出发时间\n'
        '- "5点前结束" → 设置结束时间\n'
        '- "早一点" → 出发时间提前1小时\n\n'
        "### 重新规划\n"
        "触发词：不行、重新、再来\n\n"
        "- 使用当前意图重新求解路线\n\n"
        "## 对话限制\n\n"
        "- 每个会话最多 **10轮** 对话\n"
        "- 超过后需重新调用 `/api/plan` 开始新规划"
    ),
    response_description="调整结果",
    responses={
        200: {
            "description": "调整成功",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/DialogueResult"},
                    "examples": {
                        "replace": {
                            "summary": "替换景点",
                            "value": {
                                "reply": "好的，我已经把'故宫'换成了'颐和园'。",
                                "route": {"route": [], "emotion_curve": []},
                                "changes_made": [
                                    {
                                        "type": "replace",
                                        "original": "故宫",
                                        "replacement": "颐和园",
                                    }
                                ],
                            },
                        },
                        "pace": {
                            "summary": "调整节奏",
                            "value": {
                                "reply": "好的，我帮你调整为轻松型行程，增加休息时间。",
                                "route": {"route": [], "emotion_curve": []},
                                "changes_made": [
                                    {"type": "pace", "new_pace": "闲逛型"}
                                ],
                            },
                        },
                    },
                }
            },
        },
        400: {
            "description": "指令无法识别或对话轮次超限",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "examples": {
                        "unknown": {
                            "summary": "无法识别的指令",
                            "value": {
                                "detail": "抱歉，我没有理解你的意思。你可以试试：\n"
                                "- 换掉某个景点\n- 调整节奏\n- 调整预算\n- 调整时间\n- 重新规划"
                            },
                        },
                        "expired": {
                            "summary": "对话轮次超限",
                            "value": {"detail": "对话轮次已达上限，请重新开始"},
                        },
                    },
                }
            },
        },
        404: {
            "description": "会话不存在",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    "example": {"detail": "会话不存在"},
                }
            },
        },
    },
    tags=["对话"],
)
async def dialogue(session_id: str, request: AdjustRequest):
    """
    对话式路线调整。

    通过POST请求发送调整指令，系统自动分类指令类型并执行相应调整。
    """
    from backend.services.dialogue import dialogue_engine

    result = await dialogue_engine.process_instruction(session_id, request.instruction)

    # 同步更新路线缓存
    if "route" in result:
        route_cache.set(session_id, result["route"])

    # 记录反馈到 LTM
    if result.get("changes_made"):
        try:
            session = await dialogue_engine.get_session(session_id)
            if session and session.user_intent.get("_user_id"):
                from backend.services.preference_manager import PreferenceManager
                pref_mgr = PreferenceManager.from_user_id(session.user_intent["_user_id"])
                await pref_mgr._ensure_init()
                await pref_mgr.record_feedback(
                    demand_vector=session.user_intent.get("_demand_vector", {}),
                    applied_weights=session.user_intent.get("_dynamic_weights", {}),
                    feedback="modified",
                    modification_hint=request.instruction,
                )
        except Exception as fb_err:
            logger.warning(f"反馈记录失败（不影响主流程）: {fb_err}")

    return result
