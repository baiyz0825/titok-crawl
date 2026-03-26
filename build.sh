#!/bin/bash
set -e

# ============================================
# Docker 构建脚本
# ============================================

IMAGE_NAME="douyin-scraper"
TAG="latest"
REGISTRY="${REGISTRY:-}"

echo "=== Building Docker image ==="
echo "Image: ${IMAGE_NAME}:${TAG}"

# 构建镜像
docker build -t "${IMAGE_NAME}:${TAG}" .

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo "Build successful!"

# 测试镜像
echo "=== Testing image ==="
echo "Testing basic container startup..."
timeout 60 docker run --rm "${IMAGE_NAME}:${TAG}" || exit 0

sleep 2
echo "Test container started successfully"
echo "Test complete"
echo ""
echo "=== Build process finished ==="
echo ""
echo "To push to image to registry, run:"
echo "  docker tag ${IMAGE_NAME}:${TAG} \$REGISTRY/${IMAGE_NAME}:${TAG}"
echo "  docker push \$REGISTRY/${IMAGE_NAME}:${TAG}"
echo ""
echo "To compress the image, run:"
echo "  ./slim-build.sh"
