#!/bin/bash
# scripts/demo_api.sh

set -e

echo "=== CityFlow API演示 ==="
echo ""

API_BASE="http://localhost:8000"

# 检查服务
echo "1. 检查服务状态..."
curl -s "$API_BASE/health" | python -m json.tool
echo ""

# 搜索POI
echo "2. 搜索POI..."
curl -s -X POST "$API_BASE/api/poi/search" \
  -H "Content-Type: application/json" \
  -d '{"region": "珠海", "categories": ["文化"]}' | python -m json.tool
echo ""

# 路线规划
echo "3. 路线规划..."
curl -s -X POST "$API_BASE/api/plan" \
  -H "Content-Type: application/json" \
  -d '{"user_input": "周末想一个人安静走走"}' | python -m json.tool
echo ""

echo "=== 演示完成 ==="