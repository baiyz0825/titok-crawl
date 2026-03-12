#!/bin/bash

# Playwright 安装修复脚本

echo "=== Playwright 安装修复 ==="
echo ""

# 激活虚拟环境
echo "1. 激活虚拟环境..."
source .venv/bin/activate

# 方案 1: 使用官方 CDN (推荐)
echo "2. 尝试使用官方 CDN 下载..."
export PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net
export PLAYWRIGHT_BROWSERS_PATH=0

# 如果之前设置了代理，保留代理设置
if [ -n "$http_proxy" ]; then
    echo "使用现有代理配置：$http_proxy"
fi

echo "3. 开始安装 Chromium..."
playwright install chromium

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Chromium 安装成功！"
    echo ""
    echo "如需安装其他浏览器，可执行："
    echo "  playwright install firefox"
    echo "  playwright install webkit"
else
    echo ""
    echo "❌ 安装失败，尝试使用国内镜像..."
    echo ""
    
    # 方案 2: 使用正确的镜像地址
    export PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/download
    echo "4. 使用 npmmirror 镜像重新尝试..."
    playwright install chromium
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Chromium 安装成功！"
    else
        echo ""
        echo "❌ 仍然失败，请检查网络连接或代理配置"
        echo ""
        echo "建议："
        echo "1. 检查代理是否可用：curl -I http://192.168.10.29:7890"
        echo "2. 直接使用官方源（需要科学上网）"
        echo "3. 手动下载浏览器并放到本地缓存目录"
    fi
fi

# 验证安装
echo ""
echo "5. 验证安装..."
python -c "from playwright.sync_api import sync_playwright; print('Playwright 可以正常导入！')"
