#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== 抖音采集器 ===${NC}"

# Activate venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt -q
    playwright install chromium
fi

# Install frontend deps if needed
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd frontend && npm install && cd ..
fi

# Start backend
echo -e "${GREEN}Starting backend on port 8000...${NC}"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo -e "${GREEN}Starting frontend on port 5173...${NC}"
cd frontend && npx vite --host &
FRONTEND_PID=$!
cd ..

echo -e "${GREEN}Backend:  http://localhost:8000${NC}"
echo -e "${GREEN}Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}API Docs: http://localhost:8000/docs${NC}"
echo -e "${GREEN}MCP SSE:  http://localhost:8001/sse${NC}"
echo ""
echo "Press Ctrl+C to stop all services."

# Cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

wait
