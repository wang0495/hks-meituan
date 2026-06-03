"""Live Itinerary：动态行程 + 置信度热力图 + 决策溯源。"""

from __future__ import annotations


def build_heatmap(proposals: list[dict], conflicts: list[dict]) -> dict:
    """构建置信度热力图。

    green: >0.8 多方验证
    yellow: 0.5-0.8 有备选/风险
    red: <0.5 需用户决策
    """
    heatmap = {}
    conflict_agents = set()
    for c in conflicts:
        for a in c.get("agents", []):
            conflict_agents.add(a)

    for p in proposals:
        pid = p.get("proposal_id", "")
        confidence = p.get("confidence", 0.5)
        agent = p.get("agent", "")

        # 有冲突降低置信度
        if agent in conflict_agents:
            confidence *= 0.7

        if confidence > 0.8:
            color = "green"
        elif confidence > 0.5:
            color = "yellow"
        else:
            color = "red"

        heatmap[pid] = {
            "confidence": round(confidence, 2),
            "color": color,
            "agent": agent,
            "name": p.get("content", {}).get("name", ""),
            "risk_factors": [c["description"] for c in conflicts if agent in c.get("agents", [])],
        }

    return heatmap


def build_decision_trace(proposals: list[dict]) -> dict:
    """构建决策溯源：每个提案为什么被选中。"""
    trace = {}
    for p in proposals:
        pid = p.get("proposal_id", "")
        trace[pid] = {
            "why": p.get("reasoning", ""),
            "agent": p.get("agent", ""),
            "confidence": p.get("confidence", 0),
            "name": p.get("content", {}).get("name", ""),
        }
    return trace


def heatmap_summary(heatmap: dict) -> dict:
    """热力图摘要。"""
    green = sum(1 for h in heatmap.values() if h.get("color") == "green")
    yellow = sum(1 for h in heatmap.values() if h.get("color") == "yellow")
    red = sum(1 for h in heatmap.values() if h.get("color") == "red")
    total = len(heatmap)
    return {
        "total": total,
        "green": green,
        "yellow": yellow,
        "red": red,
        "score": (green + yellow * 0.6 + red * 0.2) / total if total > 0 else 0,
    }
