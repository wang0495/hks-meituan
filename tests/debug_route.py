import sys, json
sys.path.insert(0, '.')
from backend.services.solver import solve_route

# Full 13 POI pool from test
poi_pool = [
    {"id": "poi_001", "name": "安静图书馆", "category": "文化", "rating": 4.5, "avg_price": 0, "lat": 22.270, "lng": 113.580, "business_hours": "08:00-21:00", "tags": ["免费", "安静", "学习"], "queue_prone": False, "avg_stay_min": 120, "emotion_tags": {"excitement": 0.1, "tranquility": 0.95, "sociability": 0.1, "culture_depth": 0.9, "surprise": 0.05, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0, "opening_hours": "08:00-21:00", "has_restroom": True}},
    {"id": "poi_002", "name": "刺激过山车", "category": "娱乐", "rating": 4.8, "avg_price": 150, "lat": 22.280, "lng": 113.590, "business_hours": "08:00-22:00", "tags": ["刺激", "排队", "年轻人"], "queue_prone": True, "avg_stay_min": 30, "emotion_tags": {"excitement": 0.95, "tranquility": 0.05, "sociability": 0.6, "culture_depth": 0.1, "surprise": 0.8, "physical_demand": 0.7}, "constraints": {"accessible": False, "pet_friendly": False, "queue_time_min": 45, "opening_hours": "08:00-22:00", "has_restroom": True}},
    {"id": "poi_003", "name": "浪漫咖啡厅", "category": "美食", "rating": 4.6, "avg_price": 68, "lat": 22.265, "lng": 113.575, "business_hours": "08:00-23:00", "tags": ["浪漫", "约会", "咖啡"], "queue_prone": False, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.3, "tranquility": 0.7, "sociability": 0.5, "culture_depth": 0.4, "surprise": 0.2, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0, "opening_hours": "08:00-23:00", "has_restroom": True}},
    {"id": "poi_004", "name": "城市运动公园", "category": "运动", "rating": 4.3, "avg_price": 0, "lat": 22.275, "lng": 113.585, "business_hours": "06:00-22:00", "tags": ["运动", "跑步", "免费"], "queue_prone": False, "avg_stay_min": 60, "emotion_tags": {"excitement": 0.6, "tranquility": 0.3, "sociability": 0.4, "culture_depth": 0.1, "surprise": 0.3, "physical_demand": 0.8}, "constraints": {"accessible": True, "pet_friendly": True, "queue_time_min": 0, "opening_hours": "06:00-22:00", "has_restroom": True}},
    {"id": "poi_005", "name": "历史博物馆", "category": "文化", "rating": 4.7, "avg_price": 30, "lat": 22.262, "lng": 113.572, "business_hours": "09:00-17:00", "tags": ["历史", "文化", "涨知识"], "queue_prone": False, "avg_stay_min": 120, "emotion_tags": {"excitement": 0.2, "tranquility": 0.8, "sociability": 0.2, "culture_depth": 0.95, "surprise": 0.3, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0, "opening_hours": "09:00-17:00", "has_restroom": True}},
    {"id": "poi_006", "name": "网红打卡点", "category": "购物", "rating": 4.2, "avg_price": 50, "lat": 22.268, "lng": 113.578, "business_hours": "10:00-22:00", "tags": ["网红", "打卡", "购物"], "queue_prone": True, "avg_stay_min": 45, "emotion_tags": {"excitement": 0.7, "tranquility": 0.2, "sociability": 0.6, "culture_depth": 0.3, "surprise": 0.7, "physical_demand": 0.2}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 15, "opening_hours": "10:00-22:00", "has_restroom": True}},
    {"id": "poi_007", "name": "艺术画廊", "category": "文化", "rating": 4.4, "avg_price": 0, "lat": 22.263, "lng": 113.573, "business_hours": "10:00-20:00", "tags": ["艺术", "文艺", "拍照"], "queue_prone": False, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.3, "tranquility": 0.7, "sociability": 0.3, "culture_depth": 0.8, "surprise": 0.5, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0, "opening_hours": "10:00-20:00", "has_restroom": True}},
    {"id": "poi_008", "name": "互动密室", "category": "娱乐", "rating": 4.5, "avg_price": 120, "lat": 22.271, "lng": 113.581, "business_hours": "10:00-22:00", "tags": ["互动", "解谜", "拍照"], "queue_prone": True, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.8, "tranquility": 0.1, "sociability": 0.7, "culture_depth": 0.3, "surprise": 0.9, "physical_demand": 0.4}, "constraints": {"accessible": False, "pet_friendly": False, "queue_time_min": 30, "opening_hours": "10:00-22:00", "has_restroom": True}},
    {"id": "poi_009", "name": "高端西餐厅", "category": "餐饮", "rating": 4.6, "avg_price": 200, "lat": 22.266, "lng": 113.576, "business_hours": "11:00-23:00", "tags": ["西餐", "约会", "浪漫"], "queue_prone": True, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.4, "tranquility": 0.5, "sociability": 0.6, "culture_depth": 0.4, "surprise": 0.3, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 20, "opening_hours": "11:00-23:00", "has_restroom": True}},
    {"id": "poi_010", "name": "深夜书店", "category": "文化", "rating": 4.3, "avg_price": 0, "lat": 22.269, "lng": 113.579, "business_hours": "14:00-02:00", "tags": ["书店", "安静", "深夜"], "queue_prone": False, "avg_stay_min": 60, "emotion_tags": {"excitement": 0.1, "tranquility": 0.9, "sociability": 0.2, "culture_depth": 0.7, "surprise": 0.2, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0, "opening_hours": "14:00-02:00", "has_restroom": True}},
    {"id": "poi_011", "name": "欢乐游乐园", "category": "娱乐", "rating": 4.5, "avg_price": 200, "lat": 22.282, "lng": 113.592, "business_hours": "09:00-21:00", "tags": ["游乐", "刺激", "亲子"], "queue_prone": True, "avg_stay_min": 180, "emotion_tags": {"excitement": 0.9, "tranquility": 0.05, "sociability": 0.7, "culture_depth": 0.1, "surprise": 0.8, "physical_demand": 0.6}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 30, "opening_hours": "09:00-21:00", "has_restroom": True}},
    {"id": "poi_012", "name": "海边栈道", "category": "运动", "rating": 4.4, "avg_price": 0, "lat": 22.258, "lng": 113.568, "business_hours": "00:00-23:59", "tags": ["海滨", "散步", "免费"], "queue_prone": False, "avg_stay_min": 60, "emotion_tags": {"excitement": 0.4, "tranquility": 0.7, "sociability": 0.3, "culture_depth": 0.2, "surprise": 0.4, "physical_demand": 0.5}, "constraints": {"accessible": True, "pet_friendly": True, "queue_time_min": 0, "opening_hours": "00:00-23:59", "has_restroom": False}},
    {"id": "poi_013", "name": "情侣路", "category": "运动", "rating": 4.6, "avg_price": 0, "lat": 22.255, "lng": 113.565, "business_hours": "00:00-23:59", "tags": ["浪漫", "海滨", "散步"], "queue_prone": False, "avg_stay_min": 60, "emotion_tags": {"excitement": 0.4, "tranquility": 0.7, "sociability": 0.3, "culture_depth": 0.2, "surprise": 0.4, "physical_demand": 0.5}, "constraints": {"accessible": True, "pet_friendly": True, "queue_time_min": 0, "opening_hours": "00:00-23:59", "has_restroom": False}},
]

intent = {
    "time": {"period": "下午", "start": "14:00", "end": "22:00"},
    "budget": {"per_person": 300, "type": "弹性"},
    "group": {"size": 2, "type": "情侣"},
    "preferences": {"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5},
    "pace": "平衡型",
    "hard_constraints": ["有氛围感", "可拍照"],
}

result = solve_route(poi_pool, intent, "14:00")
print("Route:")
for step in result["route"]:
    poi = step["poi"]
    tags = poi.get("tags", [])
    photo_tags = {"拍照", "浪漫", "艺术", "约会"}
    match = photo_tags & set(tags)
    print(f"  {poi['name']} ({poi['category']}) tags={tags} match={match}")
