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
# Stage 2: All-in-one runtime (backend + frontend + nginx)
# ============================================
FROM python:3.13-slim

# Container metadata
LABEL org.opencontainers.image.source=https://github.com/baiyz0825/titok-crawl
LABEL org.opencontainers.image.description="Douyin/TikTok video scraper with web UI and MCP support"
LABEL org.opencontainers.image.licenses=MIT

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITE_BYTECODE=1
ENV PYTHONFAULTHANDLER=ignore

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-unifont \
    fonts-noto-color-emoji \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/* \
    && playwright install chromium

# Copy backend code
COPY backend/ ./backend/

# Copy frontend dist
COPY --from=frontend-build /build/dist ./frontend/dist

# Create data directories
RUN mkdir -p /app/data/db /app/data/media

# Copy nginx config and entrypoint
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/entrypoint.sh /app/entrypoint.sh
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /var/log/supervisor && \
    ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

EXPOSE 80
VOLUME ["/app/data"]
ENV HEADLESS=true
CMD ["/app/entrypoint.sh"]
