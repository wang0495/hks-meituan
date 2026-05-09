#!/bin/bash

# CityFlow API测试脚本
set -e

echo "=== CityFlow API测试 ==="
echo ""

API_BASE="http://localhost:8000"

# 测试健康检查
echo "测试1: 健康检查"
response=$(curl -s "$API_BASE/api/health")
echo "响应: $response"
echo ""

# 测试POI搜索
echo "测试2: POI搜索"
response=$(curl -s -X POST "$API_BASE/api/poi/search" \
    -H "Content-Type: application/json" \
    -d '{"region": "珠海", "categories": ["文化"]}')
echo "响应: $(echo $response | head -c 200)..."
echo ""

# 测试POI详情
echo "测试3: POI详情"
response=$(curl -s "$API_BASE/api/poi/detail/poi_00001")
echo "响应: $(echo $response | head -c 200)..."
echo ""

# 测试距离矩阵
echo "测试4: 距离矩阵"
response=$(curl -s -X POST "$API_BASE/api/poi/distance-matrix" \
    -H "Content-Type: application/json" \
    -d '{"poi_ids": ["poi_00001", "poi_00002"]}')
echo "响应: $(echo $response | head -c 200)..."
echo ""

echo "=== 测试完成 ==="
