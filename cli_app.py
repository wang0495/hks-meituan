"""CityFlow CLI — 智能出行规划终端。

用法:
    python cli_app.py                         交互模式
    python cli_app.py --debug                 调试模式（显示详细处理流程）
    python cli_app.py plan "..."              一键规划
    python cli_app.py plan "..." --debug      调试规划

调试模式下，每一步的处理过程、数据变化都会可视化展示。
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import httpx
from rich import box
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.rule import Rule
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# ── 配置 ────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
_USER_CONFIG_DIR = Path.home() / ".cityflow"
console = Console()
_DEBUG = False


# ══════════════════════════════════════════════════════════════════
#  调试输出系统
# ══════════════════════════════════════════════════════════════════

_PHASE_FLOW = [
    ("parsing", "🔍 意图解析"),
    ("identifying", "👤 身份识别"),
    ("ltm_predict", "🧠 LTM预测"),
    ("weight_mapping", "⚖️ 权重映射"),
    ("searching", "🔎 POI筛选"),
    ("solving", "🧮 路线求解"),
    ("narrating", "✍️ 文案生成"),
    ("saving", "💾 记忆保存"),
]

_PHASE_EXPLAIN = {
    "parsing":
    "读取用户输入 → 调用LLM或规则降级 → 提取结构化意图(time/budget/group/preferences/pace) "
    "→ 匹配用户画像(P1-P20)",
    "identifying":
    "检查用户身份文件 → 识别user_id → 判断新老用户 → 加载上下文",
    "ltm_predict":
    "查询LongTermMemory → 按当前上下文(weather/season/day_type)匹配历史记录 "
    "→ 加权评分 → 输出预测偏好(pace/budget/categories/emotion_need)",
    "weight_mapping":
    "取demand_vector → WeightMapper.compute_weights() "
    "→ 全局基线 + 用户个性化delta → 输出solver权重(alpha/beta/gamma/delta/budget_strictness)",
    "searching":
    "从city_poi_db加载2000+ POI → 按城市过滤 → "
    "按intent约束(filter_candidates) → 集成非标体验(nonstandard_experiences)",
    "solving":
    "5阶段TSPTW算法:\n"
    "  ① TW-NN贪心初始化(时间窗可行剪枝)\n"
    "  ② 2-opt局部优化\n"
    "  ③ 呼吸空间插入(高兴奋POI间插休息)\n"
    "  ④ 高潮收尾检查\n"
    "  ⑤ 心理学规则(峰终定律+享乐适应+损失厌恶)\n"
    "  → 路线合理性审核(地理回跳/时间/预算/节奏)\n"
    "  → 输出排序后的route + emotion_curve + audit_issues",
    "narrating":
    "模板驱动 → 每个POI生成: narrative/emotion_design/design_intent/leverage "
    "→ (可选)LLM润色 → 输出完整文案",
    "saving":
    "PreferenceManager.save_trip_to_memory() → "
    "LTM.record_trip(intent+summary+context) → trip_history追加一条",
}


def _flow_diagram(active_phase: str = "", done_phases: set = None) -> Panel:
    """生成处理流水线可视化。"""
    if done_phases is None:
        done_phases = set()

    t = Text()
    for i, (key, label) in enumerate(_PHASE_FLOW):
        if i > 0:
            t.append("  →  ", style="dim #555555")

        if key == active_phase:
            t.append(f"● {label}", style="bold cyan")
        elif key in done_phases:
            t.append(f"● {label}", style="green")
        else:
            t.append(f"○ {label}", style="dim #555555")

    return Panel(t, title="📋 处理流水线", box=box.ROUNDED, border_style="cyan" if active_phase else "gray")


def _render_emotion_chart(emotion_curve: list[dict]) -> Panel:
    """情绪曲线可视化（使用 sparkline + 条形图）。"""
    if not emotion_curve:
        return Panel("[dim]无情绪数据[/]", title="📊 情绪曲线", box=box.ROUNDED)

    SPARK = "▁▂▃▄▅▆▇█"
    dims = [
        ("兴奋", "excitement", "#e94560"),
        ("宁静", "tranquility", "#3498db"),
        ("文化", "culture_depth", "#9b59b6"),
        ("社交", "sociability", "#2ecc71"),
        ("惊喜", "surprise", "#f39c12"),
        ("体力", "physical_demand", "#e67e22"),
    ]

    t = Text()
    for label, key, color in dims:
        vals = [p.get(key, 0) or 0 for p in emotion_curve]
        if all(v == 0 for v in vals):
            continue

        # sparkline
        mx = max(vals) or 1
        line = ""
        for v in vals:
            idx = min(int(v / mx * 7), 7)
            line += SPARK[idx]

        avg = sum(vals) / len(vals)
        t.append(f" {label} ", style=color)
        t.append(f"{line}  [dim]avg={avg:.2f}[/]\n", style=color)

    # 疲劳曲线
    fatigue = [p.get("fatigue", 0) or 0 for p in emotion_curve]
    if any(f > 0 for f in fatigue):
        mx = max(fatigue) or 1
        line = ""
        for v in fatigue:
            idx = min(int(v / mx * 7), 7)
            line += SPARK[idx]
        avg = sum(fatigue) / len(fatigue)
        t.append(" 疲劳 ", style="#95a5a6")
        t.append(f"{line}  [dim]avg={avg:.2f}[/]\n", style="#95a5a6")

    return Panel(t, title="📊 情绪曲线", box=box.ROUNDED, border_style="#9b59b6")


def _render_weights_chart(weights: dict) -> Panel:
    """权重条形图可视化。"""
    if not weights:
        return Panel("[dim]无权重数据[/]", title="⚖️ 求解器权重", box=box.ROUNDED)

    WEIGHT_LABELS = {
        "alpha": "位移成本", "beta": "情绪收益", "gamma": "疲劳惩罚",
        "delta": "同类惩罚", "budget_strictness": "预算严格度",
    }
    WEIGHT_BASELINE = {"alpha": 1.0, "beta": 0.5, "gamma": 0.2, "delta": 0.8, "budget_strictness": 0.5}

    W = 20  # 条形宽度
    t = Text()

    for key in ["alpha", "beta", "gamma", "delta", "budget_strictness"]:
        val = weights.get(key, 0)
        baseline = WEIGHT_BASELINE.get(key, 0.5)
        label = WEIGHT_LABELS.get(key, key)

        # 条形图
        bar_len = min(W, max(1, int(val / 3.0 * W)))
        bar = "█" * bar_len + "░" * (W - bar_len)

        # 颜色：高于基线用绿，低于用红
        color = "#2ecc71" if val > baseline else "#e94560" if val < baseline else "#888888"
        diff = val - baseline
        diff_str = f"  ({'+' if diff > 0 else ''}{diff:.2f})" if abs(diff) > 0.05 else ""

        t.append(f" {label:6s} ", style=color)
        t.append(f"{bar} {val:.2f}{diff_str}\n", style=color)

    return Panel(t, title="⚖️ 求解器权重", box=box.ROUNDED, border_style="#2ecc71")


def _render_demand_chart(demand: dict) -> Panel:
    """需求向量条形图。"""
    if not demand:
        return Panel("[dim]无需求向量[/]", title="📌 需求向量", box=box.ROUNDED)

    LABELS = {
        "efficiency_seeking": "效率", "excitement_seeking": "刺激",
        "tranquility_seeking": "宁静", "budget_sensitivity": "预算",
        "novelty_seeking": "新颖", "social_desire": "社交", "physical_energy": "体力",
    }

    W = 15
    t = Text()
    for key, label in LABELS.items():
        val = demand.get(key, 0.5)
        bar_len = min(W, max(1, int(val * W)))
        bar = "█" * bar_len + "░" * (W - bar_len)
        color = "#e94560" if val > 0.65 else "#3498db" if val < 0.35 else "#888888"
        t.append(f" {label} ", style=color)
        t.append(f"{bar} {val:.2f}\n", style=color)

    return Panel(t, title="📌 需求向量", box=box.ROUNDED, border_style="yellow")


def _debug(msg: str, detail: str = "") -> None:
    """输出调试信息。"""
    if _DEBUG:
        ts = datetime.now().strftime("%H:%M:%S")
        console.print(f"  [dim]{ts}[/] [bold yellow]⚙[/] {msg}", highlight=False)
        if detail:
            for line in detail.split("\n"):
                console.print(f"    [dim]{line}[/]", highlight=False)


def _debug_explain(phase: str) -> None:
    """输出当前阶段的详细解释。"""
    if _DEBUG and phase in _PHASE_EXPLAIN:
        console.print(f"    [cyan]└─ {_PHASE_EXPLAIN[phase]}[/]")


def _debug_data(label: str, data: Any) -> None:
    """输出数据结构。"""
    if _DEBUG and data:
        import json
        try:
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
            lines = pretty.split("\n")
            if len(lines) > 20:
                lines = lines[:20] + ["         ... (截断)"]
            console.print(f"    [dim]{label}:[/]")
            for line in lines:
                console.print(f"      [dim]{line}[/]")
        except Exception:
            pass


def _debug_phase_start(phase: str, msg: str = "") -> None:
    """阶段开始标记。"""
    if _DEBUG:
        ts = datetime.now().strftime("%H:%M:%S")
        icon = {
            "parsing": "🔍", "identifying": "👤", "ltm_predict": "🧠",
            "weight_mapping": "⚖️", "searching": "🔎", "solving": "🧮",
            "narrating": "✍️", "saving": "💾",
        }.get(phase, "●")
        console.print()
        console.print(f"  [bold cyan]{icon} [{phase}] {msg}[/]")
        _debug_explain(phase)


# ══════════════════════════════════════════════════════════════════
#  API 调用
# ══════════════════════════════════════════════════════════════════

async def _plan_route_stream(
    user_input: str,
    user_id: str | None = None,
    context: dict | None = None,
) -> dict[str, Any]:
    """调用 /api/plan，SSE 流式处理，调试模式输出每一步。"""
    payload: dict[str, Any] = {"user_input": user_input}
    if user_id:
        payload["user_id"] = user_id
    if context:
        payload["current_context"] = context
    # 默认出发位置
    payload["start_location"] = "<auto>"

    # 调试模式标题
    if _DEBUG:
        console.print()
        console.print(Rule(f"[bold]🌿 开始规划: {user_input[:50]}[/]"))
        console.print(f"  [dim]请求体: {json.dumps(payload, ensure_ascii=False)}[/]")
        console.print()

    result: dict[str, Any] = {}
    done_phases: set[str] = set()
    active_phase = ""

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", f"{API_BASE}/api/plan", json=payload) as resp:
            if resp.status_code != 200:
                err = (await resp.aread()).decode()[:300]
                return {"error": f"后端返回 {resp.status_code}: {err}"}

            buf = ""
            evt = ""
            async for chunk in resp.aiter_bytes():
                buf += chunk.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line.startswith("event: "):
                        evt = line[7:].strip()
                    elif line.startswith("data: "):
                        if not evt:
                            continue
                        try:
                            data = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue

                        # 🔔 SSE 事件处理 + 调试输出
                        if evt == "phase":
                            phase = data.get("phase", "")
                            msg = data.get("message", "")
                            active_phase = phase
                            _debug_phase_start(phase, msg)

                            # 流水线图（每阶段更新一次）
                            if _DEBUG:
                                console.print(_flow_diagram(active_phase, done_phases))

                        elif evt == "debug_llm":
                            _debug(f"LLM调用: method={data.get('method','?')}, success={data.get('used', False)}")
                            if data.get("raw_response"):
                                _debug_data("LLM原始响应", data["raw_response"][:200])

                        elif evt == "debug_profile":
                            top3 = data.get("top3", [])
                            selected = data.get("selected", "")
                            _debug(f"画像匹配: 选定 {selected}")
                            if _DEBUG:
                                for p in top3:
                                    name = p.get("name", "?")
                                    score = p.get("score", 0)
                                    bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
                                    console.print(f"         {bar} [dim]{name}({score:.3f})[/]")

                        elif evt == "debug_preference":
                            uid = data.get("user_id", "?")
                            is_new = data.get("is_new", True)
                            ic = data.get("interaction_count", 0)
                            _debug(f"用户: {uid} ({'新' if is_new else '老'}用户, {ic}次交互)")
                            if data.get("context_info"):
                                _debug(f"上下文: {data['context_info']}")

                        elif evt == "debug_ltm":
                            action = data.get("action", "predict")
                            if action == "saved":
                                tc = data.get("trip_count", 0)
                                _debug(f"行程已记忆 (累计{tc}次)")
                            else:
                                dp = data.get("data_points", 0)
                                conf = data.get("confidence", 0.0)
                                pace = data.get("predicted_pace", "")
                                budget = data.get("predicted_budget", 0)
                                cats = data.get("predicted_categories", [])
                                _debug(f"LTM预测: {dp}条匹配, 置信度{conf:.0%}")
                                if pace:
                                    _debug(f"  预测节奏: {pace}, 预算: ¥{budget}, 偏好: {cats}")

                        elif evt == "debug_weight_mapper":
                            dv = data.get("demand_vector", {})
                            cw = data.get("computed_weights", {})
                            if _DEBUG:
                                console.print(_render_demand_chart(dv))
                                console.print(_render_weights_chart(cw))

                        elif evt == "debug_solver":
                            total = data.get("total_candidates", 0)
                            sel = data.get("selected_count", 0)
                            time_m = data.get("total_time_min", 0)
                            budget_val = data.get("total_budget", 0)
                            start_loc = data.get("start_location", "未指定")
                            _debug(f"求解器: {total}候选 → {sel}选中, {time_m}min, ¥{budget_val}")
                            _debug(f"出发位置: {start_loc}")
                            for stage in data.get("stages", []):
                                _debug(f"  阶段: {stage.get('name','?')} → {stage.get('result','?')}")
                            # 路线审核
                            audit = data.get("audit_issues", [])
                            if audit:
                                _debug(f"[yellow]📋 路线审核 ({len(audit)}项):[/]")
                                for issue in audit:
                                    sev = issue.get("severity", "info")
                                    msg = issue.get("message", "")
                                    icon = {"error":"✘","warning":"⚠","info":"ℹ"}.get(sev, "•")
                                    _debug(f"  {icon} [{sev}] {msg}")

                        elif evt == "debug_filter":
                            before = data.get("before", 0)
                            after = data.get("after", 0)
                            sel = data.get("selected", 0)
                            city = data.get("city", "")
                            if city:
                                _debug(f"POI筛选: {before}→{after} [城市:{city}] (选定{sel})")
                            else:
                                _debug(f"POI筛选: {before}→{after} (选定{sel})")

                        elif evt == "debug_perception":
                            w = data.get("weather", "?")
                            t = data.get("temperature", "?")
                            h = data.get("hour", "?")
                            s = data.get("season", "?")
                            f = data.get("fatigue", 0)
                            ci = data.get("city", "")
                            cv = data.get("city_vibe", "")
                            _debug(f"感知: {ci}[{cv}] {w} {t}°C {h}:00 {s} 疲劳={f}")

                        elif evt == "step":
                            result.setdefault("steps", []).append(data)
                            poi = data.get("poi", {})
                            name = poi.get("name", "—")
                            idx = data.get("index", len(result["steps"]))
                            _debug(f"📍 步骤{idx}: {name}")

                        elif evt == "anomaly":
                            msg = data.get("message", "")
                            sev = data.get("severity", "warning")
                            color = "red" if sev == "error" else "yellow"
                            _debug(f"[{color}]⚠ {msg}[/]")

                        elif evt == "adjustment_suggestion":
                            suggestions = data.get("suggestions", [])
                            reasoning = data.get("reasoning", "")
                            _debug(f"[blue]💡 调整建议: {reasoning}[/]")
                            for s in suggestions:
                                _debug(f"   → {s}")

                        elif evt == "done":
                            result["done"] = data
                            done_phases.add(active_phase)
                            _debug(f"[green]✔ 规划完成 route_id: {data.get('route_id','?')}[/]")

                        elif evt == "budget":
                            result["budget"] = data

                        elif evt == "memory_saved":
                            msg = data.get("message", "")
                            _debug(f"💾 {msg}")

                        elif evt == "error":
                            result["error"] = data.get("error", "未知错误")
                            _debug(f"[red]✘ 错误: {result['error']}[/]")

                        evt = ""

    return result


async def _dialogue_adjust(route_id: str, instruction: str) -> dict:
    """调用对话调整接口。"""
    if _DEBUG:
        _debug(f"[cyan]💬 发送调整指令: {instruction}[/]")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{API_BASE}/api/dialogue/{route_id}",
            json={"instruction": instruction},
        )
        if resp.status_code != 200:
            err = resp.text[:200]
            _debug(f"[red]✘ 调整失败: {err}[/]")
            return {"error": f"调整失败 ({resp.status_code}): {err}"}
        data = resp.json()
        if _DEBUG:
            _debug(f"[green]✔ 调整回复: {data.get('reply', '?')}[/]")
            changes = data.get("changes_made", [])
            if changes:
                _debug_data("变更记录", changes)
        return data


# ══════════════════════════════════════════════════════════════════
#  CLI 命令
# ══════════════════════════════════════════════════════════════════

@click.group(invoke_without_command=True)
@click.option("--debug", is_flag=True, help="调试模式（显示详细处理流程和数据）")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """🌿 CityFlow — 智能出行规划"""
    global _DEBUG
    _DEBUG = debug
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    # 无命令时进入交互模式
    if ctx.invoked_subcommand is None:
        _interactive_session()


@cli.command()
@click.argument("user_input")
@click.option("--user", "-u", help="用户ID")
@click.option("--debug", is_flag=True, help="调试模式")
@click.pass_context
def plan(ctx: click.Context, user_input: str, user: str | None, debug: bool) -> None:
    """一键规划路线"""
    global _DEBUG
    if debug:
        _DEBUG = True
    config = _load_user_config()
    uid = user or config.get("last_user_id", "")

    with Status("[cyan]正在规划…[/]", spinner="dots") if not _DEBUG else console.status(""):
        result = asyncio.run(_plan_route_stream(user_input, uid))

    if "error" in result:
        console.print(f"[red]✘ {result['error']}[/]")
        return

    _display_result(result)

    done = result.get("done", {})
    if done.get("route_id"):
        _debug(f"route_id: {done['route_id']}")


@cli.command()
@click.argument("route_id")
@click.argument("instruction")
@click.option("--debug", is_flag=True, help="调试模式")
@click.pass_context
def adjust(ctx: click.Context, route_id: str, instruction: str, debug: bool) -> None:
    """对话调整路线"""
    global _DEBUG
    if debug:
        _DEBUG = True
    result = asyncio.run(_dialogue_adjust(route_id, instruction))
    if "error" in result:
        console.print(f"[red]{result['error']}[/]")
        return

    reply = result.get("reply", "")
    if reply:
        console.print(f"[green]{reply}[/]")

    new_route = result.get("route", {})
    if new_route and new_route.get("route"):
        _display_steps(new_route.get("route", []))


@cli.command()
@click.argument("route_id")
def route(route_id: str) -> None:
    """查看已缓存的路线"""
    async def _fetch():
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_BASE}/api/route/{route_id}")
            return resp
    resp = asyncio.run(_fetch())
    if resp.status_code != 200:
        console.print(f"[red]无法获取路线 ({resp.status_code})[/]")
        return
    data = resp.json()
    route_data = data.get("route", [])
    _display_steps(route_data)


@cli.command()
@click.option("--debug", is_flag=True, help="调试模式")
@click.pass_context
def interactive(ctx: click.Context, debug: bool) -> None:
    """交互模式"""
    global _DEBUG
    if debug:
        _DEBUG = True
    _interactive_session()


# ══════════════════════════════════════════════════════════════════
#  结果显示
# ══════════════════════════════════════════════════════════════════

def _display_result(result: dict) -> None:
    """展示完整的规划结果。"""
    if _DEBUG:
        console.print()
        console.print(Rule("[bold green]✔ 规划完成[/]"))

    # 意图解析结果
    done = result.get("done", {})
    full = done.get("full_route", {})
    intent = full.get("user_intent", {})

    if intent:
        pid = intent.get("matched_profile_id", "?")
        group = intent.get("group", {})
        budget = intent.get("budget", {})
        pace = intent.get("pace", "")
        constraints = intent.get("hard_constraints", [])

        t = Text()
        t.append(f"画像: [bold #e94560]{pid}[/]", style="cyan")
        t.append(f"  群体: {group.get('type', '?')}×{group.get('size', '?')}")
        t.append(f"  预算: ¥{budget.get('per_person', '?')}")
        t.append(f"  节奏: {pace}")
        t.append(f"\n  时间: {intent.get('time', {}).get('period', '?')}")
        prefs = intent.get("preferences", {})
        if prefs:
            pref_str = " ".join(f"{k}:{v}" for k, v in sorted(prefs.items(), key=lambda x: -x[1]))
            t.append(f"\n  偏好: {pref_str}")
        if constraints:
            t.append(f"\n  约束: {', '.join(constraints)}")

        # 偏好来源
        source = intent.get("preferences_source", {})
        if source:
            src_str = " ".join(
                f"{k}={{{'user':'✅','ltm':'📚','profile':'🤖'}.get(v.split('_')[0],'❓')}}"
                for k, v in sorted(source.items())
            )
            t.append(f"\n  来源: {src_str}")

        emotion_need = intent.get("emotion_need")
        if emotion_need:
            t.append(f"\n  情感需求: {emotion_need}")

        llm_used = intent.get("_llm_used", False)
        llm_err = intent.get("_llm_error", "")
        if llm_used:
            t.append(f"\n  LLM: ✅ 成功")
        elif llm_err:
            t.append(f"\n  LLM: ❌ {llm_err}")
        else:
            t.append(f"\n  LLM: 规则匹配")

        console.print(Panel(t, title="🔍 意图解析", box=box.ROUNDED))

    # POI 路线
    steps = result.get("steps", [])
    _display_steps(steps)

    # 情绪曲线
    if full and full.get("emotion_curve"):
        console.print(_render_emotion_chart(full["emotion_curve"]))

    # 权重可视化（调试模式）
    if _DEBUG:
        weights_info = result.get("done", {}).get("full_route", {}).get("user_intent", {}).get("_dynamic_weights", {})
        if weights_info:
            console.print(_render_weights_chart(weights_info))

    # 预算
    budget_info = result.get("budget", {})
    if budget_info or steps:
        total = sum(s.get("poi", {}).get("avg_price") or 0 for s in steps)
        t = Text()
        t.append(f"总预算: [bold #f39c12]¥{total}[/]")
        t.append(f"  |  地点: [green]{len(steps)}个[/]")
        if steps:
            first = steps[0].get("arrival_time", "")
            last = steps[-1].get("arrival_time", "")
            if first and last:
                t.append(f"  |  时段: [cyan]{first}-{last}[/]")
        console.print(Panel(t, title="💰 预算", box=box.ROUNDED))

    # 异常提示
    anomalies = result.get("anomalies", [])
    for anom in anomalies:
        sev = anom.get("severity", "warning")
        color = "red" if sev == "error" else "yellow"
        console.print(Panel(
            f"[{color}]⚠ {anom.get('message', '')}[/]",
            box=box.ROUNDED,
            border_style=color,
        ))

    # 调整建议
    adj = result.get("adjustment", {})
    if adj:
        suggestions = adj.get("suggestions", [])
        if suggestions:
            p = Panel(
                "\n".join(f" • {s}" for s in suggestions),
                title="💡 调整建议",
                box=box.ROUNDED,
                border_style="blue",
            )
            console.print(p)

    # 记忆保存
    mem = result.get("memory_saved", {})
    if mem:
        console.print(f"\n[dim]💾 {mem.get('message', '已记住偏好')}[/]")


def _display_steps(steps: list[dict]) -> None:
    """展示POI步骤列表。"""
    if not steps:
        return

    t = Text()
    for i, step in enumerate(steps, 1):
        poi = step.get("poi", {})
        name = poi.get("name", "—")
        cat = poi.get("category", "")
        price = poi.get("avg_price")
        arrival = step.get("arrival_time", "")
        narrative = step.get("narrative", "") or ""
        emotion_design = step.get("emotion_design", "")

        # 行1: 序号 + 名称 + 时间 + 分类 + 价格
        t.append(f"\n  {i}. ", style="bold #e94560")
        t.append(name, style="bold white")
        if arrival:
            t.append(f"  {arrival}", style="cyan")
        if cat:
            t.append(f"  [{cat}]", style="dim")
        if price:
            t.append(f"  ¥{price}", style="#f39c12")
        else:
            t.append("  免费", style="green")

        # 心理学规则标记
        psy_note = step.get("psychology_note", "")
        if psy_note and _DEBUG:
            t.append(f"  [dim]({psy_note})[/]")
        # 场景标签（调试模式）
        scene_tags = step.get("scene_tags", [])
        if scene_tags and _DEBUG:
            t.append(f"\n     🏷️ ", style="dim")
            for tag in scene_tags:
                t.append(f"[{tag}]", style="dim #888888")

        t.append("\n")

        # 行2: 情绪设计
        if emotion_design:
            t.append(f"     🎨 ", style="#9b59b6")
            t.append(emotion_design, style="italic #9b59b6")
            t.append("\n")

        # 行3: 叙事
        if narrative:
            t.append(f"     {narrative}\n", style="dim #aaaaaa")

    console.print(Panel(t, title="📍 路线规划", box=box.ROUNDED))


# ══════════════════════════════════════════════════════════════════
#  用户身份辅助
# ══════════════════════════════════════════════════════════════════

def _load_user_config() -> dict:
    try:
        _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg_file = _USER_CONFIG_DIR / "user.json"
        if cfg_file.exists():
            return json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


# ══════════════════════════════════════════════════════════════════
#  交互模式
# ══════════════════════════════════════════════════════════════════

def _interactive_session() -> None:
    """交互式 CLI 会话。"""
    config = _load_user_config()
    user_id = config.get("last_user_id", "")
    context = {}
    context_info = ""

    # 采集上下文
    try:
        import asyncio
        async def _get_ctx():
            from backend.services.holiday_utils import build_context
            from backend.services.perception import PerceptionService
            perception = PerceptionService()
            pctx = await perception.get_context()
            ctx = build_context(
                weather=pctx.weather, temperature=pctx.temperature,
                hour_of_day=pctx.hour_of_day, day_of_week=pctx.day_of_week,
                season=pctx.season,
            )
            return ctx, (
                f"{pctx.weather} {pctx.temperature}°C · "
                f"周{'日一二三四五六'[pctx.day_of_week]} · {pctx.season}"
            )
        loop = asyncio.new_event_loop()
        context, context_info = loop.run_until_complete(_get_ctx())
        loop.close()
    except Exception:
        context = {}
        context_info = "本地"

    # 欢迎
    console.clear()
    hour = datetime.now().hour
    greeting = "上午好" if 5 <= hour < 12 else "下午好" if 12 <= hour < 18 else "晚上好"
    t = Text()
    t.append(f"\n🌿 [bold #e94560]CityFlow[/] —— {greeting}", style="white")
    if user_id and user_id != "default_user":
        t.append(f"[bold] {user_id}[/]！\n", style="white")
    else:
        t.append("！\n", style="white")
    if context_info:
        t.append(f"\n今日: [cyan]{context_info}[/]\n")
    t.append(f"\n[dim]输入出行需求开始规划 | {'--debug 模式' if _DEBUG else '加 --debug 看详细处理'} | q 退出[/]")
    console.print(Panel(t, box=box.ROUNDED, border_style="#e94560"))

    current_route_id: str | None = None

    while True:
        console.print()
        text = console.input("[bold cyan]╰─[/] ").strip()

        if text.lower() in ("q", "quit", "exit"):
            break

        if not text:
            continue

        is_adjust = current_route_id is not None and (
            text.startswith("换") or any(kw in text for kw in ["赶", "累", "贵", "早", "晚", "太", "重来"])
        )

        if is_adjust:
            if _DEBUG:
                console.print()
                console.print(Rule("[bold cyan]💬 对话调整[/]"))

            result = asyncio.run(_dialogue_adjust(current_route_id, text))
            if "error" in result:
                console.print(f"[red]{result['error']}[/]")
            else:
                reply = result.get("reply", "")
                if reply:
                    console.print(f"\n[green]💬 {reply}[/]")
                new_route = result.get("route", {})
                if new_route and new_route.get("route"):
                    steps = new_route.get("route", [])
                    _display_steps(steps)
        else:
            # 规划
            console.print()
            result = asyncio.run(_plan_route_stream(text, user_id, context))
            if "error" in result:
                console.print(f"[red]✘ {result['error']}[/]")
            else:
                current_route_id = result.get("done", {}).get("route_id")
                _display_result(result)
                if current_route_id:
                    console.print(f"\n[dim]输入调整指令: 换掉第2个 / 太赶了 / 太贵了 / 早一点…[/]")


if __name__ == "__main__":
    cli()
