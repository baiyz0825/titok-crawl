#!/bin/sh
set -e

# 如果 shared volume 挂载了 /shared/html，把前端 dist 复制过去供 Nginx 使用
if [ -d "/shared/html" ]; then
    echo "Copying frontend dist to shared volume..."
    cp -r /app/frontend/dist/* /shared/html/
    echo "Frontend dist ready for Nginx"
fi

exec "$@"
