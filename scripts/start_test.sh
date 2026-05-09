#!/bin/bash
# scripts/start_test.sh

set -e

echo "=== CityFlow 测试环境启动 ==="

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

echo "激活虚拟环境..."
source venv/bin/activate || source venv/Scripts/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt -q
pip install pytest pytest-asyncio pytest-cov -q

# 运行测试
echo ""
echo "运行测试..."
python -m pytest tests/ -v --cov=backend --cov-report=html

echo ""
echo "测试完成，覆盖率报告: htmlcov/index.html"
