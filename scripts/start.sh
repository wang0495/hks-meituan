#!/bin/bash
# scripts/start.sh -- CityFlow 本地开发启动脚本
# 用法: ./scripts/start.sh [--prod]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---- 解析参数 ----
MODE="development"
HOST="0.0.0.0"
PORT="8000"
RELOAD="--reload"
WORKERS=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --prod)
            MODE="production"
            RELOAD=""
            WORKERS=4
            shift ;;
        --port)
            PORT="$2"; shift 2 ;;
        --host)
            HOST="$2"; shift 2 ;;
        --workers)
            WORKERS="$2"; shift 2 ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo "  --prod          生产模式（禁用 reload，4 worker）"
            echo "  --port PORT     指定端口（默认 8000）"
            echo "  --host HOST     指定监听地址（默认 0.0.0.0）"
            echo "  --workers N     worker 数量（默认 1，生产模式 4）"
            exit 0 ;;
        *)
            err "未知参数: $1"; exit 1 ;;
    esac
done

echo "========================================="
echo "  CityFlow - 智能城市出行规划系统"
echo "  模式: $MODE"
echo "========================================="
echo ""

# ---- 检查 Python 版本 ----
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    err "未找到 Python，请安装 Python >= 3.10"
    exit 1
fi

python_version=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    err "需要 Python >= 3.10，当前版本: $python_version"
    exit 1
fi
log "Python $python_version"

# ---- 虚拟环境 ----
VENV_DIR="$PROJECT_ROOT/venv"
if [ ! -d "$VENV_DIR" ]; then
    log "创建虚拟环境..."
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

# 激活（兼容 Windows Git Bash）
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    err "无法找到虚拟环境激活脚本"
    exit 1
fi
log "虚拟环境已激活"

# ---- 安装依赖 ----
if [ -f "requirements.txt" ]; then
    log "安装依赖..."
    pip install -r requirements.txt -q --disable-pip-version-check
fi

# ---- 加载环境变量 ----
ENV_FILE=".env"
if [ "$MODE" = "development" ] && [ -f ".env.dev" ]; then
    ENV_FILE=".env.dev"
elif [ "$MODE" = "production" ] && [ -f ".env.prod" ]; then
    ENV_FILE=".env.prod"
fi

if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    log "已加载环境变量: $ENV_FILE"
fi

# ---- 验证配置 ----
log "验证配置..."
if python -m backend.tools.check_config 2>/dev/null; then
    log "配置验证通过"
else
    warn "配置验证脚本不存在或失败，跳过"
fi

# ---- 启动服务 ----
echo ""
log "启动 uvicorn 服务..."
log "访问地址:  http://localhost:$PORT"
log "API 文档:  http://localhost:$PORT/docs"
log "健康检查:  http://localhost:$PORT/api/health"
echo ""

# shellcheck disable=SC2086
exec python -m uvicorn backend.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    $RELOAD
