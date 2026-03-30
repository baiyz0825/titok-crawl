#!/bin/sh
set -e

echo "=== Douyin Scraper All-in-One Container ==="

# 创建数据目录
mkdir -p /app/data/db /app/data/media

# 启动 supervisord (管理所有进程)
echo "Starting services with supervisor..."
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf
