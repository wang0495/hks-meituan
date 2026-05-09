#!/bin/bash
# scripts/deploy.sh -- CityFlow 部署脚本
# 用法: ./scripts/deploy.sh [dev|prod] [--no-build] [--force]
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

# ---- 参数解析 ----
ENVIRONMENT="dev"
NO_BUILD=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        dev|development)   ENVIRONMENT="development"; shift ;;
        prod|production)   ENVIRONMENT="production"; shift ;;
        --no-build)        NO_BUILD=true; shift ;;
        --force)           FORCE=true; shift ;;
        -h|--help)
            echo "用法: $0 [环境] [选项]"
            echo "  环境: dev (默认) | prod"
            echo "  --no-build  跳过镜像构建（使用已有镜像）"
            echo "  --force     跳过确认提示"
            exit 0 ;;
        *) err "未知参数: $1"; exit 1 ;;
    esac
done

COMPOSE_FILE="docker-compose.yml"
HEALTH_URL="http://localhost:80/api/health"
HEALTH_RETRIES=20
HEALTH_INTERVAL=3

# ---- 获取版本信息 ----
VERSION="unknown"
if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    VERSION=$(git describe --tags --always --dirty 2>/dev/null || git rev-parse --short HEAD 2>/dev/null || echo "unknown")
fi

echo "========================================="
echo "  CityFlow 部署"
echo "  环境:   $ENVIRONMENT"
echo "  版本:   $VERSION"
echo "  文件:   $COMPOSE_FILE"
echo "========================================="

# ---- 前置检查 ----
step "前置检查"

if ! command -v docker &>/dev/null; then
    err "未安装 Docker"; exit 1
fi

# 检测 docker compose 命令（兼容 v1 和 v2）
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    err "未安装 docker-compose"; exit 1
fi

# 检查 compose 文件
if [ ! -f "$COMPOSE_FILE" ]; then
    err "未找到 $COMPOSE_FILE"; exit 1
fi

# 检查优化版 Dockerfile
DOCKERFILE="Dockerfile.optimized"
if [ ! -f "$DOCKERFILE" ]; then
    warn "未找到 $DOCKERFILE，回退到 Dockerfile"
    DOCKERFILE="Dockerfile"
fi

# 检查环境变量文件
ENV_FILE=".env"
if [ "$ENVIRONMENT" = "production" ] && [ -f ".env.prod" ]; then
    ENV_FILE=".env.prod"
fi
if [ ! -f "$ENV_FILE" ]; then
    warn "未找到 $ENV_FILE，将使用默认环境变量"
else
    log "使用环境变量: $ENV_FILE"
fi

log "前置检查通过"

# ---- 备份当前版本信息 ----
step "记录部署前状态"

BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"
DEPLOY_RECORD="$BACKUP_DIR/deploy_history.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 记录当前运行的镜像 ID（用于回滚）
PREV_IMAGE_ID=$(docker inspect --format='{{.Image}}' cityflow-backend1 2>/dev/null || echo "none")
echo "$TIMESTAMP | env=$ENVIRONMENT | version=$VERSION | image=$PREV_IMAGE_ID | action=deploy" >> "$DEPLOY_RECORD"
log "部署记录已写入 $DEPLOY_RECORD"

# ---- 构建镜像 ----
if [ "$NO_BUILD" = false ]; then
    step "构建 Docker 镜像 (使用 $DOCKERFILE)"

    docker build \
        -f "$DOCKERFILE" \
        -t "cityflow:$VERSION" \
        -t "cityflow:latest" \
        --build-arg APP_VERSION="$VERSION" \
        . 2>&1 | tail -5

    log "镜像构建完成: cityflow:$VERSION"
else
    step "跳过镜像构建 (--no-build)"
    log "使用已有镜像: cityflow:latest"
fi

# ---- 拉取依赖镜像 ----
step "拉取依赖镜像"

$COMPOSE_CMD -f "$COMPOSE_FILE" pull --ignore-pull-failures redis nginx 2>/dev/null || true
log "依赖镜像就绪"

# ---- 停止旧服务 ----
step "停止旧服务"

$COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
log "旧服务已停止"

# ---- 启动新服务 ----
step "启动新服务"

$COMPOSE_CMD -f "$COMPOSE_FILE" up -d --build

log "服务启动命令已执行"

# ---- 健康检查 ----
step "健康检查（等待服务就绪，最多 ${HEALTH_RETRIES} 次）"

healthy=false
for i in $(seq 1 "$HEALTH_RETRIES"); do
    sleep "$HEALTH_INTERVAL"
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        healthy=true
        log "健康检查通过（第 ${i} 次尝试，耗时 $((i * HEALTH_INTERVAL))s）"
        break
    fi
    warn "等待服务就绪... ($i/$HEALTH_RETRIES)"
done

if [ "$healthy" = false ]; then
    err "健康检查失败，服务未在 $((HEALTH_RETRIES * HEALTH_INTERVAL))s 内就绪"
    err "查看日志: $COMPOSE_CMD -f $COMPOSE_FILE logs --tail=50"
    echo "$TIMESTAMP | env=$ENVIRONMENT | version=$VERSION | action=deploy_failed" >> "$DEPLOY_RECORD"

    step "自动回滚"
    $COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
    err "已停止失败的部署，请手动检查"
    exit 1
fi

# ---- 服务状态验证 ----
step "服务状态"

$COMPOSE_CMD -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# 验证所有后端实例健康
BACKEND_HEALTHY=0
for i in 1 2 3; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "cityflow-backend${i}" 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "healthy" ]; then
        BACKEND_HEALTHY=$((BACKEND_HEALTHY + 1))
    else
        warn "backend${i} 状态: $STATUS"
    fi
done
log "后端实例: ${BACKEND_HEALTHY}/3 健康"

# ---- 部署完成 ----
echo ""
echo "========================================="
echo "  部署完成"
echo "  版本:   $VERSION"
echo "  环境:   $ENVIRONMENT"
echo "  访问:   http://localhost"
echo "  API:    http://localhost/api/health"
echo "  文档:   http://localhost/docs"
echo "  监控:   http://localhost/api/health/detailed"
echo "========================================="
