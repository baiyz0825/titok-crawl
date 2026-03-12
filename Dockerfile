# ============================================
# Stage 1: Build frontend
# ============================================
FROM node:20-slim AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build

# ============================================
# Stage 2: Python runtime (backend)
# ============================================
FROM python:3.13-slim

# System dependencies: Chromium for Playwright, ffmpeg for whisper, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    libgtk-3-0 libx11-xcb1 fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps

# Copy backend code
COPY backend/ ./backend/

# Copy frontend dist（供本地 run.sh 模式使用 + entrypoint 复制到 shared volume）
COPY --from=frontend-build /build/dist ./frontend/dist

# Data volume
VOLUME /app/data

ENV HEADLESS=true

EXPOSE 8000 8001

# Entrypoint: 如果 /shared/html 目录存在（mounted volume），把 dist 复制过去供 Nginx 使用
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "backend.main"]
