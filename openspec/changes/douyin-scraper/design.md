## Context

全新项目，为个人使用的抖音数据采集工具。通过 Chrome DevTools 实际调研已确认：
- 抖音 Web 端所有数据获取需要登录（Cookie 认证）
- 核心数据通过 `/aweme/v1/web/*` API 端点以 JSON 返回
- API 请求需要 `a_bogus`、`msToken` 等签名参数（由浏览器 JS 运行时生成）
- 检测到 `navigator.webdriver`、Chrome 版本号、CDP 调用栈等反爬点
- Web 端无商品/橱窗/小黄车 API（仅 App 端可用）
- 搜索会触发滑块 CAPTCHA

## Goals / Non-Goals

**Goals:**
- 使用 Playwright 浏览器自动化 + `page.route()` API 拦截实现数据采集
- 支持用户资料、作品列表（视频/图文区分）、媒体文件下载
- SQLite 结构化存储 + pandas 数据分析
- asyncio + SQLite 持久化任务队列
- FastAPI REST API + MCP SSE Server + Vue3 Web 界面
- Cookie 持久化 + 二维码登录 + playwright-stealth 反检测

**Non-Goals:**
- 商品/橱窗/小黄车数据采集（Web 端不可用）
- 直播间数据采集
- 大规模并发采集（仅个人使用，单浏览器实例）
- 移动端抓包方案
- 自动绕过 CAPTCHA（检测到时通知用户手动处理）

## Decisions

### 1. 数据获取：page.route() 拦截 vs 直接调用 API

**选择**: `page.route()` 拦截浏览器自动发出的 API 请求响应

**理由**: 直接调用 API 需要自行构造 `a_bogus` 签名（复杂的 JS 混淆算法），且签名算法会频繁更新。拦截方式让浏览器自然完成签名，我们只读取响应数据。

**代价**: 需要实际导航页面和滚动触发请求，比直接 API 调用慢。

### 2. 浏览器策略：单实例 vs 浏览器池

**选择**: 单浏览器实例，多 tab 复用

**理由**: 个人小规模使用，单实例已足够。多实例增加 Cookie 同步复杂度和资源消耗。

### 3. 任务队列：asyncio + SQLite vs Redis/Celery

**选择**: asyncio + SQLite

**理由**: 小规模使用无需 Redis 等外部依赖。SQLite 持久化确保重启后任务不丢失。asyncio 原生协程与 Playwright 异步 API 完美配合。

### 4. 前后端通信：REST + WebSocket vs 纯 REST

**选择**: 纯 REST（轮询任务状态）

**理由**: 任务执行时间较长（秒级），前端轮询间隔 2-3s 完全可接受。WebSocket 增加复杂度但收益不大。

### 5. 反检测：playwright-stealth + 持久化浏览器数据目录

**选择**: 使用 `playwright-stealth` 库 + `persistent context`（保存浏览器数据目录）

**理由**: stealth 库覆盖 webdriver 检测、Chrome 版本伪装等。持久化数据目录保留指纹 Cookie（UIFID 等），避免每次启动都被识别为新设备。

## Risks / Trade-offs

- **[抖音 API 变更]** → API 端点和参数可能随版本更新变化。缓解：拦截方式自动适配 URL 变化，只需更新解析逻辑。
- **[签名算法更新]** → 不影响，因为我们用浏览器原生请求，不自行构造签名。
- **[CAPTCHA 触发]** → 频繁操作或指纹异常触发滑块验证。缓解：随机延迟 2-5s、持久化浏览器数据、检测到 CAPTCHA 时暂停任务通知用户。
- **[Cookie 过期]** → 登录态可能过期。缓解：每次操作前检查登录状态，过期时自动提示重新登录。
- **[单点故障]** → 单浏览器实例崩溃导致所有任务中断。缓解：任务队列持久化，重启后自动恢复未完成任务。
