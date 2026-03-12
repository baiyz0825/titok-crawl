## ADDED Requirements

### Requirement: Session management API
系统 SHALL 提供会话管理相关的 REST API 端点。

#### Scenario: Trigger login
- **WHEN** POST /api/sessions/login
- **THEN** 启动二维码登录流程，返回登录状态

#### Scenario: Check login status
- **WHEN** GET /api/sessions/status
- **THEN** 返回当前登录状态（logged_in: true/false）

### Requirement: User scraping API
系统 SHALL 提供用户采集相关的 REST API 端点。

#### Scenario: Submit scrape task
- **WHEN** POST /api/users/scrape { sec_user_id, options }
- **THEN** 创建采集任务并返回 task_id

#### Scenario: List scraped users
- **WHEN** GET /api/users?page=1&size=20
- **THEN** 返回分页的已采集用户列表

#### Scenario: Get user detail
- **WHEN** GET /api/users/{sec_user_id}
- **THEN** 返回用户详细信息

### Requirement: Works query API
系统 SHALL 提供作品查询相关的 REST API 端点。

#### Scenario: List works with filters
- **WHEN** GET /api/works?sec_user_id=xxx&type=video&page=1&size=20
- **THEN** 返回筛选和分页后的作品列表

#### Scenario: Get work detail
- **WHEN** GET /api/works/{aweme_id}
- **THEN** 返回作品详情及关联的媒体文件信息

### Requirement: Task management API
系统 SHALL 提供任务管理相关的 REST API 端点。

#### Scenario: List tasks
- **WHEN** GET /api/tasks?status=running
- **THEN** 返回筛选后的任务列表

#### Scenario: Cancel task
- **WHEN** POST /api/tasks/{id}/cancel
- **THEN** 取消指定任务

### Requirement: Analysis API
系统 SHALL 提供数据分析相关的 REST API 端点。

#### Scenario: User analysis
- **WHEN** GET /api/analysis/user/{sec_user_id}
- **THEN** 返回该用户的数据分析报告（JSON）

#### Scenario: Overview
- **WHEN** GET /api/analysis/overview
- **THEN** 返回系统总览统计数据
