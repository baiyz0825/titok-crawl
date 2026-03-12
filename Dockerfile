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
# Stage 2: Python runtime (backend + frontend)
# ============================================
FROM python:3.13-slim

# System dependencies: Chromium for Playwright, ffmpeg for whisper
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    # Playwright Chromium dependencies
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

# Copy frontend dist from build stage
COPY --from=frontend-build /build/dist ./frontend/dist

# Data volume for DB, media, browser data, logs
VOLUME /app/data

# Headless mode in container
ENV HEADLESS=true

EXPOSE 8000 8001

CMD ["python", "-m", "backend.main"]
