"""评估器方差测试：同一篇路线跑N次eval，看分数波动。

用于判断evaluator是否稳定、是否压分。

用法:
    python tests/test_eval_variance.py

输出:
    - 每个维度的 min/max/avg/std
    - 方差分析：是否超过可接受范围(±0.5)
    - "压分"检测：是否有维度系统性偏低
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_KEY = os.getenv("LLM_API_KEY", "")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
N_RUNS = 5

# 样本路线（从test_c_version_20260515_215604.json提取的真实路线）
SAMPLE_ROUTES = [
    {
        "name": "情侣珠海一日游",
        "input": "情侣珠海一日游，预算500元，喜欢拍照打卡",
        "route": """1. 珠海渔女 [文化] ¥0 到达:09:30 标签:['地标', '文化', '拍照']
2. 情侣路 [运动] ¥0 到达:10:15 标签:['海滨', '浪漫']
3. 情侣中路骑行道 [运动] ¥0 到达:10:45 标签:['骑行', '运动']
4. 湾仔海鲜街 [餐饮] ¥120 到达:12:00 标签:['海鲜', '本地']
5. 日月贝（珠海大剧院） [文化] ¥0 到达:14:00 标签:['地标', '建筑']
6. 金悅軒酒家 [餐饮] ¥85 到达:17:30 标签:['粤菜', '茶餐厅']
7. 野狸岛公园骑行道 [运动] ¥0 到达:19:00 标签:['骑行', '夜景']""",
    },
    {
        "name": "美食探索",
        "input": "珠海美食一日游，想吃海鲜和本地特色",
        "route": """1. 台灣帝鈞炭烤胡椒餅 [餐饮] ¥15 到达:09:30 标签:['小吃', '台湾']
2. 湾仔海鲜街 [餐饮] ¥120 到达:11:00 标签:['海鲜', '本地']
3. 情侣路 [运动] ¥0 到达:13:30 标签:['海滨', '散步']
4. 金悅軒酒家 [餐饮] ¥85 到达:15:00 标签:['粤菜', '茶餐厅']
5. 多记甜品 [餐饮] ¥30 到达:17:00 标签:['甜品', '港式']""",
    },
    {
        "name": "亲子海洋王国",
        "input": "带6岁孩子去长隆海洋王国，预算1000元",
        "route": """1. 长隆海洋王国 [景点] ¥395 到达:09:00 标签:['海洋', '亲子', '主题公园']
2. 肯德基 KFC [餐饮] ¥45 到达:12:30 标签:['快餐', '亲子']
3. 珠海横琴科学城儿童科技馆 [文化] ¥50 到达:14:00 标签:['科技', '亲子', '教育']
4. 珠海横琴国家湿地公园 [景点] ¥0 到达:16:00 标签:['自然', '湿地', '亲子']""",
    },
]

# 评分prompt（与test_c_version.py一致）
SCORE_PROMPT = """你是旅游路线质量评审。请客观公正地评估以下路线。

## 第一步：识别场景类型

先判断这个需求属于哪种场景（5选1）：
- **美食型**：用户核心目的是吃喝探索（"美食一日游""想吃海鲜"）
- **目的地型**：用户指定了具体大景区（"长隆海洋王国""圆明新园"）
- **特种兵型**：用户要求密集打卡
- **休闲型**：节奏慢、少景点、重体验
- **观光型**：常规观光游览（默认）

## 第二步：按场景类型调整评分标准

评分标准(每项0-10分):

**intent_match** (意图匹配):
- 美食型：路线以餐饮为主就是好匹配
- 目的地型：包含核心目的地就给7-9
- 特种兵型：覆盖重要景点就给7-8
- 休闲型：景点少不代表匹配差
- 观光型：9-10:完美 | 7-8:大部分 | 5-6:部分 | 3-4:低 | 0-2:不相关

**poi_quality** (POI质量):
- 按POI本身质量评分，不因数量少而扣分
- 9-10:都值得专程去 | 7-8:大部分不错 | 5-6:一般 | 3-4:偏低 | 0-2:不值得

**geo_continuity** (地理合理性):
- 美食型：餐厅可以分散但不折返
- 目的地型：集中在同一区域给8-9
- 特种兵型：跨区域赶场是正常的
- 观光型：9-10:流畅 | 7-8:合理 | 5-6:绕路 | 3-4:不合理 | 0-2:混乱

**scene_diversity** (场景多样性):
- 美食型：只看餐饮内部多样性
- 目的地型：给7-8
- 休闲型：1-2种大类就够
- 观光型：9-10:4种以上 | 7-8:3种 | 5-6:1-2种 | 3-4:单一 | 0-2:没有

**overall** (总体): 综合满意度评分。

## 评分底线
1. 3个以上POI且时间合理 → geo ≥ 6
2. 包含核心需求 → intent ≥ 7
3. 没有明显错误 → overall ≥ 6
4. 不要因为"还可以更好"就给低分
5. 列出2-3个优点和2-3个建议

"""


async def eval_once(user_input: str, route_text: str) -> dict | None:
    """单次eval。"""
    prompt = SCORE_PROMPT + f"""用户需求: {user_input}

路线:
{route_text}

输出JSON: {{"scene_type":"...","scores":{{"intent_match":N,"poi_quality":N,"geo_continuity":N,"scene_diversity":N,"overall":N}},"good_points":["..."],"bad_points":["..."]}}"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": MODEL,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            if r.status_code != 200:
                return None
            text = r.json()["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())

            if "scores" in data:
                scores = data["scores"]
            else:
                keys = {"intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"}
                scores = {k: data[k] for k in keys if k in data}

            return scores
    except Exception:
        return None


async def main():
    print("=" * 70)
    print(f"评估器方差测试 — 每条路线跑{N_RUNS}次eval")
    print(f"模型: {MODEL} | temperature: 0.1")
    print("=" * 70)

    all_variance_data = {}

    for sample in SAMPLE_ROUTES:
        print(f"\n场景: {sample['name']}")
        print(f"需求: {sample['input']}")
        print(f"路线: {len(sample['route'].splitlines())}站")
        print(f"{'─' * 70}")

        results = []
        for run in range(N_RUNS):
            scores = await eval_once(sample["input"], sample["route"])
            if scores:
                results.append(scores)
                dims = " ".join(f"{k}={v}" for k, v in scores.items())
                print(f"  Run {run + 1}: {dims}")
            else:
                print(f"  Run {run + 1}: 失败")
            await asyncio.sleep(1)

        if not results:
            print("  ⚠ 全部失败")
            continue

        # 统计分析
        dims = ["intent_match", "poi_quality", "geo_continuity", "scene_diversity", "overall"]
        print(f"\n  {'维度':<20} {'min':>4} {'max':>4} {'avg':>5} {'std':>5} {'range':>6} {'判断'}")
        print(f"  {'─' * 65}")

        variance_data = {}
        for dim in dims:
            vals = [r.get(dim, 0) for r in results if dim in r]
            if not vals:
                continue
            mn = min(vals)
            mx = max(vals)
            avg = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0
            rng = mx - mn

            if rng <= 1:
                judge = "✅ 稳定"
            elif rng <= 2:
                judge = "⚠ 中等波动"
            else:
                judge = "❌ 波动大"

            print(f"  {dim:<20} {mn:>4} {mx:>4} {avg:>5.1f} {std:>5.2f} {rng:>6} {judge}")
            variance_data[dim] = {"min": mn, "max": mx, "avg": avg, "std": std, "range": rng, "values": vals}

        all_variance_data[sample["name"]] = variance_data

        # 压分检测
        print(f"\n  压分检测:")
        for dim in dims:
            avg = variance_data.get(dim, {}).get("avg", 0)
            if avg < 6:
                print(f"  ⚠ {dim}: avg={avg:.1f} — 可能被压分")
            elif avg < 6.5:
                print(f"  🔍 {dim}: avg={avg:.1f} — 接近及格线")
            else:
                print(f"  ✅ {dim}: avg={avg:.1f} — 正常")

    # 总结
    print(f"\n{'=' * 70}")
    print("总结")
    print(f"{'=' * 70}")

    # 跨场景平均方差
    all_ranges = {}
    for name, dims in all_variance_data.items():
        for dim, data in dims.items():
            if dim not in all_ranges:
                all_ranges[dim] = []
            all_ranges[dim].append(data["range"])

    print(f"\n  维度间平均波动(range):")
    for dim, ranges in all_ranges.items():
        avg_range = statistics.mean(ranges)
        status = "✅" if avg_range <= 1 else "⚠" if avg_range <= 2 else "❌"
        print(f"  {status} {dim}: avg_range={avg_range:.1f}")

    print(f"\n  结论:")
    max_avg_range = max(statistics.mean(r) for r in all_ranges.values())
    if max_avg_range <= 1:
        print("  ✅ 评估器稳定，方差在可接受范围内")
    elif max_avg_range <= 2:
        print("  ⚠ 评估器存在中等方差(±1分)，建议多次eval取平均")
    else:
        print("  ❌ 评估器方差大(±2分)，单次eval不可靠，必须多次取平均")

    # 保存
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    out = {"timestamp": ts, "n_runs": N_RUNS, "variance_data": all_variance_data}
    out_path = f"docs/logs/eval_variance_{ts}.json"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  结果已保存到 {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
