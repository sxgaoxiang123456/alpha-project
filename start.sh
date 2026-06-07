#!/usr/bin/env bash
# start.sh — A股 AI 盯盘助手 一键启动脚本
# 用法: bash start.sh [-p PORT] [--setup] [--no-setup] [-h]
#
# 说明:
#   本项目采用 FastAPI + Jinja2 SSR 架构，前端模板和静态文件由后端直接 serve，
#   无需单独启动前端服务。本脚本仅启动后端 uvicorn 服务。
#
#   启动前会自动检测:
#   1. uv 是否安装
#   2. backend/.venv 虚拟环境是否存在
#   3. 关键 Python 依赖是否已安装
#   4. backend/.env 配置文件是否存在

set -euo pipefail

# --- 路径配置 ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
UVICORN_BIN="$VENV_DIR/bin/uvicorn"
REQUIREMENT_FILE="$BACKEND_DIR/requirement.txt"

# --- 默认参数 ---
PORT=8000
HOST="127.0.0.1"
FORCE_SETUP=false
SKIP_SETUP=false

# --- 颜色输出 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- 参数解析 ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --setup)
            FORCE_SETUP=true
            shift
            ;;
        --no-setup)
            SKIP_SETUP=true
            shift
            ;;
        -h|--help)
            echo "A股 AI 盯盘助手 — 一键启动脚本"
            echo ""
            echo "用法: bash start.sh [选项]"
            echo ""
            echo "选项:"
            echo "  -p, --port PORT    指定服务端口 (默认: 8000)"
            echo "  --setup            强制重新安装依赖"
            echo "  --no-setup         跳过依赖检测"
            echo "  -h, --help         显示本帮助"
            echo ""
            echo "示例:"
            echo "  bash start.sh              # 默认启动"
            echo "  bash start.sh -p 8080      # 指定端口"
            echo "  bash start.sh --setup      # 强制重装依赖后启动"
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR] 未知参数: $1${NC}" >&2
            echo "使用 -h 查看帮助" >&2
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  A股 AI 盯盘助手 — 启动中...          ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# --- 1. 检测 uv ---
if ! command -v uv &>/dev/null; then
    echo -e "${RED}[ERROR] uv 未安装${NC}"
    echo "请先安装 uv:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} uv 已安装 ($(uv --version))"

# --- 2. 检测 Python 3.11+ ---
PYTHON_CANDIDATE=""
for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [[ "$major" -ge 3 && "$minor" -ge 11 ]]; then
            PYTHON_CANDIDATE="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CANDIDATE" ]]; then
    echo -e "${RED}[ERROR] 未找到 Python 3.11+${NC}"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Python 已安装 ($($PYTHON_CANDIDATE --version))"

# --- 3. 检测/创建虚拟环境 ---
if [[ "$FORCE_SETUP" == true ]]; then
    echo -e "${YELLOW}[INFO] 强制重新安装依赖...${NC}"
    cd "$BACKEND_DIR"
    bash setup.sh
elif [[ "$SKIP_SETUP" == true ]]; then
    echo -e "${YELLOW}[INFO] 跳过依赖检测${NC}"
    if [[ ! -d "$VENV_DIR" ]]; then
        echo -e "${RED}[ERROR] 虚拟环境不存在，无法跳过 setup${NC}"
        exit 1
    fi
else
    if [[ ! -d "$VENV_DIR" ]]; then
        echo -e "${YELLOW}[INFO] 虚拟环境不存在，正在初始化...${NC}"
        cd "$BACKEND_DIR"
        bash setup.sh
    else
        echo -e "${GREEN}[OK]${NC} 虚拟环境已存在 ($VENV_DIR)"

        # --- 4. 检测关键依赖 ---
        echo -n "[INFO] 检测依赖包 ... "
        MISSING_DEPS=""
        for pkg in fastapi sqlalchemy pydantic apscheduler httpx jinja2; do
            if ! "$PYTHON_BIN" -c "import $pkg" 2>/dev/null; then
                MISSING_DEPS="$MISSING_DEPS $pkg"
            fi
        done

        if [[ -n "$MISSING_DEPS" ]]; then
            echo -e "${YELLOW}缺失: $MISSING_DEPS${NC}"
            echo -e "${YELLOW}[INFO] 正在安装缺失的依赖...${NC}"
            cd "$BACKEND_DIR"
            uv pip install -r "$REQUIREMENT_FILE" --python "$PYTHON_BIN"
        else
            echo -e "${GREEN}全部就绪${NC}"
        fi
    fi
fi

# --- 5. 检测 .env ---
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    echo -e "${YELLOW}[WARN] backend/.env 不存在${NC}"
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        echo -e "${YELLOW}[INFO] 从项目根目录复制 .env...${NC}"
        cp "$PROJECT_ROOT/.env" "$BACKEND_DIR/.env"
    else
        echo -e "${YELLOW}[WARN] 项目根目录也没有 .env，将使用默认值${NC}"
    fi
else
    echo -e "${GREEN}[OK]${NC} .env 配置文件已存在"
fi

# --- 6. 检测数据目录 ---
mkdir -p "$PROJECT_ROOT/data"
echo -e "${GREEN}[OK]${NC} 数据目录已就绪"

# --- 7. 检查端口占用 ---
if lsof -Pi :"$PORT" -sTCP:LISTEN -t &>/dev/null; then
    echo -e "${YELLOW}[WARN] 端口 $PORT 已被占用${NC}"
    echo "尝试释放端口..."
    lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true
    sleep 1
    if lsof -Pi :"$PORT" -sTCP:LISTEN -t &>/dev/null; then
        echo -e "${RED}[ERROR] 无法释放端口 $PORT，请手动处理${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK]${NC} 端口 $PORT 已释放"
fi

# --- 8. 启动服务 ---
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  服务启动成功！                        ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "  访问地址:"
echo -e "    ${GREEN}http://$HOST:$PORT/${NC}           — Dashboard 首页"
echo -e "    ${GREEN}http://$HOST:$PORT/settings${NC}     — 系统设置"
echo -e "    ${GREEN}http://$HOST:$PORT/watchlist-page${NC} — 自选股管理"
echo -e "    ${GREEN}http://$HOST:$PORT/health${NC}       — 健康检查"
echo ""
echo "  快捷键:"
echo "    Ctrl+C — 停止服务"
echo ""

# 在 backend 目录下启动，PYTHONPATH 指向项目根目录
cd "$BACKEND_DIR"
export PYTHONPATH="$PROJECT_ROOT"

# 捕获信号优雅退出
cleanup() {
    echo ""
    echo -e "${YELLOW}[INFO] 正在停止服务...${NC}"
    exit 0
}
trap cleanup INT TERM

# 启动 uvicorn
exec "$UVICORN_BIN" app.main:app --host "$HOST" --port "$PORT" --reload
