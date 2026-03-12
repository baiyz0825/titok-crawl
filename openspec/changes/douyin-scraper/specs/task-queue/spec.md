## ADDED Requirements

### Requirement: Task submission
系统 SHALL 支持提交采集任务到 SQLite 持久化队列。

#### Scenario: Submit task
- **WHEN** 调用 submit(task_type, target, **params)
- **THEN** 在 tasks 表创建 pending 状态记录，返回 task_id

### Requirement: Task scheduling
系统 SHALL 持续轮询 tasks 表，按优先级分发待执行任务。

#### Scenario: Schedule pending tasks
- **WHEN** 调度循环运行时
- **THEN** 从 tasks 表取出 priority 最高的 pending 任务，标记为 running，分发给对应 Scraper 执行

#### Scenario: Concurrency control
- **WHEN** 已有任务在执行
- **THEN** 等待当前任务完成后再取下一个（max_concurrent=1）

### Requirement: Task retry
系统 SHALL 对失败任务自动重试，最多 3 次。

#### Scenario: Auto retry on failure
- **WHEN** 任务执行失败且 retry_count < max_retries
- **THEN** 增加 retry_count，将状态重置为 pending，等待下次调度

#### Scenario: Max retries exceeded
- **WHEN** retry_count >= max_retries
- **THEN** 将状态标记为 failed，记录 error_message

### Requirement: Task lifecycle management
系统 SHALL 支持取消任务和查询任务状态。

#### Scenario: Cancel task
- **WHEN** 调用 cancel(task_id)
- **THEN** 将 pending 任务标记为 cancelled；running 任务尝试中断后标记为 cancelled

#### Scenario: Recovery after restart
- **WHEN** 服务重启时
- **THEN** 将所有 running 状态的任务重置为 pending，等待重新调度

### Requirement: Request rate limiting
系统 SHALL 在连续请求之间添加随机延迟（2-5 秒），防止触发风控。

#### Scenario: Rate limiting between requests
- **WHEN** 执行任务中的每次页面导航或滚动操作
- **THEN** 在操作前等待随机 2-5 秒
