"""CityFlow TUI 偏好对话组件。

在规划路线前，通过聊天式交互收集用户偏好。
支持: 身份识别、主动推荐、多轮追问、偏好确认。
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog, Static


class PreferenceChat(Static):
    """偏好对话面板。

    状态机:
      idle → greeting (新用户问昵称)
           → recommend (老用户 → 展示 A/B/C/D)
           → asking (用户选 C → 多轮追问收集偏好)
           → done (收集完成 → 通知外部开始规划)
    """

    def __init__(self, preference_manager: Any | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.pm = preference_manager
        self._chat_log: RichLog | None = None
        self._chat_input: Input | None = None
        self._btn_confirm: Button | None = None
        self._btn_skip: Button | None = None
        self._state = "idle"

        # 收集到的偏好
        self.collected_intent: dict = {}
        self._demand_vector: dict = {}
        self._user_stated_prefs: dict = {}
        self._current_context: dict = {}

        # 多轮追问状态
        self._asked_dims: list[str] = []  # 已问过的维度
        self._dialogue_round = 0

    def compose(self) -> ComposeResult:
        self._chat_log = RichLog(highlight=True, markup=False, max_lines=30)
        yield self._chat_log

        self._rec_area = Static("")
        yield self._rec_area

        inp = Input(
            placeholder="输入你的回答…",
            id="pref-chat-input",
        )
        self._chat_input = inp
        with Vertical():
            yield inp
            with Horizontal():
                btn_send = Button("发送", id="pref-chat-send", variant="primary")
                btn_plan = Button("开始规划", id="pref-chat-plan", variant="primary")
                btn_restart = Button("重新回答", id="pref-chat-restart")
                self._btn_confirm = btn_plan
                self._btn_skip = btn_restart
                yield Horizontal(btn_send, btn_plan, btn_restart)

    def _write(self, text: str, style: str = "") -> None:
        if self._chat_log:
            self._chat_log.write(Text(text, style=style))

    def _write_chat(self, role: str, content: str) -> None:
        style = "bold cyan" if role == "ai" else "bold green"
        prefix = "AI: " if role == "ai" else "你: "
        self._write(f"{prefix}{content}", style)

    # ── 外部接口 ──────────────────────────────────────────

    def set_preference_manager(self, pm: Any) -> None:
        self.pm = pm

    def set_context(self, context: dict) -> None:
        self._current_context = context

    def get_collected_intent(self) -> dict:
        return self.collected_intent

    def get_demand_vector(self) -> dict:
        return self._demand_vector

    def reset_state(self) -> None:
        self._state = "idle"
        self.collected_intent = {}
        self._demand_vector = {}
        self._user_stated_prefs = {}
        self._asked_dims = []
        self._dialogue_round = 0
        if self._chat_log:
            self._chat_log.clear()
        if self._rec_area:
            self._rec_area.update("")

    # ── 初始化 ────────────────────────────────────────────

    async def init_chat(self) -> None:
        """初始化对话：加载用户信息，展示上下文推荐。"""
        if not self.pm:
            self._write_chat("ai", "你好！请描述你的出行需求～")
            self._state = "asking"
            return

        status = await self.pm.get_user_status(self._current_context)

        if status.get("is_new"):
            self._write_chat("ai", "你好呀！第一次见面，怎么称呼你？")
            self._state = "greeting"
        else:
            self._write_chat("ai", status.get("greeting", "又见面啦！"))
            if status.get("context_info"):
                self._write(f"📋 {status['context_info']}", "dim")
            for hint in status.get("context_hints", []):
                self._write(f"💡 {hint}", "italic #888888")
            # 老用户直接展示推荐
            await self._show_recommendations()

    # ── 主入口 ────────────────────────────────────────────

    async def start_dialogue(self, user_input: str) -> None:
        """处理用户输入，状态机路由。"""
        self._write_chat("user", user_input)

        if self._state == "greeting":
            await self._handle_greeting(user_input)
        elif self._state == "recommend":
            await self._handle_recommend_choice(user_input)
        elif self._state == "asking":
            await self._handle_free_input(user_input)

    async def _handle_greeting(self, text: str) -> None:
        """处理昵称输入 → 展示推荐。"""
        name = text.strip()
        if self.pm:
            from backend.services.preference_manager import register_user

            register_user(name)
            self.pm.user_id = name
        self._write_chat("ai", f"好的{name}！以后我会记住你的偏好。")
        # 新用户注册后也展示推荐（至少 C/D）
        await self._show_recommendations()

    # ── 推荐展示 ──────────────────────────────────────────

    async def _show_recommendations(self) -> None:
        """展示推荐选项 A/B/C/D（无历史时只显示 C/D）。"""
        if not self.pm:
            self._write_chat("ai", "请描述你的出行需求～")
            self._state = "asking"
            return

        rec_result = await self.pm.generate_recommendations("", self._current_context)
        recs = rec_result.get("recommendations", [])

        if not recs:
            # 无任何选项 → 直接进入追问
            await self._start_asking()
            return

        self._state = "recommend"
        self._write_chat("ai", "这次想怎么安排？")

        lines = []
        for r in recs:
            rid = r.get("id", "?")
            label = r.get("label", "")
            desc = r.get("description", "")
            if rid in ("c", "d"):
                lines.append(f"  [{rid.upper()}] {label} — {desc}")
            else:
                lines.append(f"  [{rid.upper()}] {label} — {desc}")
        self._write("\n".join(lines), "bold #e94560")
        self._write("输入选项编号 (A/B/C/D)", "dim")

    # ── 推荐选择 ──────────────────────────────────────────

    async def _handle_recommend_choice(self, choice: str) -> None:
        """处理 A/B/C/D 选择。"""
        c = choice.strip().lower()

        if c == "c":
            await self._start_asking()
            return
        elif c == "d":
            self._state = "done"
            self._write_chat("ai", "好的，使用默认配置为你规划！")
            self._on_preference_done()
            return

        # A/B: 使用推荐对应的 intent_hint
        if self.pm:
            rec_result = await self.pm.generate_recommendations(
                "", self._current_context
            )
            for r in rec_result.get("recommendations", []):
                if r.get("id") == c:
                    hint = r.get("intent_hint", {})
                    if hint:
                        self._user_stated_prefs.update(hint)
                        self.collected_intent.update(hint)
                        self._write_chat("ai", f"好的，按{r.get('label', '')}来安排！")
                    break

        self._state = "done"
        self._on_preference_done()

    # ── 多轮追问 ──────────────────────────────────────────

    async def _start_asking(self) -> None:
        """进入追问模式（用户选 C 后）。"""
        self._state = "asking"
        self._asked_dims = []
        self._dialogue_round = 0
        self._write_chat("ai", "好的，请描述你的出行偏好～")
        # 直接问第一个问题
        await self._ask_next_question()

    async def _ask_next_question(self) -> None:
        """根据已收集信息，追问下一个缺失维度。"""
        self._dialogue_round += 1
        if self._dialogue_round > 5:
            # 够了，开始规划
            self._write_chat("ai", "好的，信息足够了我来规划路线！")
            self._state = "done"
            self._on_preference_done()
            return

        try:
            from backend.services.preference_dialogue import (
                ask_preference_question,
                get_missing_dimensions,
            )

            dv = self._demand_vector or {}
            conf = dv.get("_confidence", {})

            # 没有 LLM 数据 → 直接降级到 fallback
            if dv:
                missing = get_missing_dimensions(dv, conf)
                missing = [d for d in missing if d not in self._asked_dims]

                if not missing:
                    self._write_chat("ai", "好的，让我为你规划路线～")
                    self._state = "done"
                    self._on_preference_done()
                    return

                q_result = await ask_preference_question(
                    self.collected_intent, missing[:1], ""
                )
                if q_result and q_result.get("question"):
                    self._asked_dims.append(q_result["dimension"])
                    self._write_chat("ai", q_result["question"])
                    return
        except Exception:
            pass

        # 降级：顺序问问题（无 LLM 时也走这里）
        await self._fallback_ask()

    def _fallback_ask(self) -> None:
        """降级追问（LLM 不可用时）。"""
        asked = set(self._asked_dims)

        questions = [
            ("pace", "你们今天是打算特种兵式刷景点，还是懒洋洋闲逛一天？"),
            ("budget_sensitivity", "预算方面～大概人均多少比较舒服？"),
            ("tranquility_seeking", "偏向安静治愈的氛围，还是热闹有活力的？"),
            ("physical_energy", "体力怎么样？乐意多走走路还是想轻松点？"),
        ]

        for dim, question in questions:
            if dim not in asked:
                self._asked_dims.append(dim)
                self._write_chat("ai", question)
                return

        # 都问过了 → 规划
        self._write_chat("ai", "好的，让我为你规划路线～")
        self._state = "done"
        self._on_preference_done()

    async def _handle_free_input(self, user_input: str) -> None:
        """处理自由输入（追问模式下）。"""
        text = user_input.lower()
        stated: dict = {}

        # 终止信号
        if any(w in text for w in ["随便", "都行", "无所谓", "开始规划"]):
            self._write_chat("ai", "好的，我按经验帮你安排，不满意随时说～")
            self._state = "done"
            self._on_preference_done()
            return

        # 先尝试 LLM 分析
        dim = self._asked_dims[-1] if self._asked_dims else ""
        if dim:
            try:
                from backend.services.preference_dialogue import analyze_user_response

                result = await analyze_user_response(dim, user_input)
                val = result.get("value", 0.5)
                # 映射到 collected_intent
                dim_map = {
                    "pace": ("pace", lambda v: "悠闲型" if v < 0.4 else "平衡型" if v < 0.7 else "紧凑型"),
                    "budget_sensitivity": ("budget", lambda v: {}),
                    "tranquility_seeking": ("pace", lambda v: "闲逛型" if v > 0.6 else "平衡型"),
                    "physical_energy": ("pace", lambda v: "闲逛型" if v < 0.4 else "平衡型"),
                }
                if dim in dim_map:
                    key, fn = dim_map[dim]
                    stated[key] = fn(val)
            except Exception:
                pass

        # 关键词兜底提取
        if not stated:
            if any(w in text for w in ["悠闲", "慢慢", "放松", "闲逛", "懒"]):
                stated["pace"] = "闲逛型"
            elif any(w in text for w in ["紧凑", "高效", "赶", "快"]):
                stated["pace"] = "特种兵型"
            elif any(w in text for w in ["适中", "平衡"]):
                stated["pace"] = "平衡型"

            import re
            budget_match = re.search(r"(\d+)\s*[元块]", text)
            if budget_match:
                stated["budget"] = {
                    "per_person": int(budget_match.group(1)),
                    "type": "硬约束",
                }

        if stated:
            self._user_stated_prefs.update(stated)
            self.collected_intent.update(stated)

        # 看看是否问够了，没够继续
        if len(self._asked_dims) >= 5:
            self._write_chat("ai", "好的，让我为你规划路线～")
            self._state = "done"
            self._on_preference_done()
        elif stated:
            self._write_chat("ai", "收到！还有其他想法吗？")
            await self._ask_next_question()
        else:
            await self._ask_next_question()

    # ── 完成回调 ──────────────────────────────────────────

    def _on_preference_done(self) -> None:
        self.post_message(self.PreferenceDone(self.collected_intent, self._user_stated_prefs))

    class PreferenceDone:
        def __init__(self, collected_intent: dict, user_stated_prefs: dict):
            self.collected_intent = collected_intent
            self.user_stated_prefs = user_stated_prefs

    # ── 事件绑定 ──────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        inp = self._chat_input
        if not inp:
            return

        if btn_id == "pref-chat-send":
            text = inp.value.strip()
            if text:
                inp.value = ""
                self._on_user_input(text)
        elif btn_id == "pref-chat-plan":
            if self._state == "done":
                pass
            else:
                self._write_chat("ai", "好的，按当前了解的信息来规划！")
                self._state = "done"
                self._on_preference_done()
        elif btn_id == "pref-chat-restart":
            self.reset_state()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "pref-chat-input":
            text = event.input.value.strip()
            if text:
                event.input.value = ""
                self._on_user_input(text)

    def _on_user_input(self, text: str) -> None:
        self._run_dialogue(text)

    @work(exit_on_error=False)
    async def _run_dialogue(self, text: str) -> None:
        await self.start_dialogue(text)
