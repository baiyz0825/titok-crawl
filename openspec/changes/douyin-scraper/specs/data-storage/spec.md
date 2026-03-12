## ADDED Requirements

### Requirement: Database initialization
系统 SHALL 在首次启动时自动创建 SQLite 数据库和所有表。

#### Scenario: Auto create tables
- **WHEN** 应用启动且 data/db/douyin.db 不存在
- **THEN** 创建数据库文件和 users、works、media_files、tasks、sessions 五张表

### Requirement: Users table CRUD
系统 SHALL 提供 users 表的增删改查操作。

#### Scenario: Upsert user
- **WHEN** 采集到用户数据且 sec_user_id 已存在
- **THEN** 更新已有记录而非创建重复记录

#### Scenario: Query users with pagination
- **WHEN** 查询用户列表
- **THEN** 支持分页（offset/limit）和按字段排序

### Requirement: Works table CRUD
系统 SHALL 提供 works 表的增删改查操作，支持按用户、类型筛选。

#### Scenario: Upsert work
- **WHEN** 采集到作品数据且 aweme_id 已存在
- **THEN** 更新已有记录

#### Scenario: Filter works by type
- **WHEN** 查询时指定 type='video' 或 type='note'
- **THEN** 仅返回对应类型的作品

### Requirement: Data analysis with pandas
系统 SHALL 使用 pandas 提供用户数据分析功能。

#### Scenario: User analysis report
- **WHEN** 请求用户分析报告
- **THEN** 返回作品发布频率、互动数据趋势（点赞/评论/分享均值）、视频 vs 图文比例等统计

#### Scenario: Overview statistics
- **WHEN** 请求总览数据
- **THEN** 返回已采集用户数、作品数、媒体文件数、任务统计
