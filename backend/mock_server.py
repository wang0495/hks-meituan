"""CityFlow Mock Server — 模拟 MoE 全流程 SSE，省 token。

启动: python backend/mock_server.py
端口: 8001
"""

import asyncio
import json
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="CityFlow Mock Server")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ── CSP + CORS headers on every response ──
@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "*"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return resp


# ── Explicit OPTIONS handler (catches all preflight) ──
@app.options("/api/plan")
async def options_plan():
    return Response(status_code=204)

@app.options("/api/dialogue/{route_id}")
async def options_dialogue(route_id: str):
    return Response(status_code=204)


# ── Mock Data ──

MOCK_POIS = [
    {"id": "m1", "name": "凤凰山森林公园步道", "category": "景点", "rating": 4.6, "avg_price": 0, "city": "珠海", "tags": ["自然风光", "运动健身", "拍照出片"], "avg_stay_min": 150, "lat": 22.28, "lng": 113.55, "business_hours": "06:00-18:00", "experience_leverage": "high", "spend_emotion": "物超所值"},
    {"id": "m2", "name": "金鼎湿地公园", "category": "景点", "rating": 4.6, "avg_price": 0, "city": "珠海", "tags": ["自然风光", "公园", "休闲放松"], "avg_stay_min": 90, "lat": 22.36, "lng": 113.46, "business_hours": "全天开放", "experience_leverage": "high", "spend_emotion": "物超所值"},
    {"id": "m3", "name": "横琴花海长廊", "category": "景点", "rating": 4.7, "avg_price": 0, "city": "珠海", "tags": ["自然风光", "拍照出片", "休闲放松"], "avg_stay_min": 90, "lat": 22.14, "lng": 113.56, "business_hours": "全天开放", "experience_leverage": "high", "spend_emotion": "物超所值"},
    {"id": "m4", "name": "旧物仓·珠海仓", "category": "文创", "rating": 4.5, "avg_price": 28, "city": "珠海", "tags": ["文艺", "拍照出片", "怀旧"], "avg_stay_min": 75, "lat": 22.27, "lng": 113.54, "business_hours": "10:00-20:00", "experience_leverage": "high", "spend_emotion": "惊喜"},
    {"id": "m5", "name": "华发商都·咖啡街", "category": "餐饮", "rating": 4.4, "avg_price": 35, "city": "珠海", "tags": ["咖啡", "休闲放松", "约会"], "avg_stay_min": 50, "lat": 22.25, "lng": 113.53, "business_hours": "10:00-22:00", "experience_leverage": "medium", "spend_emotion": "舒适"},
]

NARRATIVES = [
    "清晨六点，山间薄雾还未散尽。你独自踏上石阶，露水打湿鞋尖，空气里弥漫着泥土和松脂的气味。转过第五道弯，阳光穿透树冠，在苔藓上投下金色光斑——这一刻，整座山仿佛只属于你一个人。",
    "午后阳光穿过红树林叶隙，在木栈道上洒下碎金般的影子。潮水刚刚退去，滩涂上的弹涂鱼慌忙钻进泥洞，留下一串细密的水纹。你靠在栏杆上，远处有白鹭掠过水面，世界安静得只剩下风声。",
    "簕杜鹃从廊架垂落成一片流动的紫色瀑布，风过时花瓣纷纷扬扬沾上衣领。你沿着花廊慢慢走，脚下是细碎的落英，头顶是无尽的繁花。走到尽头回望，那条花路像是只为今日而开。",
    "推开铁锈斑驳的仓库大门，旧风扇、铁皮信箱、褪色搪瓷缸静静陈列在暖黄灯光下。每一件老物件都在低声讲述被遗忘的故事——那个年代的慢时光，透过玻璃天窗洒下来的光柱里，灰尘在跳舞。",
    "拿铁拉花像一朵小云沉在杯底，爵士乐从黑胶唱片机里流淌出来，和咖啡豆的焦香搅在一起。你窝在天鹅绒沙发里，窗外车水马龙，窗内时间慢了半拍。这杯咖啡，值得花一整个下午。",
]

AGENTS = [
    {"id": "intent_parser", "name": "意图解析", "icon": "🧠", "role": "需求理解", "color": "#ff5368",
     "thinking": ["读取自然语言输入...", "提取关键词: 独处、安静、自然", "匹配画像 P1(社恐独居) 87%", "生成需求向量: nature=0.8"],
     "result": "意图已解析 → 独处·自然·闲逛型"},
    {"id": "poi_expert", "name": "POI 专家", "icon": "🏛", "role": "景点筛选", "color": "#51aef9",
     "thinking": ["加载 2000+ POI...", "过滤城市+排除酒店", "自然风光 TOP10", "排除排队热门 → 6个"],
     "result": "筛选出 6 个高匹配景点"},
    {"id": "food_expert", "name": "美食专家", "icon": "🍜", "role": "餐饮推荐", "color": "#ff9b54",
     "thinking": ["分析用餐时段: 下午茶", "偏好: 咖啡/轻食", "5子类各取TOP3"],
     "result": "推荐 3 家特色咖啡"},
    {"id": "local_expert", "name": "本地向导", "icon": "🗺", "role": "隐藏宝藏", "color": "#7edc95",
     "thinking": ["搜索非热门高评地点", "发现旧物仓·珠海仓 4.5★", "匹配独处场景 ✓"],
     "result": "挖掘到 1 个隐藏宝藏"},
    {"id": "budget_hacker", "name": "预算专家", "icon": "💰", "role": "性价比", "color": "#925cff",
     "thinking": ["总预算 ¥200 弹性", "免费景点 3/4", "体验杠杆优化"],
     "result": "总花费 ¥63, 节省 ¥137"},
    {"id": "synthesizer", "name": "综合师", "icon": "✨", "role": "路线组装", "color": "#ff5a88",
     "thinking": ["收集5个专家提案", "地理聚类: 北→中→南", "时间窗校验 ✓", "情绪节奏: 安静→沉浸→惊喜→收尾", "总行程 ~7h"],
     "result": "组装完成: 5站最优路线"},
]


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/plan")
async def mock_plan(req: Request):
    body = await req.json()

    async def stream():
        yield sse("phase", {"phase": "parsing", "message": "正在理解你的需求..."})
        await asyncio.sleep(0.6)
        yield sse("debug_llm", {"used": True, "method": "llm", "model": "mock"})
        yield sse("debug_profile", {"top3": [{"id": "P1", "score": 14.7, "name": "社恐独居"}], "selected": "P1"})

        yield sse("phase", {"phase": "searching", "message": "筛选候选 POI..."})
        await asyncio.sleep(0.5)

        yield sse("phase", {"phase": "agents", "message": "MoE 智能体启动..."})
        await asyncio.sleep(0.3)

        # Agents interleaved
        queues = {a["id"]: list(a["thinking"]) for a in AGENTS}
        finished = set()
        while len(finished) < len(AGENTS):
            for a in AGENTS:
                aid = a["id"]
                if aid in finished:
                    continue
                q = queues[aid]
                if q:
                    yield sse("agent_start", {"agent": aid, "name": a["name"], "icon": a["icon"], "role": a["role"], "color": a["color"]})
                    yield sse("agent_thinking", {"agent": aid, "text": q.pop(0)})
                    await asyncio.sleep(0.35 + hash(aid) % 3 * 0.15)
                else:
                    yield sse("agent_result", {"agent": aid, "summary": a["result"]})
                    finished.add(aid)
                    await asyncio.sleep(0.2)

        yield sse("debug_agents", {"version": "Mock", "agent_count": len(AGENTS), "agents": [a["id"] for a in AGENTS]})
        await asyncio.sleep(0.3)

        yield sse("phase", {"phase": "narrating", "message": "逐站生成叙述..."})
        cur_hour = 9
        cur_min = 0
        for i, poi in enumerate(MOCK_POIS):
            if i > 0:
                travel_min = 15 + i * 8
                cur_min += travel_min
                cur_hour += cur_min // 60
                cur_min = cur_min % 60
            at = f"{cur_hour:02d}:{cur_min:02d}"
            stay = poi["avg_stay_min"]
            cur_min += stay
            cur_hour += cur_min // 60
            cur_min = cur_min % 60
            dt = f"{cur_hour:02d}:{cur_min:02d}"
            travel = {"distance_m": 3000 + i * 1500, "time_min": 15 + i * 8, "method": ["步行", "公交", "骑行", "打车"][i % 4]} if i > 0 else None
            yield sse("step", {"index": i + 1, "poi": {**poi, "emotion_tags": {"primary": "平静", "intensity": 0.7}, "_scene_tags": [], "queue_prone": i == 2, "constraints": {"time_window": True, "budget_ok": True}}, "arrival_time": at, "departure_time": dt, "narrative": NARRATIVES[i], "emotion_design": ["宁静", "沉浸", "惊喜", "怀旧", "舒适"][i], "scene_tags": [], "travel_from_prev": travel})
            await asyncio.sleep(0.5)

        rid = uuid.uuid4().hex[:8]
        total = sum(p["avg_price"] for p in MOCK_POIS)
        yield sse("done", {"route_id": rid, "version": "C-Mock", "full_route": {"route": [{"poi": {**p, "emotion_tags": {}, "_scene_tags": [], "queue_prone": False, "constraints": {}}, "arrival_time": f"{9+i*2:02d}:{'00' if i%2==0 else '30'}", "departure_time": f"{10+i*2:02d}:{'15' if i%2==0 else '45'}", "narrative": NARRATIVES[i], "emotion_design": "体验", "scene_tags": p.get("tags", [])[:2], "travel_from_prev": {"distance_m": 3000+i*1500, "time_min": 15+i*8} if i > 0 else None} for i, p in enumerate(MOCK_POIS)], "total_cost": {"time_min": 420, "budget_used": total}, "emotion_curve": []}})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/dialogue/{route_id}")
async def mock_dialogue(route_id: str, req: Request):
    body = await req.json()
    await asyncio.sleep(0.3)
    return {"reply": f"已根据「{body.get('instruction', '')}」调整路线 (mock)", "route": None}


# ── 静态文件 (必须在 API 路由之后) ──
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.mock_server:app", host="0.0.0.0", port=8001, reload=True)
