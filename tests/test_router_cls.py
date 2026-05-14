"""单点测试 expert_router 分类准确性。"""

import asyncio
import json
import os

from dotenv import load_dotenv
load_dotenv()

os.environ.setdefault("LLM_MODEL", "deepseek-chat")

from backend.agents_v3.nodes.expert_router import expert_router

# 30个测试场景 (user_input → 期望scene_type)
SCENARIOS = [
    ("和女朋友珠海约会，想找有氛围的地方", "观光型"),
    ("情侣珠海一日游，预算500元，喜欢拍照打卡", "观光型"),
    ("异地恋终于见面了，珠海玩一天，想海边散步吃好吃的", "观光型"),
    ("纪念日带对象去珠海，预算800，要浪漫", "观光型"),
    ("4个人珠海玩一天，每人预算100", "观光型"),
    ("带6岁孩子去长隆海洋王国", "目的地型"),
    ("珠海亲子游，孩子喜欢动物和科学", "观光型"),
    ("带娃珠海半日游，上午搞定", "观光型"),
    ("一家四口珠海，两岁和八岁，预算600", "观光型"),
    ("带爸妈珠海一日游，不能太累", "休闲型"),
    ("5个朋友珠海聚餐，吃吃喝喝", "美食型"),
    ("兄弟几个珠海特种兵一天，打卡所有景点", "特种兵型"),
    ("和闺蜜珠海逛街，想拍照+吃甜品", "观光型"),  # ← 逛街为主
    ("4个大学生珠海穷游，不花钱", "观光型"),
    ("公司团建珠海，20人，预算每人200", "观光型"),
    ("社恐一个人珠海，安静地方", "休闲型"),
    ("珠海摄影出片，日落夜景", "观光型"),
    ("凌晨珠海，吃宵夜", "美食型"),
    ("珠海早起晨跑", "休闲型"),
    ("一个人珠海文艺独处，咖啡馆书店", "休闲型"),
    ("珠海吃海鲜，想吃最新鲜最划算的", "美食型"),
    ("珠海美食一日游，想吃海鲜和本地特色", "美食型"),
    ("珠海小吃扫街，一路吃过去", "美食型"),
    ("珠海茶餐厅打卡", "美食型"),
    ("4个人珠海吃垮，每人预算50", "美食型"),
    ("退休老两口珠海慢游，公园喝茶", "休闲型"),
    ("下雨天珠海，室内活动", "观光型"),
    ("带狗珠海，宠物友好", "观光型"),
    ("珠海极限省钱，不花一分钱", "观光型"),
    ("珠海有啥好玩的", "观光型"),
]


async def main():
    correct = 0
    total = len(SCENARIOS)
    errors = []

    for i, (user_input, expected) in enumerate(SCENARIOS, 1):
        state = {
            "user_input": user_input,
            "user_intent": {},
            "candidates": [],
        }
        result = await expert_router(state)
        actual = result.get("scene_type", "?")
        weights = result.get("expert_weights", {})
        active = result.get("active_experts", [])

        ok = actual == expected
        mark = "✅" if ok else "❌"
        if ok:
            correct += 1
        else:
            errors.append((i, user_input[:15], expected, actual))

        # 简短打印
        top_w = {k: round(v, 2) for k, v in sorted(weights.items(), key=lambda x: -x[1])[:4]}
        print(f"{mark} [{i:02d}] {actual}(expect={expected}) | {top_w} | {user_input[:25]}")

    print(f"\n准确率: {correct}/{total} ({correct/total*100:.0f}%)")
    if errors:
        print(f"\n错误场景:")
        for i, inp, exp, act in errors:
            print(f"  [{i:02d}] '{inp}...' → got={act}, expect={exp}")


if __name__ == "__main__":
    asyncio.run(main())
