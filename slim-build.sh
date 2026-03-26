#!/bin/bash
set -e

# ============================================
# Docker Slim 镜像压缩脚本
# ============================================
# 使用 docker-slim 工压缩镜像大小
# 要求先安装 docker-slim: https://github.com/slimtoolkit/docker-slim
# ============================================

IMAGE_NAME="douyin-scraper"
TAG="latest"
SLIM_IMAGE="${IMAGE_NAME}:${TAG}-slim"

echo "=== Docker Slim Image Compression ==="
echo "Original image: ${IMAGE_NAME}:${TAG}"
echo "Target image: ${SLIM_IMAGE}"
echo ""

# 检查原始镜像是否存在
if ! docker image inspect "${IMAGE_NAME}:${TAG}" --format "{{.Id}}" > /dev/null 2>&1; then
    echo "Error: Image ${IMAGE_NAME}:${TAG} not found. Please build it first with ./build.sh"
    exit 1
fi

# 获取原始镜像大小
original_size=$(docker image inspect "${IMAGE_NAME}:${TAG}" --format "{{.Size}}")
echo "Original image size: $(echo $original_size | awk '{printf "%.2f MB", $1/1024/1024}')"

# 运行 docker slim
echo ""
echo "Running docker-slim build..."
echo "This may take several minutes..."
echo ""

docker slim build \
    --target "${IMAGE_NAME}:${TAG}" \
    --tag "${SLIM_IMAGE}" \
    --http-probe \
    --http-probe-port 80 \
    --http-probe-cmd "curl -sf http://localhost/api/sessions/status" \
    --exclude-path "/app/data" \
    --include-path "/app/backend" \
    --include-path "/app/frontend/dist" \
    --env HEADLESS=true \
    --continue-after-failure 3

# 检查压缩是否成功
if [ $? -ne 0 ]; then
    echo "Error: Docker slim failed"
    exit 1
fi

# 获取压缩后镜像大小
slim_size=$(docker image inspect "${SLIM_IMAGE}" --format "{{.Size}}")

# 显示大小对比
echo ""
echo "=== Image Size Comparison ==="
echo "Original image: $(echo $original_size | awk '{printf "%.2f MB", $1/1024/1024}')"
echo "Slim image:    $(echo $slim_size | awk '{printf "%.2f MB", $1/1024/1024}')"

# 计算压缩比
original_mb=$(echo "$original_size" | awk '{print int($1/(1024*1024))}')
slim_mb=$(echo "$slim_size" | awk '{print int($1/(1024*1024))}')
if [ -n "$original_mb" ] && [ -n "$slim_mb" ] && [ "$original_mb" -gt 0 ]; then
    reduction=$(echo "scale=2; print ($original_mb - $slim_mb) * 100 / $original_mb" | bc -l)
    echo "Size reduction: ${reduction}%"
fi

echo ""
echo "=== Slim build complete ==="
echo ""
echo "To run the slim image:"
echo "  docker compose up -d"
echo ""
echo "Or directly:"
echo "  docker run -d -p 80:80 -v \$(pwd)/data:/app/data ${SLIM_IMAGE}"
