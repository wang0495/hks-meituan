#!/bin/bash

# CityFlow 演示脚本
set -e

echo "=== CityFlow 智能城市出行规划系统演示 ==="
echo ""

API_BASE="http://localhost:8000"

# 检查服务是否运行
if ! curl -s "$API_BASE/api/health" > /dev/null 2>&1; then
    echo "错误: 服务未运行，请先执行 ./run.sh"
    exit 1
fi

echo "✓ 服务运行正常"
echo ""

# 演示场景1: 社恐独居
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "场景1: 社恐独居"
echo "输入: '周末想出去走走，不想去人多的地方'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

response=$(curl -s -X POST "$API_BASE/api/plan" \
    -H "Content-Type: application/json" \
    -d '{"user_input": "周末想出去走走，不想去人多的地方"}')

echo "响应:"
echo "$response" | python -m json.tool 2>/dev/null || echo "$response" | head -c 500
echo ""
echo ""

# 演示场景2: 亲子出行
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "场景2: 亲子出行"
echo "输入: '周末一家人带娃出去，让他消耗体力'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

response=$(curl -s -X POST "$API_BASE/api/plan" \
    -H "Content-Type: application/json" \
    -d '{"user_input": "周末一家人带娃出去，让他消耗体力"}')

echo "响应:"
echo "$response" | python -m json.tool 2>/dev/null || echo "$response" | head -c 500
echo ""
echo ""

# 演示场景3: 情侣约会
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "场景3: 情侣约会"
echo "输入: '和女朋友约会，想找有氛围的地方'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

response=$(curl -s -X POST "$API_BASE/api/plan" \
    -H "Content-Type: application/json" \
    -d '{"user_input": "和女朋友约会，想找有氛围的地方"}')

echo "响应:"
echo "$response" | python -m json.tool 2>/dev/null || echo "$response" | head -c 500
echo ""
echo ""

# 演示场景4: 带宠物
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "场景4: 带宠物出行"
echo "输入: '带狗子出去转转'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

response=$(curl -s -X POST "$API_BASE/api/plan" \
    -H "Content-Type: application/json" \
    -d '{"user_input": "带狗子出去转转"}')

echo "响应:"
echo "$response" | python -m json.tool 2>/dev/null || echo "$response" | head -c 500
echo ""
echo ""

# 演示场景5: 朋友聚会
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "场景5: 朋友聚会"
echo "输入: '想找便宜好玩的地方，和朋友一起'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

response=$(curl -s -X POST "$API_BASE/api/plan" \
    -H "Content-Type: application/json" \
    -d '{"user_input": "想找便宜好玩的地方，和朋友一起"}')

echo "响应:"
echo "$response" | python -m json.tool 2>/dev/null || echo "$response" | head -c 500
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "=== 演示完成 ==="
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
