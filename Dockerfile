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

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITE_BYTECODE=1
ENV PYTHONFAULTHANDLER=ignore

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright chromium
RUN playwright install chromium --with-deps

# Copy backend code
COPY backend/ ./backend/

# Copy frontend dist
COPY --from=frontend-build /build/dist ./frontend/dist

# Create data directories
RUN mkdir -p /app/data/db /app/data/media

# Copy nginx config and entrypoint
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

 ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

EXPOSE 80 8000 8001
VOLUME ["/app/data"]
ENV HEADLESS=true
CMD ["/app/entrypoint.sh"]
