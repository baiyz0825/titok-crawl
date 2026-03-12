# 抖音数据采集工具 - 设计文档

## 1. 项目概述

个人使用的抖音平台自动化数据采集工具，基于 Playwright 浏览器自动化，通过拦截 API 响应获取结构化数据。

### 1.1 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 用户资料采集 | ✅ 可行 | 粉丝数、获赞、简介、认证信息等 |
| 用户作品采集 | ✅ 可行 | 视频/图文列表、互动数据、分页遍历 |
| 作品媒体下载 | ✅ 可行 | 视频/图片文件下载到本地 |
| 搜索发现 | ✅ 可行 | 关键词搜索用户/作品（需处理 CAPTCHA） |
| 小黄车/橱窗商品 | ❌ Web 端不可用 | 仅 App/客户端支持，Web 版无商品 API |
| 直播商品 | ❌ Web 端不可用 | 同上 |

### 1.2 小黄车/橱窗调研结论

通过 Chrome DevTools 实际调研确认：
- Web 版 `douyin.com` 用户主页无"橱窗"tab
- `/mall/item/*` 路由存在但页面内容为空，不加载商品数据
- 视频详情页 SSR 数据中无商品关联字段（如 `product_id`、`commerce_info`）
- 所有 API 请求中均无 `/product/`、`/shop/`、`/goods/`、`/ecommerce/` 相关端点
- **结论**：电商/商品功能仅在移动端 App 中实现，纯 Web Playwright 方案无法采集
- **备选**：如未来需要商品数据，需改用移动端抓包方案（如 mitmproxy + 手机模拟器）

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue3 + Vite | Web 管理界面 |
| 后端 | FastAPI (Python 3.11+) | 异步 API 服务 |
| 采集引擎 | Playwright (Chromium) | 浏览器自动化 + API 拦截 |
| 反检测 | playwright-stealth | 隐藏 webdriver 指纹 |
| 数据库 | SQLite + aiosqlite | 结构化存储 |
| 数据分析 | pandas | 行为分析和数据统计 |
| 任务队列 | asyncio + SQLite | 轻量级持久化任务队列 |
| AI 接口 | MCP Server (SSE) | 支持 AI 客户端调用 |

## 3. 系统架构

```
┌─────────────────────────────────────────────────┐
│                  Client Layer                    │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐ │
│  │ Vue3 Web │  │ REST API  │  │ MCP Server   │ │
│  │ 管理界面  │  │ (Swagger) │  │ (SSE)        │ │
│  └────┬─────┘  └─────┬─────┘  └──────┬───────┘ │
│       │              │               │          │
│       └──────────────┼───────────────┘          │
│                      ▼                          │
│  ┌───────────────────────────────────────────┐  │
│  │         FastAPI Service Layer              │  │
│  │  Unified API Router + Auth Middleware      │  │
│  └─────────────────┬─────────────────────────┘  │
│                    ▼                             │
│  ┌───────────────────────────────────────────┐  │
│  │         Task Queue (asyncio + SQLite)      │  │
│  │  调度器 → 任务分发 → 状态追踪 → 重试      │  │
│  └─────────────────┬─────────────────────────┘  │
│                    ▼                             │
│  ┌───────────────────────────────────────────┐  │
│  │       Playwright Scraping Engine           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ │  │
│  │  │ Browser  │ │ Cookie   │ │ Anti-Det   │ │  │
│  │  │ Pool     │ │ Manager  │ │ Module     │ │  │
│  │  └──────────┘ └──────────┘ └───────────┘ │  │
│  │  ┌──────────────────────────────────────┐ │  │
│  │  │            Scrapers                   │ │  │
│  │  │  UserProfile │ UserWorks │ Search     │ │  │
│  │  │  MediaDown   │ WorkDetail│            │ │  │
│  │  └──────────────────────────────────────┘ │  │
│  └─────────────────┬─────────────────────────┘  │
│                    ▼                             │
│  ┌───────────────────────────────────────────┐  │
│  │            Data Layer                      │  │
│  │  SQLite DB │ pandas Analysis │ File Store  │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## 4. 已确认的 API 端点

通过 Chrome DevTools 实际抓包确认：

### 4.1 核心数据 API

| 端点 | 用途 | 关键参数 |
|------|------|----------|
| `/aweme/v1/web/user/profile/other/` | 用户资料 | `sec_user_id` |
| `/aweme/v1/web/aweme/post/` | 作品列表 | `sec_user_id`, `max_cursor`, `count=18` |
| `/aweme/v1/web/aweme/detail/` | 作品详情 | `aweme_id` |
| `/aweme/v1/web/comment/list/` | 评论列表 | `aweme_id` |
| `/aweme/v1/web/discover/search/` | 搜索 | `keyword` |
| `/aweme/v1/web/social/count` | 社交统计 | `sec_user_id` |
| `/aweme/v1/web/mix/listcollection/` | 合集列表 | `cursor`, `count=20` |

### 4.2 辅助 API

| 端点 | 用途 |
|------|------|
| `/aweme/v1/web/profile/record/` | 用户档案记录 |
| `/aweme/v1/web/hot/search/list/` | 热搜榜 |
| `/aweme/v1/web/seo/inner/link/` | SEO 内链 |
| `/aweme/v1/web/query/account/type/` | 账号类型 |
| `/aweme/v1/web/suggest_words/` | 搜索建议词 |
| `/aweme/v1/web/danmaku/conf/get/` | 弹幕配置 |

### 4.3 登录相关

| 端点 | 用途 |
|------|------|
| `/passport/web/get_qrcode/` | 获取二维码 |
| `/passport/web/check_qrconnect/` | 轮询扫码状态 |

### 4.4 请求签名参数

所有 API 请求需携带以下参数（从浏览器环境自动获取）：
- `device_platform=webapp`
- `aid=6383`
- `channel=channel_pc_web`
- `update_version_code=170400`
- `pc_client_type=1`
- `msToken` — 安全令牌（Cookie 中获取）
- `a_bogus` — 签名参数（JS 运行时生成）
- `verifyFp` — 指纹验证

**核心策略**：使用 `page.route()` 拦截 API 响应，无需自行构造签名参数。

## 5. 数据库设计

### 5.1 users 表

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sec_user_id TEXT UNIQUE NOT NULL,     -- 用户唯一标识
    uid TEXT,                              -- 数字 UID
    nickname TEXT,
    avatar_url TEXT,
    signature TEXT,                        -- 个人简介
    douyin_id TEXT,                        -- 抖音号
    location TEXT,                         -- 地区
    follower_count INTEGER DEFAULT 0,      -- 粉丝数
    following_count INTEGER DEFAULT 0,     -- 关注数
    total_favorited INTEGER DEFAULT 0,     -- 获赞数
    aweme_count INTEGER DEFAULT 0,         -- 作品数
    is_verified BOOLEAN DEFAULT FALSE,     -- 是否认证
    verification_type TEXT,                -- 认证类型
    extra_data TEXT,                       -- JSON 扩展字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 works 表

```sql
CREATE TABLE works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aweme_id TEXT UNIQUE NOT NULL,          -- 作品 ID
    sec_user_id TEXT NOT NULL,              -- 作者
    type TEXT NOT NULL CHECK(type IN ('video', 'note')),  -- 视频/图文
    title TEXT,                             -- 标题/描述
    cover_url TEXT,                         -- 封面
    duration INTEGER,                       -- 时长(ms)，图文为 0
    digg_count INTEGER DEFAULT 0,           -- 点赞数
    comment_count INTEGER DEFAULT 0,        -- 评论数
    share_count INTEGER DEFAULT 0,          -- 分享数
    collect_count INTEGER DEFAULT 0,        -- 收藏数
    play_count INTEGER DEFAULT 0,           -- 播放量
    hashtags TEXT,                          -- JSON 数组: ["tag1", "tag2"]
    music_title TEXT,                       -- 背景音乐
    publish_time TIMESTAMP,                 -- 发布时间
    extra_data TEXT,                        -- JSON 扩展字段
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sec_user_id) REFERENCES users(sec_user_id)
);
```

### 5.3 media_files 表

```sql
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aweme_id TEXT NOT NULL,                 -- 关联作品
    media_type TEXT NOT NULL CHECK(media_type IN ('video', 'image', 'cover')),
    url TEXT NOT NULL,                      -- 原始 URL
    local_path TEXT,                        -- 本地存储路径
    file_size INTEGER,                      -- 文件大小(bytes)
    download_status TEXT DEFAULT 'pending'
        CHECK(download_status IN ('pending', 'downloading', 'completed', 'failed')),
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id)
);
```

### 5.4 tasks 表

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,                -- user_profile / user_works / search / media_download
    target TEXT NOT NULL,                   -- sec_user_id / keyword / url
    params TEXT,                            -- JSON 参数
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 0,
    progress REAL DEFAULT 0,               -- 0.0 ~ 1.0
    result TEXT,                            -- JSON 结果摘要
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 5.5 sessions 表

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,             -- 会话名称
    cookies TEXT NOT NULL,                 -- JSON Cookie 数据
    user_agent TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.6 本地文件存储

```
data/
├── media/
│   └── {sec_user_id}/
│       ├── videos/
│       │   └── {aweme_id}.mp4
│       └── notes/
│           └── {aweme_id}/
│               ├── 1.jpg
│               ├── 2.jpg
│               └── ...
└── db/
    └── douyin.db
```

## 6. 核心模块设计

### 6.1 项目目录结构

```
douyin-scraper/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 配置管理
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py              # 统一路由
│   │   ├── users.py               # 用户相关 API
│   │   ├── works.py               # 作品相关 API
│   │   ├── tasks.py               # 任务管理 API
│   │   └── sessions.py            # 会话管理 API
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── engine.py              # Playwright 引擎 (浏览器池+Cookie管理)
│   │   ├── anti_detect.py         # 反检测模块
│   │   ├── interceptor.py         # API 响应拦截器 (page.route)
│   │   ├── user_scraper.py        # 用户资料采集
│   │   ├── works_scraper.py       # 作品列表采集
│   │   ├── search_scraper.py      # 搜索采集
│   │   └── media_downloader.py    # 媒体文件下载
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── scheduler.py           # 任务调度器
│   │   └── worker.py              # 任务执行器
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py            # 数据库连接管理
│   │   ├── models.py              # 数据模型
│   │   └── crud.py                # CRUD 操作
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── server.py              # MCP SSE Server
│   └── analysis/
│       ├── __init__.py
│       └── analyzer.py            # pandas 数据分析
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── views/
│   │   │   ├── Dashboard.vue      # 数据概览
│   │   │   ├── Users.vue          # 用户管理
│   │   │   ├── Works.vue          # 作品管理
│   │   │   ├── Tasks.vue          # 任务管理
│   │   │   └── Sessions.vue       # 会话管理
│   │   ├── components/
│   │   └── api/
│   ├── vite.config.ts
│   └── package.json
├── data/                          # 运行时数据（gitignore）
│   ├── db/
│   └── media/
├── requirements.txt
└── README.md
```

### 6.2 Playwright 引擎 (engine.py)

核心职责：浏览器生命周期管理 + Cookie 持久化 + 反检测注入。

```python
class ScraperEngine:
    """单浏览器实例管理（个人小规模使用）"""

    async def start(self):
        """启动浏览器，注入反检测，加载已保存的 Cookie"""

    async def stop(self):
        """保存 Cookie，关闭浏览器"""

    async def get_page(self) -> Page:
        """获取可用页面，复用或新建 tab"""

    async def save_cookies(self, name: str):
        """将当前 Cookie 保存到 sessions 表"""

    async def load_cookies(self, name: str):
        """从 sessions 表加载 Cookie"""

    async def check_login(self) -> bool:
        """检测登录状态"""

    async def wait_for_login(self):
        """展示二维码，等待用户扫码登录"""
```

### 6.3 API 响应拦截器 (interceptor.py)

核心数据获取策略：不直接调用 API（避免签名），而是拦截浏览器自动发出的请求。

```python
class ResponseInterceptor:
    """使用 page.route() 拦截 API 响应"""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}  # pattern -> callback
        self._responses: asyncio.Queue = asyncio.Queue()

    async def setup(self, page: Page):
        """注册路由拦截"""
        await page.route("**/aweme/v1/web/**", self._on_route)

    async def _on_route(self, route: Route):
        """拦截响应：放行请求，捕获响应 JSON"""
        response = await route.fetch()
        body = await response.json()
        await self._responses.put({
            'url': route.request.url,
            'data': body
        })
        await route.fulfill(response=response)

    async def wait_for(self, pattern: str, timeout: float = 30) -> dict:
        """等待匹配指定 pattern 的 API 响应"""
```

### 6.4 用户采集 (user_scraper.py)

```python
class UserScraper:
    async def scrape_profile(self, sec_user_id: str) -> UserProfile:
        """
        1. 导航到 /user/{sec_user_id}
        2. 拦截 /user/profile/other/ 响应
        3. 解析并存储到 users 表
        """

    async def scrape_works(self, sec_user_id: str, max_pages: int = None) -> list[Work]:
        """
        1. 导航到用户主页
        2. 拦截 /aweme/post/ 响应（首页 18 条）
        3. 滚动加载更多，持续拦截（max_cursor 分页）
        4. 区分 video / note 类型
        5. 存储到 works 表
        """

    async def scrape_all(self, sec_user_id: str):
        """采集用户资料 + 全部作品 + 媒体下载"""
```

### 6.5 任务队列 (scheduler.py)

```python
class TaskScheduler:
    """基于 asyncio + SQLite 的轻量级任务调度器"""

    async def start(self):
        """启动调度循环，恢复未完成任务"""

    async def submit(self, task_type: str, target: str, **params) -> int:
        """提交新任务，返回 task_id"""

    async def _run_loop(self):
        """
        持续循环:
        1. 从 tasks 表取 pending 任务（按 priority 排序）
        2. 分发给对应 Scraper
        3. 更新进度和状态
        4. 失败自动重试（max_retries=3）
        5. 控制并发数和请求间隔（防风控）
        """

    async def cancel(self, task_id: int):
        """取消任务"""

    async def get_status(self, task_id: int) -> TaskStatus:
        """获取任务状态"""
```

## 7. API 设计

### 7.1 REST API

```
# 会话管理
POST   /api/sessions/login          # 触发二维码登录
GET    /api/sessions/status          # 登录状态检查
GET    /api/sessions                 # 会话列表

# 用户
POST   /api/users/scrape             # 提交用户采集任务
GET    /api/users                    # 已采集用户列表
GET    /api/users/{sec_user_id}      # 用户详情

# 作品
GET    /api/works                    # 作品列表（支持筛选）
GET    /api/works/{aweme_id}         # 作品详情
GET    /api/works/{aweme_id}/media   # 媒体文件列表

# 搜索
POST   /api/search                   # 提交搜索任务

# 任务
GET    /api/tasks                    # 任务列表
GET    /api/tasks/{id}               # 任务详情
POST   /api/tasks/{id}/cancel        # 取消任务
POST   /api/tasks/{id}/retry         # 重试任务

# 数据分析
GET    /api/analysis/user/{sec_user_id}   # 用户数据分析报告
GET    /api/analysis/overview             # 数据总览
```

### 7.2 MCP Server (SSE)

提供以下 MCP Tools 供 AI 客户端调用：

| Tool | 说明 |
|------|------|
| `scrape_user` | 采集指定用户资料 |
| `scrape_user_works` | 采集用户作品列表 |
| `search_users` | 搜索用户 |
| `get_user_info` | 查询已采集的用户信息 |
| `get_works` | 查询已采集的作品 |
| `get_task_status` | 查询任务状态 |
| `analyze_user` | 获取用户数据分析 |

## 8. 反检测策略

根据 Chrome DevTools 调研发现的检测点：

| 检测项 | 风险 | 应对方案 |
|--------|------|----------|
| `navigator.webdriver` | 致命 | playwright-stealth 覆盖为 `false` |
| Chrome 版本号 | 致命 | 使用真实 Chrome 内核版本号 |
| CDP 调用栈 | 致命 | 避免使用 `evaluate` 暴露栈，用 `addInitScript` |
| 安全 Cookie SDK | 高 | 保持浏览器自然生成，不手动修改 |
| 指纹 Cookie (UIFID/fpk) | 高 | 持久化 Cookie，避免频繁重建浏览器 |
| 请求频率 | 中 | 随机延迟 2-5s，模拟人工浏览节奏 |
| CAPTCHA 滑块 | 中 | 检测到时暂停任务，通知用户手动处理 |

## 9. 关键流程

### 9.1 首次启动流程

```
启动 FastAPI → 初始化 DB → 启动 Playwright 引擎
    → 检查 Cookie → 无有效 Cookie → 展示二维码
    → 用户扫码登录 → 保存 Cookie → 启动任务调度器
```

### 9.2 用户采集流程

```
提交采集任务 (sec_user_id)
    → 任务入队 (tasks 表)
    → 调度器分配执行
    → 导航到用户主页
    → 拦截 /user/profile/other/ → 存储用户资料
    → 拦截 /aweme/post/ → 存储作品列表
    → 滚动加载 → 拦截更多 /aweme/post/（max_cursor 分页）
    → 遍历作品 → 提取视频/图片 URL
    → 提交媒体下载子任务
    → 更新任务状态为 completed
```

### 9.3 媒体下载流程

```
媒体下载任务
    → 检查 media_files 表（避免重复下载）
    → 创建目录 data/media/{sec_user_id}/videos/ 或 notes/
    → 下载文件（支持断点续传）
    → 更新 local_path 和 download_status
    → 失败自动重试
```

## 10. 配置项

```python
# config.py
class Settings:
    # 数据库
    DB_PATH = "data/db/douyin.db"

    # 媒体存储
    MEDIA_DIR = "data/media"

    # Playwright
    HEADLESS = False              # 首次使用需要扫码，建议 False
    BROWSER_DATA_DIR = "data/browser"  # 浏览器数据持久化

    # 请求控制
    MIN_DELAY = 2.0               # 最小请求间隔(秒)
    MAX_DELAY = 5.0               # 最大请求间隔(秒)
    MAX_RETRIES = 3               # 最大重试次数
    REQUEST_TIMEOUT = 30          # 请求超时(秒)

    # 任务队列
    MAX_CONCURRENT_TASKS = 1      # 最大并发任务数（小规模使用）

    # 服务端口
    API_PORT = 8000
    MCP_PORT = 8001
```

## 11. 开发阶段规划

### Phase 1: 基础架构
- FastAPI 项目骨架 + SQLite 数据库初始化
- Playwright 引擎 + Cookie 管理 + 反检测
- 二维码登录流程

### Phase 2: 核心采集
- API 响应拦截器
- 用户资料采集
- 作品列表采集（视频/图文区分）
- 媒体文件下载

### Phase 3: 任务系统
- SQLite 任务队列
- 调度器 + Worker
- 任务状态管理 + 重试机制

### Phase 4: API + MCP
- REST API 完整实现
- MCP SSE Server
- Swagger 文档

### Phase 5: 前端界面
- Vue3 项目搭建
- 数据概览 Dashboard
- 用户/作品管理页面
- 任务管理页面

### Phase 6: 数据分析
- pandas 数据分析模块
- 用户行为分析报告
- 数据导出功能
