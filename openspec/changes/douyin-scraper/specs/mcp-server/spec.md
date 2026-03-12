## ADDED Requirements

### Requirement: MCP SSE transport
系统 SHALL 提供基于 SSE 的 MCP Server，供 AI 客户端连接。

#### Scenario: MCP server startup
- **WHEN** 应用启动
- **THEN** 在端口 8001 启动 MCP SSE Server，注册所有可用 Tools

### Requirement: MCP scrape tools
系统 SHALL 通过 MCP 暴露采集相关的 Tools。

#### Scenario: scrape_user tool
- **WHEN** AI 客户端调用 scrape_user(sec_user_id)
- **THEN** 提交用户采集任务，返回 task_id

#### Scenario: scrape_user_works tool
- **WHEN** AI 客户端调用 scrape_user_works(sec_user_id, max_pages)
- **THEN** 提交作品采集任务，返回 task_id

#### Scenario: search_users tool
- **WHEN** AI 客户端调用 search_users(keyword)
- **THEN** 提交搜索任务，返回 task_id

### Requirement: MCP query tools
系统 SHALL 通过 MCP 暴露数据查询相关的 Tools。

#### Scenario: get_user_info tool
- **WHEN** AI 客户端调用 get_user_info(sec_user_id)
- **THEN** 返回已采集的用户信息

#### Scenario: get_works tool
- **WHEN** AI 客户端调用 get_works(sec_user_id, type, page, size)
- **THEN** 返回已采集的作品列表

#### Scenario: get_task_status tool
- **WHEN** AI 客户端调用 get_task_status(task_id)
- **THEN** 返回任务当前状态和进度

#### Scenario: analyze_user tool
- **WHEN** AI 客户端调用 analyze_user(sec_user_id)
- **THEN** 返回用户数据分析报告
