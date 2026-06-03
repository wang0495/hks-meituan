"""美团API工具定义 — 注册为 LLM function calling 的 tools。

每个 tool 对应 meituan_server 的一个接口，
LLM 通过 tool_use 调用获取数据，自行完成路线规划推理。
"""

MEITUAN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_poi",
            "description": "搜索商户/景点。支持按关键词、品类、位置半径、价格区间、评分筛选。返回商户列表含名称、地址、评分、价格、营业时间、坐标。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如'海鲜'、'咖啡馆'、'密室'",
                    },
                    "category": {
                        "type": "string",
                        "description": "品类筛选：餐饮、文化、娱乐、景点、自然风光、运动、购物等",
                        "enum": [
                            "餐饮",
                            "文化",
                            "娱乐",
                            "景点",
                            "自然风光",
                            "运动",
                            "购物",
                            "咖啡馆",
                            "酒店",
                            "温泉SPA",
                            "密室逃脱",
                            "剧本杀",
                            "书店",
                            "夜市",
                        ],
                    },
                    "lat": {
                        "type": "number",
                        "description": "用户当前纬度",
                    },
                    "lng": {
                        "type": "number",
                        "description": "用户当前经度",
                    },
                    "radius_km": {
                        "type": "number",
                        "description": "搜索半径(公里)，默认10",
                        "default": 10,
                    },
                    "price_min": {
                        "type": "number",
                        "description": "最低人均消费",
                    },
                    "price_max": {
                        "type": "number",
                        "description": "最高人均消费",
                    },
                    "rating_min": {
                        "type": "number",
                        "description": "最低评分",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回条数，默认50",
                        "default": 50,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_poi_detail",
            "description": "获取商户完整详情，含设施标签、排队时间、无障碍、宠物友好、情绪标签、适用人群等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_id": {
                        "type": "string",
                        "description": "商户ID，如 'poi_00001'",
                    },
                },
                "required": ["poi_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_poi_reviews",
            "description": "获取商户的UGC用户评价。返回用户评论内容、评分、评价关键词汇总。用于判断是否'踩雷'、找到亮点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_id": {
                        "type": "string",
                        "description": "商户ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "最多返回条数，默认10",
                        "default": 10,
                    },
                },
                "required": ["poi_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_poi_location",
            "description": "获取商户精确位置，含坐标、结构化地址、附近地标。用于路线编排时计算距离。",
            "parameters": {
                "type": "object",
                "properties": {
                    "poi_id": {
                        "type": "string",
                        "description": "商户ID",
                    },
                },
                "required": ["poi_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_route_distance",
            "description": "计算两点间的距离和预估耗时。支持驾驶/步行/骑行模式。返回距离(公里)和耗时(分钟)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_lat": {
                        "type": "number",
                        "description": "起点纬度",
                    },
                    "origin_lng": {
                        "type": "number",
                        "description": "起点经度",
                    },
                    "dest_lat": {
                        "type": "number",
                        "description": "终点纬度",
                    },
                    "dest_lng": {
                        "type": "number",
                        "description": "终点经度",
                    },
                    "mode": {
                        "type": "string",
                        "description": "出行方式",
                        "enum": ["driving", "walking", "cycling", "transit"],
                        "default": "driving",
                    },
                },
                "required": ["origin_lat", "origin_lng", "dest_lat", "dest_lng"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hot_trending",
            "description": "获取当前热门商户排行。可按品类筛选，返回热度评分和排名。用于推荐'必去'地点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "品类筛选",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认20",
                        "default": 20,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_area_boundaries",
            "description": "获取城市商圈范围信息。返回各商圈中心坐标、边界、商户数量、主要品类。用于了解区域分布。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，默认珠海",
                        "default": "珠海",
                    },
                },
            },
        },
    },
]
