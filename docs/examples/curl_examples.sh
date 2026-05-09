#!/bin/bash
# CityFlow API cURL 示例

BASE_URL="http://localhost:8000"

# ============================================================
# 1. 路线规划 (SSE流式响应)
# ============================================================
echo "=== 路线规划 ==="
curl -X POST "$BASE_URL/api/plan" \
  -H "Content-Type: application/json" \
  -d '{"user_input": "周末想一个人安静走走"}'

# ============================================================
# 2. 搜索POI
# ============================================================
echo -e "\n=== 搜索POI ==="
curl -X POST "$BASE_URL/api/poi/search" \
  -H "Content-Type: application/json" \
  -d '{"region": "珠海", "categories": ["文化"]}'

# ============================================================
# 3. 获取POI详情
# ============================================================
echo -e "\n=== POI详情 ==="
curl "$BASE_URL/api/poi/detail/poi_00001"

# ============================================================
# 4. 计算距离矩阵
# ============================================================
echo -e "\n=== 距离矩阵 ==="
curl -X POST "$BASE_URL/api/poi/distance-matrix" \
  -H "Content-Type: application/json" \
  -d '{"poi_ids": ["poi_00001", "poi_00002"]}'

# ============================================================
# 5. 调整路线 (对话式)
# ============================================================
echo -e "\n=== 调整路线 ==="
ROUTE_ID="your-route-id"
curl -X POST "$BASE_URL/api/dialogue/$ROUTE_ID" \
  -H "Content-Type: application/json" \
  -d '{"instruction": "太赶了，想轻松点"}'
