#!/bin/bash
set -e

# ============================================
# Docker 多架构构建脚本
# 支持 amd64/arm64 架构，推送到 ghcr.io
# ============================================

IMAGE_NAME="titok-crawl"
TAG="latest"
REGISTRY="${REGISTRY:-ghcr.io/baiyz0825}"
PLATFORMS="linux/amd64,linux/arm64"

# 完整镜像名
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "=========================================="
echo "  Docker 多架构构建"
echo "=========================================="
echo "Image: ${FULL_IMAGE}"
echo "Platforms: ${PLATFORMS}"
echo ""

# 检查 buildx 是否可用
check_buildx() {
    if ! docker buildx version &> /dev/null; then
        echo "Error: docker buildx not available"
        exit 1
    fi
}

# 创建并使用 buildx builder
setup_builder() {
    echo "=== Setting up docker buildx ==="
    docker buildx create --use --name multiarch-builder 2>/dev/null || docker buildx use multiarch-builder
    docker buildx inspect --bootstrap
}

# 多架构构建
build_multiarch() {
    echo ""
    echo "=== Building multi-architecture image ==="

    docker buildx build \
        --platform "${PLATFORMS}" \
        --tag "${FULL_IMAGE}" \
        --push \
        --progress=plain \
        # --no-cache \
        --builder multiarch-builder \
        --annotation "index.org.opencontainers.image.description=Douyin/TikTok video scraper with web UI and MCP support" \
        "$(dirname "$0")/."

    if [ $? -ne 0 ]; then
        echo "Build failed!"
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo "  构建完成!"
    echo "=========================================="
    echo ""
    echo "镜像: ${FULL_IMAGE}"
    echo "架构: ${PLATFORMS}"
    echo ""
    echo "拉取镜像:"
    echo "  docker pull ${FULL_IMAGE}"
    echo ""
    echo "运行镜像:"
    echo "  docker run -d -p 80:80 -v \$(pwd)/data:/app/data ${FULL_IMAGE}"
    echo ""
}

# 主流程
main() {
    check_buildx
    setup_builder
    build_multiarch
}

# 根据参数选择执行
case "${1:-all}" in
    build|all)
        main
        ;;
    *)
        echo "用法: $0 [build]"
        echo "  build - 构建并推送镜像 (默认)"
        ;;
esac
