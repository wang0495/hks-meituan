#!/bin/bash
# scripts/deploy-dev.sh -- CityFlow 本地开发环境启动
# 用法: ./scripts/deploy-dev.sh [up|down|restart|logs]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker-compose.dev.yml"

# 检测 docker compose 命令
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "未安装 docker-compose" >&2
    exit 1
fi

ACTION="${1:-up}"

case "$ACTION" in
    up)
        echo "启动开发环境..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build
        echo "等待服务就绪..."
        sleep 5
        curl -sf http://localhost:8000/health && echo " 服务已就绪" || echo " 服务启动中..."
        echo ""
        echo "访问地址: http://localhost:8000"
        echo "API 文档: http://localhost:8000/docs"
        ;;
    down)
        echo "停止开发环境..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans
        ;;
    restart)
        echo "重启开发环境..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" restart
        ;;
    logs)
        $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f --tail=100
        ;;
    *)
        echo "用法: $0 [up|down|restart|logs]"
        exit 1
        ;;
esac
