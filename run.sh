#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Parse arguments
HEADLESS_MODE=false
SKIP_FRONTEND=false
for arg in "$@"; do
    case $arg in
        --headless)
            HEADLESS_MODE=true
            ;;
        --no-frontend)
            SKIP_FRONTEND=true
            ;;
        --help|-h)
            echo "Usage: ./run.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --headless      启用无头浏览器模式（无桌面环境）"
            echo "  --no-frontend   不启动前端 dev server（使用已构建的 dist）"
            echo "  --help, -h      显示帮助信息"
            exit 0
            ;;
    esac
done

echo -e "${GREEN}=== 抖音采集器 ===${NC}"
if [ "$HEADLESS_MODE" = true ]; then
    echo -e "${YELLOW}无头模式已启用${NC}"
fi

# ── 1. Python 虚拟环境 ──
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}虚拟环境已激活${NC}"
    # Sync dependencies on every start
    pip install -r requirements.txt -q 2>/dev/null
else
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt -q
    echo -e "${YELLOW}安装 Playwright Chromium...${NC}"
    playwright install chromium
fi

# ── 2. 安装 datasette ──
if ! command -v datasette &>/dev/null; then
    echo -e "${YELLOW}安装 datasette...${NC}"
    pip install datasette -q
fi

# ── 3. 前端依赖 & 构建 ──
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}安装前端依赖...${NC}"
    cd frontend && npm install && cd ..
fi

if [ ! -d "frontend/dist" ]; then
    echo -e "${YELLOW}构建前端...${NC}"
    cd frontend && npm run build && cd ..
fi

# ── 4. 确保数据目录存在 ──
mkdir -p data/db data/media data/browser data/logs

# ── 5. 导出环境变量 ──
if [ "$HEADLESS_MODE" = true ]; then
    export HEADLESS=true
fi

# ── 6. 记录所有子进程 PID ──
PIDS=()

# ── 7. 启动后端 ──
echo -e "${GREEN}启动后端 (port 8000)...${NC}"
python -m backend.main &
PIDS+=($!)

# 等待后端初始化数据库（datasette 需要 db 文件存在）
echo -e "${YELLOW}等待数据库初始化...${NC}"
for i in $(seq 1 30); do
    if [ -f "data/db/douyin.db" ]; then
        echo -e "${GREEN}数据库就绪${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}警告：等待数据库超时，datasette 可能无法启动${NC}"
    fi
    sleep 1
done

# ── 8. 启动 datasette ──
echo -e "${GREEN}启动 Datasette (port 8002)...${NC}"
datasette data/db/douyin.db -h 0.0.0.0 -p 8002 --setting sql_time_limit_ms 5000 &
PIDS+=($!)

# ── 9. 启动前端 dev server（仅非无头模式且未跳过） ──
if [ "$HEADLESS_MODE" = false ] && [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${GREEN}启动前端 dev server (port 5173)...${NC}"
    cd frontend && npx vite --host &
    PIDS+=($!)
    cd ..
fi

# ── 10. 输出服务地址 ──
echo ""
echo -e "${GREEN}════════════════════════════════════${NC}"
echo -e "${GREEN} 后端 API:  http://localhost:8000${NC}"
if [ "$HEADLESS_MODE" = false ] && [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${GREEN} 前端 Dev:  http://localhost:5173${NC}"
fi
echo -e "${GREEN} Datasette: http://localhost:8002${NC}"
echo -e "${GREEN} API 文档:  http://localhost:8000/docs${NC}"
echo -e "${GREEN} MCP SSE:   http://localhost:8001/sse${NC}"
echo -e "${GREEN}════════════════════════════════════${NC}"
echo ""
echo "Usage: ./run.sh [--headless] [--no-frontend] [--help]"
echo "Press Ctrl+C to stop all services."

# ── Cleanup ──
cleanup() {
    echo -e "\n${YELLOW}正在关闭所有服务...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
    wait 2>/dev/null
    echo -e "${GREEN}已关闭${NC}"
}
trap cleanup EXIT INT TERM

wait
