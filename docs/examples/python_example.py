# CityFlow API Python 示例
# 依赖: pip install httpx

import httpx
import asyncio
import json


BASE_URL = "http://localhost:8000"


async def plan_route(user_input: str):
    """规划路线 - 流式SSE响应"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/plan",
            json={"user_input": user_input},
            timeout=60,
        )

        # 解析SSE响应
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                event_type = data.get("type", "unknown")
                print(f"[{event_type}] {data}")


async def search_pois(region: str, category: str = None):
    """搜索POI"""
    async with httpx.AsyncClient() as client:
        body = {"region": region}
        if category:
            body["categories"] = [category]

        response = await client.post(
            f"{BASE_URL}/api/poi/search",
            json=body,
        )

        data = response.json()
        pois = data.get("pois", [])
        print(f"找到 {len(pois)} 个POI:")
        for poi in pois:
            print(f"  - {poi['name']} ({poi.get('category', '')})")
        return pois


async def get_poi_detail(poi_id: str):
    """获取POI详情"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/poi/detail/{poi_id}")
        data = response.json()
        print(f"POI详情: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return data


async def calculate_distance(poi_ids: list[str]):
    """计算距离矩阵"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/poi/distance-matrix",
            json={"poi_ids": poi_ids},
        )
        data = response.json()
        print(f"距离矩阵: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return data


async def adjust_route(route_id: str, instruction: str):
    """调整路线 - 对话式交互"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/dialogue/{route_id}",
            json={"instruction": instruction},
        )
        data = response.json()
        print(f"调整结果: {data.get('reply', '')}")
        return data


# 使用示例
if __name__ == "__main__":
    # 1. 规划路线
    print("=== 规划路线 ===")
    asyncio.run(plan_route("周末想一个人安静走走"))

    # 2. 搜索POI
    print("\n=== 搜索POI ===")
    asyncio.run(search_pois("珠海", "文化"))

    # 3. 调整路线 (需要有效的route_id)
    # asyncio.run(adjust_route("your-route-id", "太赶了，想轻松点"))
