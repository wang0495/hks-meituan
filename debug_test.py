"""Debug test_contains_interactive."""
from backend.services.solver import solve_route

poi_pool = [
    {"id": "poi_001", "name": "安静图书馆", "category": "文化", "rating": 4.5, "avg_price": 0, "lat": 22.270, "lng": 113.580, "business_hours": "08:00-21:00", "tags": ["免费", "安静", "学习"], "queue_prone": False, "avg_stay_min": 120, "emotion_tags": {"excitement": 0.1, "tranquility": 0.95, "sociability": 0.1, "culture_depth": 0.9, "surprise": 0.05, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0}},
    {"id": "poi_002", "name": "刺激过山车", "category": "娱乐", "rating": 4.8, "avg_price": 150, "lat": 22.280, "lng": 113.590, "business_hours": "08:00-22:00", "tags": ["刺激", "排队", "年轻人"], "queue_prone": True, "avg_stay_min": 30, "emotion_tags": {"excitement": 0.95, "tranquility": 0.05, "sociability": 0.6, "culture_depth": 0.1, "surprise": 0.8, "physical_demand": 0.7}, "constraints": {"accessible": False, "pet_friendly": False, "queue_time_min": 45}},
    {"id": "poi_003", "name": "浪漫咖啡厅", "category": "美食", "rating": 4.6, "avg_price": 68, "lat": 22.265, "lng": 113.575, "business_hours": "08:00-23:00", "tags": ["浪漫", "约会", "咖啡"], "queue_prone": False, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.3, "tranquility": 0.7, "sociability": 0.5, "culture_depth": 0.4, "surprise": 0.2, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": True, "queue_time_min": 5}},
    {"id": "poi_004", "name": "儿童乐园", "category": "娱乐", "rating": 4.3, "avg_price": 88, "lat": 22.255, "lng": 113.565, "business_hours": "08:00-18:00", "tags": ["亲子", "儿童", "游乐"], "queue_prone": True, "avg_stay_min": 150, "emotion_tags": {"excitement": 0.7, "tranquility": 0.2, "sociability": 0.8, "culture_depth": 0.2, "surprise": 0.6, "physical_demand": 0.5}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 20}},
    {"id": "poi_005", "name": "历史博物馆", "category": "文化", "rating": 4.7, "avg_price": 30, "lat": 22.248, "lng": 113.558, "business_hours": "08:00-17:00", "tags": ["历史", "文化", "教育"], "queue_prone": False, "avg_stay_min": 120, "emotion_tags": {"excitement": 0.2, "tranquility": 0.8, "sociability": 0.3, "culture_depth": 0.95, "surprise": 0.3, "physical_demand": 0.2}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 10}},
    {"id": "poi_006", "name": "海滨公园", "category": "公园", "rating": 4.4, "avg_price": 0, "lat": 22.260, "lng": 113.570, "business_hours": "06:00-22:00", "tags": ["公园", "休息", "自然"], "queue_prone": False, "avg_stay_min": 60, "emotion_tags": {"excitement": 0.15, "tranquility": 0.85, "sociability": 0.3, "culture_depth": 0.0, "surprise": 0.1, "physical_demand": 0.2}, "constraints": {"accessible": True, "pet_friendly": True, "queue_time_min": 0}},
    {"id": "poi_007", "name": "艺术画廊", "category": "文化", "rating": 4.6, "avg_price": 50, "lat": 22.258, "lng": 113.585, "business_hours": "08:00-18:00", "tags": ["艺术", "文艺", "拍照"], "queue_prone": False, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.3, "tranquility": 0.7, "sociability": 0.3, "culture_depth": 0.85, "surprise": 0.4, "physical_demand": 0.2}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 5}},
    {"id": "poi_008", "name": "密室逃脱", "category": "娱乐", "rating": 4.5, "avg_price": 80, "lat": 22.272, "lng": 113.588, "business_hours": "08:00-23:00", "tags": ["互动", "解谜", "拍照"], "queue_prone": False, "avg_stay_min": 60, "emotion_tags": {"excitement": 0.85, "tranquility": 0.1, "sociability": 0.7, "culture_depth": 0.2, "surprise": 0.9, "physical_demand": 0.3}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 10}},
    {"id": "poi_009", "name": "高端西餐厅", "category": "美食", "rating": 4.7, "avg_price": 200, "lat": 22.263, "lng": 113.582, "business_hours": "08:00-22:00", "tags": ["西餐", "约会", "浪漫"], "queue_prone": False, "avg_stay_min": 90, "emotion_tags": {"excitement": 0.4, "tranquility": 0.6, "sociability": 0.5, "culture_depth": 0.3, "surprise": 0.2, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 5}},
    {"id": "poi_010", "name": "登山步道", "category": "自然", "rating": 4.2, "avg_price": 0, "lat": 22.275, "lng": 113.560, "business_hours": "00:00-23:59", "tags": ["户外", "运动", "自然"], "queue_prone": False, "avg_stay_min": 180, "emotion_tags": {"excitement": 0.5, "tranquility": 0.6, "sociability": 0.3, "culture_depth": 0.1, "surprise": 0.3, "physical_demand": 0.9}, "constraints": {"accessible": False, "pet_friendly": True, "queue_time_min": 0}},
    {"id": "poi_011", "name": "街角咖啡馆", "category": "咖啡馆", "rating": 4.3, "avg_price": 35, "lat": 22.268, "lng": 113.578, "business_hours": "08:00-22:00", "tags": ["咖啡", "休息", "安静"], "queue_prone": False, "avg_stay_min": 45, "emotion_tags": {"excitement": 0.1, "tranquility": 0.8, "sociability": 0.3, "culture_depth": 0.2, "surprise": 0.05, "physical_demand": 0.05}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 0}},
    {"id": "poi_012", "name": "水上乐园", "category": "娱乐", "rating": 4.6, "avg_price": 120, "lat": 22.285, "lng": 113.595, "business_hours": "08:00-20:00", "tags": ["刺激", "水上", "夏天"], "queue_prone": True, "avg_stay_min": 120, "emotion_tags": {"excitement": 0.9, "tranquility": 0.05, "sociability": 0.7, "culture_depth": 0.0, "surprise": 0.7, "physical_demand": 0.8}, "constraints": {"accessible": True, "pet_friendly": False, "queue_time_min": 30}},
    {"id": "poi_013", "name": "城市广场", "category": "广场", "rating": 4.0, "avg_price": 0, "lat": 22.266, "lng": 113.576, "business_hours": "00:00-23:59", "tags": ["广场", "休息", "免费"], "queue_prone": False, "avg_stay_min": 30, "emotion_tags": {"excitement": 0.05, "tranquility": 0.75, "sociability": 0.4, "culture_depth": 0.0, "surprise": 0.0, "physical_demand": 0.1}, "constraints": {"accessible": True, "pet_friendly": True, "queue_time_min": 0}},
]

p2_intent = {
    "time": {"period": "下午", "start": "14:00", "end": "22:00"},
    "budget": {"per_person": 300, "type": "弹性"},
    "group": {"size": 2, "type": "情侣"},
    "preferences": {"culture": 0.5, "food": 0.8, "nature": 0.6, "social": 0.5},
    "pace": "平衡型",
    "hard_constraints": ["有氛围感", "可拍照"],
}

result = solve_route(poi_pool, p2_intent, "14:00")

print("Route steps:")
for i, step in enumerate(result["route"]):
    poi = step["poi"]
    print(f"  {i+1}. {poi['name']} (tags: {poi.get('tags', [])})")

interactive_tags = {"互动", "解谜", "体验"}
has_interactive = any(interactive_tags & set(step["poi"].get("tags", [])) for step in result["route"])
print(f"Has interactive: {has_interactive}")
