## 1. Project Setup

- [x] 1.1 Initialize Python project structure: create `backend/` directory with `__init__.py` files for `api/`, `scraper/`, `queue/`, `db/`, `mcp/`, `analysis/` packages
- [x] 1.2 Create `requirements.txt` with dependencies: fastapi, uvicorn, playwright, playwright-stealth, aiosqlite, pandas, pydantic, httpx, mcp[server]
- [x] 1.3 Create `backend/config.py` with Settings class (DB_PATH, MEDIA_DIR, BROWSER_DATA_DIR, delays, ports, etc.)
- [x] 1.4 Run `pip install -r requirements.txt && playwright install chromium` to install dependencies

## 2. Database Layer

- [x] 2.1 Create `backend/db/database.py`: async SQLite connection manager using aiosqlite, auto-create DB file and directory
- [x] 2.2 Create `backend/db/models.py`: Pydantic models for User, Work, MediaFile, Task, Session with proper type hints
- [x] 2.3 Create `backend/db/crud.py`: CRUD operations — create_tables(), upsert_user(), upsert_work(), create_media_file(), create_task(), update_task(), get_users(), get_works(), get_tasks(), get_session(), save_session()
- [x] 2.4 Write and run test: verify database initialization creates all 5 tables with correct schemas

## 3. Scraper Engine

- [x] 3.1 Create `backend/scraper/anti_detect.py`: playwright-stealth injection wrapper, addInitScript to hide webdriver flag and fix Chrome version
- [x] 3.2 Create `backend/scraper/engine.py`: ScraperEngine class with start(), stop(), get_page(), save_cookies(), load_cookies(), check_login(), wait_for_login() methods using persistent browser context
- [x] 3.3 Create `backend/scraper/interceptor.py`: ResponseInterceptor class with setup(page), _on_route(route), wait_for(pattern, timeout) using asyncio.Queue for captured responses
- [x] 3.4 Test engine: start browser, verify anti-detection, navigate to douyin.com, verify page loads

## 4. User & Works Scrapers

- [x] 4.1 Create `backend/scraper/user_scraper.py`: UserScraper with scrape_profile(sec_user_id) — navigate to user page, intercept profile API, parse and store to DB
- [x] 4.2 Add scrape_works(sec_user_id, max_pages) to UserScraper — intercept /aweme/post/ responses, scroll for pagination via max_cursor, distinguish video/note by aweme_type, store to works table
- [x] 4.3 Create `backend/scraper/search_scraper.py`: SearchScraper with search(keyword, type) — navigate to search page, intercept search API, detect CAPTCHA and pause if triggered
- [x] 4.4 Test user scraper: scrape a known user profile and verify data in DB

## 5. Media Downloader

- [x] 5.1 Create `backend/scraper/media_downloader.py`: MediaDownloader with download_video(aweme_id, url, sec_user_id) and download_images(aweme_id, urls, sec_user_id) — download files to data/media/{sec_user_id}/videos/ or notes/, update media_files table
- [x] 5.2 Add skip-existing logic: check media_files table before downloading, skip if status=completed and file exists
- [x] 5.3 Test downloader: download a video and images, verify files on disk and DB records

## 6. Task Queue

- [x] 6.1 Create `backend/queue/worker.py`: TaskWorker that maps task_type to corresponding scraper method (user_profile → UserScraper.scrape_profile, user_works → scrape_works, search → SearchScraper.search, media_download → MediaDownloader)
- [x] 6.2 Create `backend/queue/scheduler.py`: TaskScheduler with start(), submit(), cancel(), _run_loop() — poll tasks table, dispatch to worker, handle retries (max 3), random delay 2-5s between tasks, recover running→pending on restart
- [x] 6.3 Test scheduler: submit a task, verify it gets picked up, executed, and status updated to completed

## 7. FastAPI REST API

- [x] 7.1 Create `backend/main.py`: FastAPI app with lifespan (startup: init DB + start engine + start scheduler, shutdown: stop engine)
- [x] 7.2 Create `backend/api/sessions.py`: POST /api/sessions/login, GET /api/sessions/status endpoints
- [x] 7.3 Create `backend/api/users.py`: POST /api/users/scrape, GET /api/users, GET /api/users/{sec_user_id} endpoints
- [x] 7.4 Create `backend/api/works.py`: GET /api/works (with sec_user_id, type, page, size filters), GET /api/works/{aweme_id} endpoints
- [x] 7.5 Create `backend/api/tasks.py`: GET /api/tasks, GET /api/tasks/{id}, POST /api/tasks/{id}/cancel, POST /api/tasks/{id}/retry endpoints
- [x] 7.6 Create `backend/api/router.py`: aggregate all API routers with /api prefix
- [x] 7.7 Create `backend/analysis/analyzer.py`: UserAnalyzer with analyze_user(sec_user_id) and get_overview() using pandas
- [x] 7.8 Create `backend/api/analysis.py`: GET /api/analysis/user/{sec_user_id}, GET /api/analysis/overview endpoints
- [x] 7.9 Test API: start server, verify Swagger docs at /docs, test key endpoints with httpx

## 8. MCP Server

- [x] 8.1 Create `backend/mcp/server.py`: MCP SSE Server on port 8001, register tools: scrape_user, scrape_user_works, search_users, get_user_info, get_works, get_task_status, analyze_user
- [x] 8.2 Integrate MCP server startup into FastAPI lifespan (run in background asyncio task)
- [x] 8.3 Test MCP: verify SSE endpoint responds and tools are listed

## 9. Vue3 Frontend

- [x] 9.1 Initialize Vue3 + Vite + TypeScript project in `frontend/`, install element-plus, vue-router, axios
- [x] 9.2 Create `frontend/src/api/client.ts`: axios instance with baseURL /api, request/response interceptors
- [x] 9.3 Create `frontend/src/router/index.ts`: routes for Dashboard, Users, Works, Tasks, Sessions
- [x] 9.4 Create `frontend/src/views/Dashboard.vue`: overview statistics cards (users, works, media, tasks), login status indicator
- [x] 9.5 Create `frontend/src/views/Users.vue`: user list table with pagination, scrape input form, user detail drawer
- [x] 9.6 Create `frontend/src/views/Works.vue`: works list with cover thumbnails, type/user filter, pagination
- [x] 9.7 Create `frontend/src/views/Tasks.vue`: tasks table with status badges, cancel/retry buttons, auto-refresh
- [x] 9.8 Create `frontend/src/views/Sessions.vue`: login status display, login trigger button
- [x] 9.9 Create `frontend/src/App.vue`: layout with sidebar navigation
- [x] 9.10 Add proxy config in `vite.config.ts` to forward /api to backend port 8000
- [x] 9.11 Test frontend: npm run dev, verify all pages render and API calls work

## 10. Integration & Polish

- [x] 10.1 Create startup script `run.sh`: start backend (uvicorn) and frontend (vite dev) together
- [ ] 10.2 End-to-end test: login via QR → scrape a user → view works → download media → verify in frontend
- [x] 10.3 Add error handling: global exception handler in FastAPI, toast notifications in frontend for task errors
