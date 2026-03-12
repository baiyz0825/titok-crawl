## ADDED Requirements

### Requirement: Dashboard page
系统 SHALL 提供数据总览 Dashboard 页面。

#### Scenario: Show overview statistics
- **WHEN** 用户访问 Dashboard
- **THEN** 展示已采集用户数、作品数、媒体文件数、运行中/已完成任务数

#### Scenario: Show login status
- **WHEN** 用户访问 Dashboard
- **THEN** 展示当前登录状态，未登录时提供登录入口

### Requirement: Users management page
系统 SHALL 提供用户管理页面。

#### Scenario: List users
- **WHEN** 用户访问用户管理页面
- **THEN** 展示已采集用户列表（头像、昵称、粉丝数、作品数），支持分页

#### Scenario: Trigger user scrape
- **WHEN** 用户输入 sec_user_id 并点击采集
- **THEN** 提交采集任务并展示任务状态

### Requirement: Works management page
系统 SHALL 提供作品管理页面。

#### Scenario: List works with filters
- **WHEN** 用户访问作品管理页面
- **THEN** 展示作品列表（封面、标题、类型、互动数据），支持按用户和类型筛选

### Requirement: Tasks management page
系统 SHALL 提供任务管理页面。

#### Scenario: List tasks with status
- **WHEN** 用户访问任务管理页面
- **THEN** 展示任务列表（类型、目标、状态、进度、创建时间），支持取消和重试

### Requirement: Sessions management page
系统 SHALL 提供会话管理页面。

#### Scenario: QR login
- **WHEN** 用户点击登录按钮
- **THEN** 打开浏览器窗口展示二维码，用户扫码后更新登录状态
