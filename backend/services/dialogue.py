"""CityFlow 多轮对话引擎。

支持用户对已规划路线进行调整，包括：
- 替换指令：换掉某个景点
- 节奏调整：太赶了/想轻松点
- 预算调整：太贵了/便宜一点
- 时间调整：早一点/晚一点
- 不满反馈：重新来/再想一个

v2 新增：
- 对话状态 Redis 持久化（P0-2）
- 序列化/反序列化 to_dict/from_dict
- Redis 不可用时自动回退到内存模式
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

from backend.errors import DialogueError
from backend.services.solver import _BETA, _GAMMA  # V2: 权重基线常量
from backend.services.time_utils import format_time, parse_time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 对话状态
# ---------------------------------------------------------------------------


class DialogueState:
    """单个对话会话的状态管理。"""

    def __init__(
        self,
        session_id: str,
        initial_route: dict[str, Any],
        user_intent: dict[str, Any],
    ) -> None:
        self.session_id = session_id
        self.route = initial_route
        self.user_intent = user_intent
        self.history: list[dict[str, str]] = []
        self.pending_changes: list[dict[str, Any]] = []
        self.turn_count = 0
        self.max_turns = 10
        self.created_at: str = datetime.now().isoformat()
        self.last_active: str = self.created_at

    def add_message(self, role: str, content: str) -> None:
        """添加消息到对话历史。"""
        self.history.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def is_expired(self) -> bool:
        """对话轮次是否已达上限。"""
        return self.turn_count >= self.max_turns

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 Redis 存储）。"""
        return {
            "session_id": self.session_id,
            "route": self.route,
            "user_intent": self.user_intent,
            "history": self.history,
            "pending_changes": self.pending_changes,
            "turn_count": self.turn_count,
            "max_turns": self.max_turns,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DialogueState:
        """从 dict 重建对话状态。"""
        state = cls(
            session_id=data["session_id"],
            initial_route=data["route"],
            user_intent=data["user_intent"],
        )
        state.history = data.get("history", [])
        state.pending_changes = data.get("pending_changes", [])
        state.turn_count = data.get("turn_count", 0)
        state.max_turns = data.get("max_turns", 10)
        state.created_at = data.get("created_at", "")
        state.last_active = data.get("last_active", "")
        return state


# ---------------------------------------------------------------------------
# Redis 持久化后端
# ---------------------------------------------------------------------------

DIALOGUE_REDIS_KEY_PREFIX = "dialogue:"
DIALOGUE_REDIS_TTL = 3600  # 1 小时


class DialoguePersistence:
    """对话状态持久化后端（Redis）。

    在 Redis 可用时保存/恢复 DialogueState；
    不可用时置 fallback=True，继续内存操作。
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None  # redis.asyncio.Redis | None
        self._connected = False
        self._fallback = False

    async def _get_redis(self) -> Any:
        """获取 Redis 连接（延迟连接）。"""
        if self._connected and self._redis is not None:
            return self._redis
        if self._fallback or not self._redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            await self._redis.ping()
            self._connected = True
            self._fallback = False
            logger.info("[DialoguePersistence] Redis 连接成功")
            return self._redis
        except Exception:
            self._connected = False
            self._fallback = True
            logger.warning("[DialoguePersistence] Redis 不可达，切换到内存模式")
            return None

    async def save(self, session_id: str, state: DialogueState) -> bool:
        """保存对话状态到 Redis。失败时记录警告并设置 fallback。"""
        r = await self._get_redis()
        if r is None:
            return False
        try:
            key = f"{DIALOGUE_REDIS_KEY_PREFIX}{session_id}"
            state.last_active = datetime.now().isoformat()
            await r.setex(key, DIALOGUE_REDIS_TTL, json.dumps(state.to_dict(), ensure_ascii=False))
            return True
        except Exception:
            self._fallback = True
            logger.warning("[DialoguePersistence] Redis save 失败，切换到内存模式")
            return False

    async def load(self, session_id: str) -> dict[str, Any] | None:
        """从 Redis 加载对话状态。"""
        r = await self._get_redis()
        if r is None:
            return None
        try:
            key = f"{DIALOGUE_REDIS_KEY_PREFIX}{session_id}"
            data = await r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            self._fallback = True
            logger.warning("[DialoguePersistence] Redis load 失败，切换到内存模式")
            return None

    async def delete(self, session_id: str) -> bool:
        """从 Redis 删除对话状态。"""
        r = await self._get_redis()
        if r is None:
            return False
        try:
            key = f"{DIALOGUE_REDIS_KEY_PREFIX}{session_id}"
            await r.delete(key)
            return True
        except Exception as e:
            logger.warning("dialogue error: %s", e)
            return False

    @property
    def is_fallback(self) -> bool:
        return self._fallback


# ---------------------------------------------------------------------------
# 对话引擎
# ---------------------------------------------------------------------------


class DialogueEngine:
    """对话引擎：管理会话生命周期，分发指令到对应处理器。

    Args:
        persistence: 可选持久化后端。提供时，会话会持久化到 Redis。
    """

    def __init__(self, persistence: DialoguePersistence | None = None) -> None:
        self.sessions: dict[str, DialogueState] = {}
        self._persistence = persistence

    async def create_session(
        self,
        session_id: str,
        route: dict[str, Any],
        user_intent: dict[str, Any],
    ) -> DialogueState:
        """创建新会话并注册。"""
        state = DialogueState(session_id, route, user_intent)
        self.sessions[session_id] = state
        if self._persistence:
            await self._persistence.save(session_id, state)
        logger.info("[Dialogue] 创建会话 %s", session_id)
        return state

    async def get_session(self, session_id: str) -> DialogueState | None:
        """获取已有会话（内存 → Redis → None）。"""
        # 1) 内存命中
        state = self.sessions.get(session_id)
        if state is not None:
            return state
        # 2) 从 Redis 恢复
        if self._persistence:
            data = await self._persistence.load(session_id)
            if data:
                state = DialogueState.from_dict(data)
                self.sessions[session_id] = state
                logger.info("[Dialogue] 从 Redis 恢复会话 %s", session_id)
                return state
        return None

    async def remove_session(self, session_id: str) -> None:
        """删除会话。"""
        self.sessions.pop(session_id, None)
        if self._persistence:
            await self._persistence.delete(session_id)

    async def _persist_state(self, state: DialogueState) -> None:
        """持久化当前状态到 Redis（process_instruction 内部使用）。"""
        if self._persistence:
            await self._persistence.save(state.session_id, state)

    # ---- 指令分发 --------------------------------------------------------

    async def process_instruction(self, session_id: str, instruction: str) -> dict[str, Any]:
        """处理用户指令的主入口。

        Returns:
            {"reply": str, "route": dict, "changes_made": list}

        Raises:
            DialogueError: 会话不存在或对话轮次已达上限
        """
        state = await self.get_session(session_id)
        if not state:
            raise DialogueError(
                message="会话不存在",
                details={"session_id": session_id},
            )

        if state.is_expired():
            raise DialogueError(
                message="对话轮次已达上限，请重新开始",
                details={"session_id": session_id, "turn_count": state.turn_count},
            )

        # 记录用户消息
        state.add_message("user", instruction)
        state.turn_count += 1
        logger.info("[Dialogue] 会话 %s 第 %d 轮: %s", session_id, state.turn_count, instruction)

        # 分类 + 处理
        instruction_type = self._classify_instruction(instruction)
        handler = {
            "replace": self._handle_replace,
            "pace": self._handle_pace,
            "budget": self._handle_budget,
            "time": self._handle_time,
            "retry": self._handle_retry,
            "emotion_weight": self._handle_emotion_weight,
            "mood": self._handle_mood_adjust,
        }.get(instruction_type)

        if handler:
            result = await handler(state, instruction)
        else:
            result = {
                "reply": (
                    "抱歉，我没有理解你的意思。你可以试试：\n"
                    "- 换掉某个景点\n"
                    "- 调整节奏（太赶了/想轻松点）\n"
                    "- 调整预算（太贵了/便宜一点）\n"
                    "- 调整时间（早一点/晚一点）\n"
                    "- 太累了换个轻松的\n"
                    "- 想放松一下\n"
                    "- 重新规划"
                ),
                "route": state.route,
                "changes_made": [],
            }

        # 记录系统回复
        state.add_message("assistant", result.get("reply", ""))

        # 注入调试信息（不持久化，仅用于响应）
        changes = result.get("changes_made", [])
        result["_debug"] = {
            "instruction_type": instruction_type,
            "turn": state.turn_count,
            "max_turns": state.max_turns,
            "history_len": len(state.history),
            "pace": state.user_intent.get("pace", ""),
            "emotion_need": state.user_intent.get("emotion_need"),
            "budget_per_person": state.user_intent.get("budget", {}).get("per_person", 0),
            "time_range": {
                "start": state.user_intent.get("time", {}).get("start", "09:00"),
                "end": state.user_intent.get("time", {}).get("end", "18:00"),
            },
            "change_count": len(changes),
            "change_types": [c.get("type") for c in changes],
        }

        # 持久化到 Redis（不影响主流程）
        await self._persist_state(state)
        return result

    # ---- 指令分类 --------------------------------------------------------

    def _classify_instruction(self, instruction: str) -> str:
        """基于关键词将用户指令分类。

        V2 新增类型: emotion_weight（情绪/精力调整）, mood（情感需求）
        """
        text = instruction.lower()

        # V2: 情绪/精力调整（优先匹配，因为"累"也可能触发 pace）
        if any(kw in text for kw in ["太累", "累", "疲惫", "换个轻松", "精力", "体力", "强度"]):
            return "emotion_weight"

        # V2: 情感需求（"烦"也可能触发情绪调整，但属于不同处理）
        if any(kw in text for kw in ["烦", "放松", "治愈", "平静", "焦虑", "压抑"]):
            return "mood"

        # 替换
        if any(kw in text for kw in ["换", "替换", "不喜欢", "不要", "去掉"]):
            return "replace"

        # 节奏
        if any(kw in text for kw in ["赶", "轻松", "慢", "快", "紧凑"]):
            return "pace"

        # 预算
        if any(kw in text for kw in ["贵", "便宜", "省钱", "预算"]):
            return "budget"

        # 时间
        if any(kw in text for kw in ["早", "晚", "时间", "点之前", "之前结束"]):
            return "time"
        if re.search(r"\d{1,2}[点时:：]", text):
            return "time"

        # 不满
        if any(kw in text for kw in ["不行", "重新", "再来"]):
            return "retry"

        return "unknown"

    # ---- 替换指令 --------------------------------------------------------

    async def _handle_replace(self, state: DialogueState, instruction: str) -> dict[str, Any]:
        """处理替换指令：换掉路线中的某个景点。"""
        poi_name = self._extract_poi_name(instruction, state.route)

        if not poi_name:
            return {
                "reply": "你想换掉哪个景点？请告诉我景点名称。",
                "route": state.route,
                "changes_made": [],
            }

        # 定位要替换的 POI 在路线中的位置
        replace_index: int | None = None
        for i, step in enumerate(state.route.get("route", [])):
            if step["poi"]["name"] == poi_name:
                replace_index = i
                break

        if replace_index is None:
            return {
                "reply": f"没有找到名为'{poi_name}'的景点。",
                "route": state.route,
                "changes_made": [],
            }

        # 从候选池找替代
        used_ids = {step["poi"]["id"] for step in state.route.get("route", [])}
        unused = [p for p in state.route.get("unused_candidates", []) if p["id"] not in used_ids]

        if not unused:
            return {
                "reply": "抱歉，没有其他合适的备选景点了。",
                "route": state.route,
                "changes_made": [],
            }

        original_poi = state.route["route"][replace_index]["poi"]
        replacement = self._pick_best_replacement(original_poi, unused)

        # 构建新的路线步骤
        new_route = self._deep_copy_route(state.route)
        prev_poi = new_route["route"][replace_index - 1]["poi"] if replace_index > 0 else None
        prev_departure_str = (
            new_route["route"][replace_index - 1]["departure_time"]
            if replace_index > 0
            else "09:00"
        )

        prev_departure = parse_time(prev_departure_str)
        from backend.services.solver import estimate_travel_time

        travel = estimate_travel_time(prev_poi, replacement)
        arrival = prev_departure + timedelta(minutes=travel)
        stay = replacement.get("avg_stay_min", 60)
        departure = arrival + timedelta(minutes=stay)

        from backend.services.solver import estimate_distance

        new_step: dict[str, Any] = {
            "poi": replacement,
            "arrival_time": format_time(arrival),
            "departure_time": format_time(departure),
            "travel_from_prev": {
                "distance_m": round(estimate_distance(prev_poi, replacement)),
                "time_min": round(travel),
            },
        }

        new_route["route"][replace_index] = new_step

        # 更新候选池：被换出的放回，被换入的移出
        new_route["unused_candidates"] = [p for p in unused if p["id"] != replacement["id"]]
        new_route["unused_candidates"].append(original_poi)

        state.route = new_route
        logger.info("[Dialogue] 替换 %s -> %s", poi_name, replacement["name"])

        return {
            "reply": f"好的，我已经把'{poi_name}'换成了'{replacement['name']}'。",
            "route": new_route,
            "changes_made": [
                {
                    "type": "replace",
                    "original": poi_name,
                    "replacement": replacement["name"],
                }
            ],
        }

    def _extract_poi_name(self, instruction: str, route: dict[str, Any]) -> str | None:
        """从用户指令中提取要操作的 POI 名称。"""
        # 1) 直接匹配路线中已有的 POI 名称
        for step in route.get("route", []):
            name = step["poi"]["name"]
            if name in instruction:
                return name

        # 2) 匹配序号："第2个" / "第二个" / "2"
        match = re.search(r"第?(\d+)个?", instruction)
        if match:
            index = int(match.group(1)) - 1
            steps = route.get("route", [])
            if 0 <= index < len(steps):
                return steps[index]["poi"]["name"]

        return None

    @staticmethod
    def _pick_best_replacement(
        original: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """从候选列表中选出与 original 最相似的替代 POI。"""
        orig_cat = original.get("category")
        orig_exc = original.get("emotion_tags", {}).get("excitement", 0)

        def score(c: dict[str, Any]) -> float:
            cat_score = 1.0 if c.get("category") == orig_cat else 0.5
            exc = c.get("emotion_tags", {}).get("excitement", 0)
            emo_score = 1.0 - abs(exc - orig_exc)
            return cat_score * 0.6 + emo_score * 0.4

        return max(candidates, key=score)

    @staticmethod
    def _deep_copy_route(route: dict[str, Any]) -> dict[str, Any]:
        """深拷贝路线字典（避免修改原对象）。"""
        import copy

        return copy.deepcopy(route)

    # ---- 节奏调整 --------------------------------------------------------

    async def _handle_pace(self, state: DialogueState, instruction: str) -> dict[str, Any]:
        """处理节奏调整指令。"""
        current_pace = state.user_intent.get("pace", "平衡型")

        if any(kw in instruction for kw in ["太慢", "紧凑", "快"]):
            # 加快：闲逛型 → 平衡型 → 特种兵型
            new_pace = {"闲逛型": "平衡型", "平衡型": "特种兵型", "特种兵型": "特种兵型"}.get(
                current_pace, "特种兵型"
            )
            reply = "好的，我帮你调整为{}行程。".format(
                {
                    "闲逛型": "更紧凑的",
                    "平衡型": "紧凑型",
                    "特种兵型": "更紧凑的",
                }.get(current_pace, "紧凑型")
            )
        elif any(kw in instruction for kw in ["太赶", "太累", "轻松"]):
            # 放慢：特种兵型 → 平衡型 → 闲逛型
            new_pace = {"特种兵型": "平衡型", "平衡型": "闲逛型", "闲逛型": "闲逛型"}.get(
                current_pace, "闲逛型"
            )
            reply = "好的，我帮你调整为{}行程。".format(
                {
                    "特种兵型": "更轻松的",
                    "平衡型": "轻松型",
                    "闲逛型": "更轻松的",
                }.get(current_pace, "轻松型")
            )
        else:
            new_pace = "平衡型"
            reply = "好的，我帮你调整为平衡型行程。"

        state.user_intent["pace"] = new_pace

        # 收集所有候选 POI（已选 + 未选），过滤后重新求解
        all_candidates = self._collect_all_candidates(state)
        from backend.services.filters import filter_candidates
        from backend.services.solver import solve_route

        filtered = filter_candidates(all_candidates, state.user_intent)
        start_time = state.user_intent.get("time", {}).get("start", "09:00")
        new_route = solve_route(
            filtered,
            state.user_intent,
            start_time,
            dynamic_weights=state.user_intent.get("_dynamic_weights"),
        )
        state.route = new_route

        logger.info("[Dialogue] 节奏调整 -> %s", new_pace)
        return {
            "reply": reply,
            "route": new_route,
            "changes_made": [{"type": "pace", "new_pace": new_pace}],
        }

    # ---- 预算调整 --------------------------------------------------------

    async def _handle_budget(self, state: DialogueState, instruction: str) -> dict[str, Any]:
        """处理预算调整指令。"""
        current_budget = state.user_intent.get("budget", {}).get("per_person", 500)
        original_budget = current_budget

        if any(kw in instruction for kw in ["便宜", "省钱", "少", "降"]):
            new_budget = int(current_budget * 0.8)
            reply = f"好的，我帮你把预算调整到每人{new_budget}元。"
        else:
            new_budget = int(current_budget * 1.3)
            reply = f"好的，我帮你把预算调整到每人{new_budget}元。"

        # 预算边界限制：不低于20，不高于原始预算的10倍
        new_budget = max(20, min(new_budget, max(original_budget * 10, 5000)))

        state.user_intent.setdefault("budget", {})["per_person"] = new_budget

        # 重新过滤 + 求解
        all_candidates = self._collect_all_candidates(state)
        from backend.services.filters import filter_candidates
        from backend.services.solver import solve_route

        filtered = filter_candidates(all_candidates, state.user_intent)
        start_time = state.user_intent.get("time", {}).get("start", "09:00")
        new_route = solve_route(
            filtered,
            state.user_intent,
            start_time,
            dynamic_weights=state.user_intent.get("_dynamic_weights"),
        )
        state.route = new_route

        logger.info("[Dialogue] 预算调整 -> %d", new_budget)
        return {
            "reply": reply,
            "route": new_route,
            "changes_made": [{"type": "budget", "new_budget": new_budget}],
        }

    # ---- 时间调整 --------------------------------------------------------

    def _apply_time_offset(self, state: DialogueState, offset_min: int) -> None:
        """将时间偏移应用到路线中的所有时间点。"""
        if offset_min == 0 or not state.route.get("route"):
            return

        for step in state.route["route"]:
            for key in ["arrival_time", "departure_time"]:
                if key in step:
                    try:
                        h, m = map(int, step[key].split(":"))
                        total_min = max(0, min(24 * 60 - 1, h * 60 + m + offset_min))
                        step[key] = f"{total_min // 60:02d}:{total_min % 60:02d}"
                    except Exception as e:
                        logger.warning("dialogue error: %s", e)

    async def _handle_time(self, state: DialogueState, instruction: str) -> dict[str, Any]:
        """处理时间调整指令（增量调整，不重新规划）。"""
        time_match = re.search(r"(\d{1,2})[点时:：](\d{2})?", instruction)

        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            if any(kw in instruction for kw in ["下午", "晚上", "晚"]) and hour <= 12:
                hour += 12
            new_time = f"{hour:02d}:{minute:02d}"

            if any(kw in instruction for kw in ["早", "提前", "出发"]):
                state.user_intent.setdefault("time", {})["start"] = new_time
                reply = f"好的，我把出发时间调整到{new_time}。"
            else:
                state.user_intent.setdefault("time", {})["end"] = new_time
                reply = f"好的，我确保行程在{new_time}前结束。"
        elif "早" in instruction:
            current_start = state.user_intent.get("time", {}).get("start", "09:00")
            hour = max(6, int(current_start.split(":")[0]) - 1)
            new_time = f"{hour:02d}:00"
            state.user_intent.setdefault("time", {})["start"] = new_time
            reply = f"好的，我把出发时间提前到{new_time}。"
        elif "晚" in instruction:
            current_end = state.user_intent.get("time", {}).get("end", "22:00")
            hour = min(23, int(current_end.split(":")[0]) + 1)
            new_time = f"{hour:02d}:00"
            state.user_intent.setdefault("time", {})["end"] = new_time
            reply = f"好的，我把结束时间推迟到{new_time}。"
        else:
            reply = "好的，我会注意时间安排。"

        # 计算并应用时间偏移
        old_start = state.user_intent.get("time", {}).get("start", "09:00")
        new_start = state.user_intent.get("time", {}).get("start", "09:00")
        try:
            old_h, old_m = map(int, old_start.split(":"))
            new_h, new_m = map(int, new_start.split(":"))
            offset_min = (new_h * 60 + new_m) - (old_h * 60 + old_m)
        except Exception as e:
            logger.warning("dialogue error: %s", e)
            offset_min = 0

        self._apply_time_offset(state, offset_min)

        logger.info("[Dialogue] 时间调整（增量） -> %s", state.user_intent.get("time", {}))
        return {
            "reply": reply,
            "route": state.route,
            "changes_made": [
                {"type": "time", "new_time": state.user_intent.get("time", {}), "incremental": True}
            ],
        }

    # ---- 重新规划 --------------------------------------------------------

    async def _handle_retry(self, state: DialogueState, instruction: str) -> dict[str, Any]:
        """处理重新规划指令。"""
        import random

        all_candidates = self._collect_all_candidates(state)
        from backend.services.filters import filter_candidates
        from backend.services.solver import solve_route

        filtered = filter_candidates(all_candidates, state.user_intent)
        # 打乱候选顺序，增加结果多样性
        random.shuffle(filtered)
        start_time = state.user_intent.get("time", {}).get("start", "09:00")
        new_route = solve_route(
            filtered,
            state.user_intent,
            start_time,
            dynamic_weights=state.user_intent.get("_dynamic_weights"),
        )
        state.route = new_route

        logger.info("[Dialogue] 重新规划路线")
        return {
            "reply": "好的，我重新为你规划了一条路线。",
            "route": new_route,
            "changes_made": [{"type": "retry"}],
        }

    # ---- V2: 情绪/精力权重调整 ---------------------------------------------------

    async def _handle_emotion_weight(
        self, state: DialogueState, instruction: str
    ) -> dict[str, Any]:
        """处理情绪/精力调整指令：如"太累了换个轻松的""太兴奋了"。

        调整 dynamic_weights 中的 gamma（疲劳惩罚）和 beta（情绪收益），
        然后全量重算。
        """
        text = instruction.lower()

        # 分析调整方向
        gamma_delta = 0.0
        beta_delta = 0.0
        reply_parts = []

        if any(kw in text for kw in ["累", "轻松", "精力"]):
            gamma_delta = 1.0  # gamma 翻倍（更在意疲劳）
            reply_parts.append("降低体力消耗权重")
        if any(kw in text for kw in ["兴奋", "刺激", "嗨"]):
            beta_delta = 0.3  # beta 提高（更在意情绪体验）
            reply_parts.append("提高兴奋感权重")

        if not reply_parts:
            reply_parts.append("调整精力分配")

        # 构建动态权重（保留原有的 alpha/delta/budget_strictness）
        current_weights = dict(state.user_intent.get("_dynamic_weights", {}))
        current_weights["gamma"] = max(
            0.1, current_weights.get("gamma", _GAMMA) + gamma_delta * 0.5
        )
        current_weights["beta"] = max(0.1, current_weights.get("beta", _BETA) + beta_delta * 0.5)
        # 上限保护
        current_weights["gamma"] = min(3.0, current_weights["gamma"])
        current_weights["beta"] = min(3.0, current_weights["beta"])
        state.user_intent["_dynamic_weights"] = current_weights

        reply = "好的，" + "，".join(reply_parts) + "，插入更多休息点。已重新规划。"

        # 全量重算
        all_candidates = self._collect_all_candidates(state)
        from backend.services.filters import filter_candidates
        from backend.services.solver import solve_route

        filtered = filter_candidates(all_candidates, state.user_intent)
        start_time = state.user_intent.get("time", {}).get("start", "09:00")
        new_route = solve_route(
            filtered,
            state.user_intent,
            start_time,
            dynamic_weights=current_weights,
        )
        state.route = new_route

        logger.info(
            "[Dialogue] 情绪权重调整: gamma=%.2f beta=%.2f",
            current_weights.get("gamma", _GAMMA),
            current_weights.get("beta", _BETA),
        )
        return {
            "reply": reply,
            "route": new_route,
            "changes_made": [{"type": "emotion_weight", "new_weights": current_weights}],
        }

    # ---- V2: 情感需求调整 -------------------------------------------------------

    async def _handle_mood_adjust(self, state: DialogueState, instruction: str) -> dict[str, Any]:
        """处理情感需求指令：如"最近有点烦，想放松一下"。

        设置 emotion_need，调整偏好权重，然后全量重算。
        """
        text = instruction.lower()

        # 识别情感需求
        if any(kw in text for kw in ["烦", "焦虑", "压抑"]):
            emotion_need = "放松"
            reply = "好的，我帮你调整为治愈放松型路线，多安排安静舒缓的景点。"
            # tranquility 权重提升
            prefs = state.user_intent.setdefault("preferences", {})
            prefs["tranquility"] = max(prefs.get("tranquility", 0.5), 0.8)
        elif any(kw in text for kw in ["无聊", "没意思"]):
            emotion_need = "新鲜感"
            reply = "好的，我帮你找一些没去过的新地方，增加新鲜感。"
            prefs = state.user_intent.setdefault("preferences", {})
            prefs["novelty"] = 0.8
        else:
            emotion_need = "放松"
            reply = "好的，我帮你调整路线氛围。"

        state.user_intent["emotion_need"] = emotion_need

        # 全量重算
        all_candidates = self._collect_all_candidates(state)
        from backend.services.filters import filter_candidates
        from backend.services.solver import solve_route

        filtered = filter_candidates(all_candidates, state.user_intent)
        start_time = state.user_intent.get("time", {}).get("start", "09:00")
        dynamic_weights = state.user_intent.get("_dynamic_weights")
        new_route = solve_route(
            filtered,
            state.user_intent,
            start_time,
            dynamic_weights=dynamic_weights,
        )
        state.route = new_route

        logger.info("[Dialogue] 情感需求调整: %s", emotion_need)
        return {
            "reply": reply,
            "route": new_route,
            "changes_made": [{"type": "mood_adjust", "emotion_need": emotion_need}],
        }

    # ---- 通用工具 --------------------------------------------------------

    @staticmethod
    def _collect_all_candidates(state: DialogueState) -> list[dict[str, Any]]:
        """从当前路线中收集所有候选 POI（已选 + 未选）。"""
        route_pois = [step["poi"] for step in state.route.get("route", [])]
        unused = state.route.get("unused_candidates", [])
        # 去重（以 id 为准）
        seen: set[str] = set()
        all_cands: list[dict[str, Any]] = []
        for p in route_pois + unused:
            if p["id"] not in seen:
                seen.add(p["id"])
                all_cands.append(p)
        return all_cands


# ---------------------------------------------------------------------------
# 全局实例 + 便捷函数
# ---------------------------------------------------------------------------


def _create_dialogue_persistence() -> DialoguePersistence | None:
    """根据配置创建持久化后端（无配置或 Redis 不可达时返回 None）。"""
    try:
        from backend.config import settings

        rs = settings.redis
        redis_url = (
            f"redis://:{quote_plus(rs.password)}@{rs.host}:{rs.port}/{rs.db}"
            if rs.password
            else f"redis://{rs.host}:{rs.port}/{rs.db}"
        )
        return DialoguePersistence(redis_url=redis_url)
    except (ImportError, AttributeError):
        return None


dialogue_engine = DialogueEngine(persistence=_create_dialogue_persistence())


async def create_dialogue(
    session_id: str, route: dict[str, Any], user_intent: dict[str, Any]
) -> dict[str, str]:
    """创建新对话会话。"""
    await dialogue_engine.create_session(session_id, route, user_intent)
    return {
        "session_id": session_id,
        "message": "对话已创建，你可以告诉我如何调整路线。",
    }


async def process_dialogue(session_id: str, instruction: str) -> dict[str, Any]:
    """处理对话指令。"""
    return await dialogue_engine.process_instruction(session_id, instruction)
