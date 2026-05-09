#!/bin/bash
# scripts/rollback.sh -- CityFlow 回滚脚本
# 用法: ./scripts/rollback.sh [版本号]
#   不带参数: 回滚到上一个版本
#   带参数:   回滚到指定版本
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step() { echo -e "\n${CYAN}>>> $*${NC}"; }

# ---- 检测 docker compose 命令 ----
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

COMPOSE_FILE="docker-compose.yml"
HEALTH_URL="http://localhost:80/api/health"
HEALTH_RETRIES=15
HEALTH_INTERVAL=3
DEPLOY_RECORD="backups/deploy_history.log"

# ---- 确定回滚目标版本 ----
TARGET_VERSION="${1:-}"

if [ -n "$TARGET_VERSION" ]; then
    # 用户指定了版本
    log "回滚到指定版本: $TARGET_VERSION"
else
    # 从部署历史中获取上一个版本
    if [ ! -f "$DEPLOY_RECORD" ]; then
        err "未找到部署历史文件: $DEPLOY_RECORD"
        err "请手动指定版本: $0 <版本号>"
        exit 1
    fi

    # 提取最近两次成功的部署版本
    PREV_VERSIONS=$(grep "action=deploy$" "$DEPLOY_RECORD" | tail -2 | head -1 | grep -oP 'version=\K[^ ]+' || true)

    if [ -z "$PREV_VERSIONS" ]; then
        # 回退方案：列出所有可用的 cityflow 镜像
        warn "部署历史中未找到可回滚的版本"
        echo ""
        echo "可用的 cityflow 镜像:"
        docker images cityflow --format "  {{.Tag}}  ({{.CreatedAt}})" 2>/dev/null | head -10
        echo ""
        echo "请手动指定版本: $0 <版本号>"
        exit 1
    fi

    TARGET_VERSION="$PREV_VERSIONS"
    log "从部署历史中找到上一版本: $TARGET_VERSION"
fi

# ---- 验证镜像存在 ----
step "验证目标镜像"

if ! docker image inspect "cityflow:$TARGET_VERSION" > /dev/null 2>&1; then
    err "镜像 cityflow:$TARGET_VERSION 不存在"
    echo ""
    echo "可用的 cityflow 镜像:"
    docker images cityflow --format "  {{.Tag}}  ({{.CreatedAt}})" 2>/dev/null | head -10
    exit 1
fi

log "镜像 cityflow:$TARGET_VERSION 存在"

# ---- 确认回滚 ----
echo ""
echo "========================================="
echo "  CityFlow 回滚"
echo "  目标版本: $TARGET_VERSION"
echo "========================================="
echo ""

# 非交互模式下跳过确认（CI/CD 场景）
if [ -t 0 ] && [ "${FORCE_ROLLBACK:-}" != "1" ]; then
    read -r -p "确认回滚? [y/N] " confirm
    case "$confirm" in
        [yY]|[yY][eE][sS]) ;;
        *)
            warn "回滚已取消"
            exit 0 ;;
    esac
fi

# ---- 记录回滚 ----
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
mkdir -p "$(dirname "$DEPLOY_RECORD")"
echo "$TIMESTAMP | version=$TARGET_VERSION | action=rollback" >> "$DEPLOY_RECORD"

# ---- 停止当前服务 ----
step "停止当前服务"

$COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
log "当前服务已停止"

# ---- 切换镜像标签 ----
step "切换到目标版本"

docker tag "cityflow:$TARGET_VERSION" "cityflow:latest"
log "已将 cityflow:latest 指向 $TARGET_VERSION"

# ---- 启动服务 ----
step "启动回滚版本"

$COMPOSE_CMD -f "$COMPOSE_FILE" up -d

# ---- 健康检查 ----
step "健康检查"

healthy=false
for i in $(seq 1 "$HEALTH_RETRIES"); do
    sleep "$HEALTH_INTERVAL"
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        healthy=true
        log "健康检查通过（第 ${i} 次尝试）"
        break
    fi
    warn "等待服务就绪... ($i/$HEALTH_RETRIES)"
done

if [ "$healthy" = false ]; then
    err "回滚后健康检查失败"
    err "查看日志: $COMPOSE_CMD -f $COMPOSE_FILE logs --tail=50"
    echo "$TIMESTAMP | version=$TARGET_VERSION | action=rollback_failed" >> "$DEPLOY_RECORD"
    exit 1
fi

# ---- 显示服务状态 ----
step "服务状态"

$COMPOSE_CMD -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "========================================="
echo "  回滚完成"
echo "  版本: $TARGET_VERSION"
echo "  访问: http://localhost"
echo "========================================="
