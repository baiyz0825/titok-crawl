#!/bin/sh
set -e

echo "=== Douyin Scraper All-in-One Container ==="

# 创建数据目录
mkdir -p /app/data/db /app/data/media

# 启动后端 API (后台运行)
echo "Starting backend API..."
cd /app
python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    --timeout-keep-alive 120 \
    --log-level info &

# 启动 MCP 服务器 (后台运行)
echo "Starting MCP server..."
python -m mcp run backend/mcp_server.py \
    --transport sse \
    --port 8001 &

# 等待后端启动
echo "Waiting for backend to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/sessions/status > /dev/null 2>&1; then
        echo "Backend is ready!"
        break
    fi
    sleep 1
done

# 等待 MCP 服务器启动
echo "Waiting for MCP server to be ready..."
for i in $(seq 1 10); do
    if curl -sf http://localhost:8001/ > /dev/null 2>&1; then
        echo "MCP server is ready!"
        break
    fi
    sleep 1
done

# 启动 nginx (前台运行)
echo "Starting nginx..."
exec nginx -g "daemon off;"
