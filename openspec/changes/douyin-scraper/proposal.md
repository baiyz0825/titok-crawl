## Why

需要一个个人使用的抖音平台自动化数据采集工具，支持用户资料、作品列表、媒体文件的采集与本地存储，并通过 Web 界面和 MCP API 进行管理。当前无此类工具，手动采集效率极低。

## What Changes

- 新建完整的抖音数据采集后端服务（FastAPI + Playwright + SQLite）
- 新建 Vue3 Web 管理前端
- 新建 MCP SSE Server 支持 AI 客户端调用
- 新建 asyncio + SQLite 轻量级任务队列
- 支持二维码登录、Cookie 持久化、反检测
- 支持 `page.route()` 拦截 API 响应获取结构化数据
- 小黄车/橱窗商品功能标注为 **不可用**（Web 端无商品 API，仅 App 端支持）

## Capabilities

### New Capabilities
- `scraper-engine`: Playwright 浏览器引擎，包括浏览器生命周期管理、Cookie 持久化、反检测注入、API 响应拦截
- `user-scraper`: 用户资料采集、作品列表采集（视频/图文区分）、搜索发现
- `media-downloader`: 视频/图片文件下载到本地，断点续传，下载状态追踪
- `task-queue`: asyncio + SQLite 持久化任务队列、调度器、状态追踪、自动重试
- `data-storage`: SQLite 数据库（users/works/media_files/tasks/sessions 表）、pandas 数据分析
- `rest-api`: FastAPI REST API 服务（用户/作品/任务/会话管理端点）
- `mcp-server`: MCP SSE Server 提供 AI 客户端可调用的 Tools
- `web-frontend`: Vue3 Web 管理界面（Dashboard/用户/作品/任务/会话页面）

### Modified Capabilities

（无已有能力需要修改，这是全新项目）

## Impact

- 新增 Python 后端依赖：fastapi, uvicorn, playwright, playwright-stealth, aiosqlite, pandas, pydantic
- 新增前端依赖：vue3, vite, axios, vue-router, element-plus
- 需要本地 Chromium 浏览器（Playwright 自动安装）
- 数据存储在 `data/db/douyin.db` 和 `data/media/` 目录
- 服务端口：8000 (API) / 8001 (MCP)
