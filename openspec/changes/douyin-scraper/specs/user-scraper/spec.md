## ADDED Requirements

### Requirement: User profile scraping
系统 SHALL 通过导航到用户主页并拦截 `/aweme/v1/web/user/profile/other/` API 响应来采集用户资料。

#### Scenario: Scrape user profile
- **WHEN** 调用 scrape_profile(sec_user_id)
- **THEN** 导航到 `https://www.douyin.com/user/{sec_user_id}`，拦截 profile API 响应，解析并存储到 users 表（nickname、follower_count、following_count、total_favorited、aweme_count、signature、location、is_verified 等字段）

#### Scenario: User not found
- **WHEN** sec_user_id 无效或用户不存在
- **THEN** 返回错误信息，不写入数据库

### Requirement: User works scraping
系统 SHALL 通过拦截 `/aweme/v1/web/aweme/post/` API 响应来采集用户作品列表，支持分页遍历。

#### Scenario: Scrape first page of works
- **WHEN** 导航到用户主页
- **THEN** 拦截首次 `/aweme/post/` 响应，解析出最多 18 条作品数据

#### Scenario: Scrape all works with pagination
- **WHEN** 指定 max_pages=None（全部采集）
- **THEN** 滚动页面触发加载更多请求，通过 max_cursor 参数持续拦截后续页响应，直到 has_more=false

#### Scenario: Distinguish video and note
- **WHEN** 解析作品数据时
- **THEN** 根据 aweme_type 字段区分视频（type='video'）和图文（type='note'），分别存储到 works 表

### Requirement: Search discovery
系统 SHALL 支持通过关键词搜索用户和作品。

#### Scenario: Search users by keyword
- **WHEN** 调用 search(keyword, type='user')
- **THEN** 导航到搜索页面，拦截 `/aweme/v1/web/discover/search/` 响应，返回搜索结果列表

#### Scenario: CAPTCHA detection
- **WHEN** 搜索触发滑块验证
- **THEN** 暂停任务并通知用户手动处理验证码，验证通过后继续
