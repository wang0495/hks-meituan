#!/bin/bash
# scripts/start_prod.sh

set -e

echo "=== CityFlow 生产环境启动 ==="

# 检查环境变量
if [ -z "$OPENAI_API_KEY" ]; then
    echo "警告: OPENAI_API_KEY未设置"
fi

# 启动服务
echo "启动CityFlow生产服务器..."
echo "访问地址: http://localhost:8000"
echo ""

# 使用gunicorn启动
gunicorn backend.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
