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
    echo -e "${YELLOW}更新 Python 依赖...${NC}"
    pip install -r requirements.txt -q
else
    echo -e "${YELLOW}创建虚拟环境...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    echo -e "${YELLOW}安装 Python 依赖...${NC}"
    pip install -r requirements.txt
fi

# ── 1.1 安装 Playwright 浏览器 ──
echo -e "${YELLOW}检查 Playwright 浏览器...${NC}"
if ! playwright install --dry-run chromium 2>/dev/null | grep -q "chromium"; then
    echo -e "${YELLOW}安装 Playwright Chromium...${NC}"
    if playwright install chromium; then
        echo -e "${GREEN}✓ Chromium 安装成功${NC}"
    else
        echo -e "${RED}✗ Chromium 安装失败，尝试重试...${NC}"
        # 尝试使用官方源重试
        PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net playwright install chromium
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Chromium 安装成功（官方源）${NC}"
        else
            echo -e "${RED}✗ 自动安装失败，请手动运行: playwright install chromium${NC}"
            exit 1
        fi
    fi
else
    echo -e "${GREEN}✓ Chromium 已安装${NC}"
fi

# ── 2. 安装 datasette ──
if ! command -v datasette &>/dev/null; then
    echo -e "${YELLOW}安装 datasette...${NC}"
    if pip install datasette -q; then
        echo -e "${GREEN}✓ datasette 安装成功${NC}"
    else
        echo -e "${RED}✗ datasette 安装失败${NC}"
    fi
else
    echo -e "${GREEN}✓ datasette 已安装${NC}"
fi

# ── 3. 前端依赖 & 构建 ──
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}安装前端依赖...${NC}"
    cd frontend
    if npm install; then
        echo -e "${GREEN}✓ 前端依赖安装成功${NC}"
    else
        echo -e "${RED}✗ 前端依赖安装失败${NC}"
        exit 1
    fi
    cd ..
fi

# 前端缓存清理 & 强制重新构建
FRONTEND_REBUILD=false
if [ -d "frontend/dist" ]; then
    # 检查 dist 时间是否早于 src 修改时间
    DIST_TIME=$(stat -f %m frontend/dist 2>/dev/null || stat -c %Y frontend/dist 2>/dev/null)
    SRC_TIME=$(find frontend/src -type f -name "*.vue" -o -name "*.ts" 2>/dev/null | xargs stat -f %m 2>/dev/null | sort -n | tail -1)

    if [ -n "$SRC_TIME" ] && [ "$DIST_TIME" -lt "$SRC_TIME" ]; then
        FRONTEND_REBUILD=true
    fi
fi

if [ ! -d "frontend/dist" ] || [ "$FRONTEND_REBUILD" = true ]; then
    if [ "$FRONTEND_REBUILD" = true ]; then
        echo -e "${YELLOW}前端代码已更新，清理缓存并重新构建...${NC}"
    else
        echo -e "${YELLOW}构建前端...${NC}"
    fi

    # 清理前端缓存
    rm -rf frontend/dist 2>/dev/null || true
    rm -rf frontend/node_modules/.vite 2>/dev/null || true

    cd frontend
    if npm run build; then
        echo -e "${GREEN}✓ 前端构建成功${NC}"
    else
        echo -e "${YELLOW}⚠ 前端构建失败，将使用 dev server${NC}"
    fi
    cd ..
fi

# ── 4. 确保数据目录存在 ──
mkdir -p data/db data/media data/browser data/logs

# ── 4.1 定义端口（使用高位端口避免冲突） ──
BACKEND_PORT=18000
MCP_PORT=18001
DATASETTE_PORT=18002
FRONTEND_PORT=15173

# ── 4.2 清理可能残留的端口占用 ──
cleanup_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}清理端口 $port 占用 (PID: $pid)...${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

cleanup_port $BACKEND_PORT
cleanup_port $DATASETTE_PORT
cleanup_port $FRONTEND_PORT

# ── 5. 导出环境变量 ──
if [ "$HEADLESS_MODE" = true ]; then
    export HEADLESS=true
fi

# 导出端口配置
export BACKEND_PORT=$BACKEND_PORT
export MCP_PORT=$MCP_PORT
export DATASETTE_PORT=$DATASETTE_PORT

# 导出前端配置
export PORT=$FRONTEND_PORT
export VITE_API_URL="http://localhost:$BACKEND_PORT"

# ── 6. 记录所有子进程 PID ──
PIDS=()

# ── 7. 启动后端 ──
echo -e "${GREEN}启动后端 (port $BACKEND_PORT)...${NC}"

# 确保端口可用
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}端口 $BACKEND_PORT 仍被占用，请手动检查${NC}"
    lsof -i :$BACKEND_PORT
    exit 1
fi

# 清理 Python 缓存确保加载最新代码
find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find backend -type f -name "*.pyc" -delete 2>/dev/null || true

# 使用 uvicorn 启动后端，支持热重载
uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
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
echo -e "${GREEN}启动 Datasette (port $DATASETTE_PORT)...${NC}"
datasette data/db/douyin.db -h 0.0.0.0 -p $DATASETTE_PORT --setting sql_time_limit_ms 5000 &
PIDS+=($!)

# ── 9. 启动前端 dev server（仅非无头模式且未跳过） ──
if [ "$HEADLESS_MODE" = false ] && [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${GREEN}启动前端 dev server (port $FRONTEND_PORT)...${NC}"
    cd frontend && PORT=$FRONTEND_PORT npx vite --host &
    PIDS+=($!)
    cd ..
fi

# ── 10. 输出服务地址 ──
echo ""
echo -e "${GREEN}════════════════════════════════════${NC}"
echo -e "${GREEN} 后端 API:  http://localhost:$BACKEND_PORT${NC}"
if [ "$HEADLESS_MODE" = false ] && [ "$SKIP_FRONTEND" = false ]; then
    echo -e "${GREEN} 前端 Dev:  http://localhost:$FRONTEND_PORT${NC}"
fi
echo -e "${GREEN} Datasette: http://localhost:$DATASETTE_PORT${NC}"
echo -e "${GREEN} API 文档:  http://localhost:$BACKEND_PORT/docs${NC}"
echo -e "${GREEN} MCP SSE:   http://localhost:$MCP_PORT/sse${NC}"
echo -e "${GREEN}════════════════════════════════════${NC}"
echo ""
echo "Usage: ./run.sh [--headless] [--no-frontend] [--help]"
echo "Press Ctrl+C to stop all services."

# ── Cleanup ──
cleanup() {
    echo -e "\n${YELLOW}正在关闭所有服务...${NC}"

    # 优先发送 SIGTERM
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done

    # 等待进程优雅退出（最多5秒）
    local count=0
    while [ $count -lt 5 ]; do
        local all_dead=true
        for pid in "${PIDS[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                all_dead=false
                break
            fi
        done
        if [ "$all_dead" = true ]; then
            break
        fi
        sleep 1
        count=$((count + 1))
    done

    # 强制杀死仍在运行的进程
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}强制停止进程 $pid...${NC}"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done

    # 最终清理端口（确保没有残留）
    cleanup_port $BACKEND_PORT
    cleanup_port $MCP_PORT
    cleanup_port $DATASETTE_PORT
    cleanup_port $FRONTEND_PORT

    echo -e "${GREEN}✓ 所有服务已关闭${NC}"
}
trap cleanup EXIT INT TERM

wait
