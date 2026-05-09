#!/bin/bash
set -e

echo "=== CityFlow 智能城市出行规划系统 ==="

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "错误: 需要 Python >= 3.10，当前版本: $python_version"
    exit 1
fi

echo "✓ Python版本检查通过"

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt -q

# 启动服务
echo ""
echo "启动后端服务..."
echo "访问地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo ""

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
