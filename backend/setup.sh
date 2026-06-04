#!/usr/bin/env bash
# backend/setup.sh — 后端虚拟环境一键构建
#
# 用法:
#   cd backend && bash setup.sh        # 创建/重建 .venv
#   cd backend && bash setup.sh -k     # 保留已有 .venv，仅安装依赖

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

REQUIREMENT_FILE="requirement.txt"
VENV_DIR=".venv"
KEEP_VENV=false

# --- 参数解析 ---
while getopts "kh" opt; do
    case "$opt" in
        k) KEEP_VENV=true ;;
        h)
            echo "用法: setup.sh [-k] [-h]"
            echo "  -k  保留已有 .venv，仅安装依赖"
            echo "  -h  显示帮助"
            exit 0
            ;;
        *) echo "用法: setup.sh [-k] [-h]" >&2; exit 1 ;;
    esac
done

# --- 检查 uv ---
if ! command -v uv &>/dev/null; then
    echo "[ERROR] uv 未安装，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# --- Python 版本选择 ---
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] 未找到 Python 3.11+，请安装后再运行" >&2
    exit 1
fi

echo "[INFO] 使用 Python: $PYTHON_BIN ($($PYTHON_BIN --version))"
echo "[INFO] 使用 uv:    $(uv --version)"

# --- 虚拟环境 ---
if [ "$KEEP_VENV" = true ] && [ -d "$VENV_DIR" ]; then
    echo "[INFO] 保留已有 $VENV_DIR，跳过创建"
else
    if [ -d "$VENV_DIR" ]; then
        echo "[INFO] 删除旧 $VENV_DIR ..."
        rm -rf "$VENV_DIR"
    fi
    echo "[INFO] 创建虚拟环境 ..."
    uv venv --python "$PYTHON_BIN" "$VENV_DIR"
fi

# --- 安装依赖 ---
echo "[INFO] 安装依赖 ($REQUIREMENT_FILE) ..."
uv pip install -r "$REQUIREMENT_FILE" --python "$VENV_DIR/bin/python"

# --- 确保前端占位目录 ---
mkdir -p frontend/public frontend/src/templates

# --- 验证 ---
echo ""
echo "[INFO] 验证安装 ..."
"$VENV_DIR/bin/python" -c "
import fastapi, sqlalchemy, pydantic, apscheduler, httpx
print(f'  FastAPI     {fastapi.__version__}')
print(f'  SQLAlchemy  {sqlalchemy.__version__}')
print(f'  Pydantic    {pydantic.__version__}')
print(f'  APScheduler {apscheduler.__version__}')
print(f'  httpx       {httpx.__version__}')
"

echo ""
echo "[OK] 后端环境就绪。运行测试: cd backend && .venv/bin/python -m pytest tests/"
