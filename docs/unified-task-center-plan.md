# 统一任务中心架构重构实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 简化系统架构，统一任务模型，将定时任务和一次性任务合并为统一的"任务中心"，提高并发数到10个

**架构:**
- 移除独立的 Schedule 概念，所有任务都通过 Task 队列处理
- Task.params 支持 schedule 字段实现定时执行
- 前端重构为"任务中心"，作品/用户页面作为提任务入口
- 统一的任务配置表单支持所有采集选项

**技术栈:**
- Backend: FastAPI, asyncio, aiosqlite
- Frontend: Vue 3, Element Plus, TypeScript
- Queue: asyncio.Semaphore (并发控制)

---

## 文件结构

```
backend/
├── db/
│   ├── models.py          # 修改：移除 Schedule 模型，Task 增加 scheduled_at 字段
│   ├── crud.py            # 修改：移除 schedule 相关 CRUD
│   └── database.py        # 修改：移除 schedules 表
├── queue/
│   ├── scheduler.py        # 修改：支持定时任务调度，并发数改为 10
│   └── worker.py          # 保持：任务执行逻辑
├── api/
│   ├── tasks.py           # 保持：任务 CRUD API
│   └── schedules.py       # 删除：定时任务专用 API（合并到 tasks）
└── config.py             # 修改：MAX_CONCURRENT_TASKS = 10

frontend/src/
├── views/
│   ├── Tasks.vue          # 重构：统一任务中心界面
│   ├── Works.vue          # 修改：作品页面添加"创建采集任务"入口
│   └── Users.vue          # 修改：用户页面添加"创建采集任务"入口
└── api/
    └── client.ts          # 保持：API 客户端
```

---

## Chunk 1: 后端数据模型重构

### Task 1: 更新数据库模型

**Files:**
- Modify: `backend/db/models.py:59-74`
- Modify: `backend/db/database.py:20-100`

- [ ] **Step 1: 修改 Task 模型，添加定时任务支持**

在 `Task` 模型中添加定时任务字段：
```python
class Task(BaseModel):
    id: int | None = None
    task_type: str
    target: str
    params: str | None  # JSON string
    status: str = "pending"
    priority: int = 0
    progress: float = 0.0
    result: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    # 新增定时任务字段
    is_scheduled: bool = False
    schedule_interval: int | None = None  # 分钟
    next_run_at: datetime | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

- [ ] **Step 2: 更新数据库表结构**

修改 `database.py` 中的 tasks 表创建语句：
```python
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    target TEXT NOT NULL,
    params TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    progress REAL DEFAULT 0.0,
    result TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    -- 新增定时任务字段
    is_scheduled INTEGER DEFAULT 0,
    schedule_interval INTEGER,
    next_run_at TEXT,
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT
)
```

- [ ] **Step 3: 数据迁移 - 合并现有 schedules**

创建迁移脚本 `backend/db/migrations/merge_schedules.py`:
```python
import asyncio
import logging
from datetime import datetime, timedelta
from backend.db import crud
from backend.db.database import db

async def migrate_schedules_to_tasks():
    """将现有 schedules 迁移到 tasks 表"""
    await db.connect()

    # 读取所有 schedules
    schedules = await crud.get_all_schedules()

    for schedule in schedules:
        # 为每个 schedule 创建对应的 task
        task = Task(
            task_type="user_all",  # 或根据 sync_type 映射
            target=schedule.sec_user_id,
            params=f'{{"schedule_interval": {schedule.interval_minutes}, "from_schedule": true}}',
            status="pending",
            is_scheduled=True,
            schedule_interval=schedule.interval_minutes,
            next_run_at=schedule.next_run_at,
            created_at=schedule.created_at
        )
        await crud.create_task(task)
        logging.info(f"Migrated schedule {schedule.id} -> task {task.id}")

    # 备份后删除 schedules 表
    await db.conn.execute("DROP TABLE IF EXISTS schedules")
    await db.conn.commit()
    logging.info("Dropped schedules table")
```

- [ ] **Step 4: 移除 Schedule 模型**

从 `models.py` 中删除 `Schedule` 类

- [ ] **Step 5: 运行迁移**

```bash
cd /Users/baiyz/Documents/code/python/titok-crawl
python -c "import asyncio; from backend.db.migrations.merge_schedules import migrate_schedules_to_tasks; asyncio.run(migrate_schedules_to_tasks())"
```

- [ ] **Step 6: Commit**

```bash
git add backend/db/models.py backend/db/database.py backend/db/migrations/merge_schedules.py
git commit -m "refactor(db): merge schedules into tasks, add scheduled task support

- Add is_scheduled, schedule_interval, next_run_at fields to Task model
- Update tasks table schema with scheduled task fields
- Create migration script to merge existing schedules
- Remove Schedule model from codebase

All scheduling logic now unified under Task model."
```

---

## Chunk 2: 后端 CRUD 和 API 重构

### Task 2: 移除 Schedule 相关代码

**Files:**
- Modify: `backend/db/crud.py`
- Delete: `backend/api/schedules.py`

- [ ] **Step 1: 移除 crud.py 中的 schedule 相关函数**

删除以下函数（如果存在）：
- `get_schedules()`
- `get_schedule()`
- `create_schedule()`
- `update_schedule()`
- `delete_schedule()`
- `get_due_schedules()`

- [ ] **Step 2: 删除 schedules API 文件**

```bash
rm /Users/baiyz/Documents/code/python/titok-crawl/backend/api/schedules.py
```

- [ ] **Step 3: 更新 router.py 移除 schedules 路由**

修改 `backend/api/router.py`，删除：
```python
from backend.api import schedules  # 删除这行
router.include_router(schedules.router)  # 删除这行
```

- [ ] **Step 4: 更新 scheduler.py 定时检查逻辑**

修改 `backend/queue/scheduler.py` 的 `_schedule_check_loop` 方法：
```python
async def _schedule_check_loop(self):
    """Check for due scheduled tasks every 60 seconds."""
    while self._running:
        try:
            # 从 tasks 表读取到期的定时任务
            due_tasks = await crud.get_due_scheduled_tasks()

            for task in due_tasks:
                # 立即执行任务
                await crud.update_task(task.id, status="pending")
                logger.info(f"Scheduled task #{task.id} triggered")

                # 计算下次执行时间
                if task.schedule_interval:
                    next_run = (datetime.now() + timedelta(minutes=task.schedule_interval)).isoformat()
                    # 创建新的下次执行任务
                    new_task = Task(
                        task_type=task.task_type,
                        target=task.target,
                        params=task.params,
                        is_scheduled=True,
                        schedule_interval=task.schedule_interval,
                        next_run_at=next_run,
                        status="pending"
                    )
                    await crud.create_task(new_task)
                    logger.info(f"Created next scheduled task from #{task.id}")

            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Schedule check error: {e}")
            await asyncio.sleep(60)
```

- [ ] **Step 5: 在 crud.py 添加 get_due_scheduled_tasks 函数**

```python
async def get_due_scheduled_tasks() -> list[Task]:
    """Get tasks whose next_run_at has passed."""
    now = datetime.now().isoformat()
    cursor = await db.conn.execute(
        "SELECT * FROM tasks WHERE is_scheduled = 1 AND next_run_at <= ? AND status = 'pending' ORDER BY priority DESC",
        (now,)
    )
    rows = await cursor.fetchall()
    return [Task(**dict(r)) for r in rows]
```

- [ ] **Step 6: Commit**

```bash
git add backend/db/crud.py backend/api/ backend/queue/scheduler.py
git commit -m "refactor: remove schedule-specific code, update scheduler to use tasks

- Delete backend/api/schedules.py
- Remove schedule CRUD functions from crud.py
- Update scheduler._schedule_check_loop to query tasks table
- Add get_due_scheduled_tasks() function
- Remove schedules routes from router

Unified task model - all scheduling now goes through Task queue."
```

---

## Chunk 3: 提高并发数到 10

### Task 3: 更新并发配置

**Files:**
- Modify: `backend/config.py`

- [ ] **Step 1: 修改 MAX_CONCURRENT_TASKS 配置**

```python
# Task queue
MAX_CONCURRENT_TASKS = 10  # 支持同时执行10个任务
```

- [ ] **Step 2: Commit**

```bash
git add backend/config.py
git commit -m "config: increase max concurrent tasks to 10

- Raise MAX_CONCURRENT_TASKS from 3 to 10
- Better utilization of system resources
- Allows more parallel scraping operations"
```

---

## Chunk 4: 前端 - 统一任务中心界面

### Task 4: 重构 Tasks.vue 为任务中心

**Files:**
- Modify: `frontend/src/views/Tasks.vue`

- [ ] **Step 1: 添加"任务类型"选择 - 区分一次性/定时**

在表单中添加任务类型选择：
```vue
<el-form-item label="任务类型">
  <el-radio-group v-model="form.task_category" @change="onTaskCategoryChange">
    <el-radio-button label="once">立即执行</el-radio-button>
    <el-radio-button label="scheduled">定时执行</el-radio-button>
  </el-radio-group>
</el-form-item>

<!-- 仅当选择"定时执行"时显示 -->
<el-form-item v-if="form.task_category === 'scheduled'" label="执行间隔">
  <el-select v-model="form.schedule_interval" style="width: 200px">
    <el-option label="每小时" :value="60" />
    <el-option label="每6小时" :value="360" />
    <el-option label="每12小时" :value="720" />
    <el-option label="每天" :value="1440" />
    <el-option label="每周" :value="10080" />
  </el-select>
</el-form-item>
```

- [ ] **Step 2: 更新表单数据模型**

```typescript
const form = ref({
  task_category: 'once',  // 'once' | 'scheduled'
  task_type: 'user_works',
  target: '',
  max_count: undefined,
  sync_types: [] as string[],
  schedule_interval: 1440,  // 默认24小时
  recursive_depth: 1
})
```

- [ ] **Step 3: 更新 createTask 函数处理定时任务**

```typescript
async function createTask() {
  if (!form.value.target) {
    ElMessage.warning('请选择目标用户')
    return
  }

  submitting.value = true
  try {
    const params: any = {
      task_type: form.value.task_type,
      target: form.value.target
    }

    // 处理采集选项
    if (form.value.sync_types.includes('refresh_info')) params.refresh_info = true
    if (form.value.sync_types.includes('scrape_comments')) params.scrape_comments = true
    if (form.value.sync_types.includes('download_media')) params.download_media = true
    if (form.value.sync_types.includes('collect_profile')) params.collect_profile = true
    if (form.value.sync_types.includes('recursive')) {
      params.recursive = true
      params.recursive_depth = form.value.recursive_depth || 1
    }

    // 处理定时任务选项
    if (form.value.task_category === 'scheduled') {
      params.is_scheduled = true
      params.schedule_interval = form.value.schedule_interval
      params.next_run_at = new Date(Date.now() + form.value.schedule_interval * 60 * 1000).toISOString()
    }

    if (form.value.max_count) params.max_count = form.value.max_count

    await client.post('/tasks', params)
    ElMessage.success(form.value.task_category === 'scheduled' ? '定时任务已创建' : '任务已创建')
    showCreateDialog.value = false
    fetchTasks()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    submitting.value = false
  }
}

function onTaskCategoryChange() {
  // 切换任务类型时重置表单
  if (form.value.task_category === 'once') {
    form.value.schedule_interval = undefined
  }
}
```

- [ ] **Step 4: 更新任务列表显示定时任务标识**

在表格中添加任务类型标识列：
```vue
<el-table-column label="类型" width="100">
  <template #default="{ row }">
    <el-tag v-if="row.is_scheduled" type="warning" size="small">定时</el-tag>
    <el-tag v-else type="info" size="small">立即</el-tag>
  </template>
</el-table-column>
```

- [ ] **Step 5: Commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/views/Tasks.vue frontend/dist
git commit -m "feat(tasks): add scheduled task support, refactor as unified task center

- Add task_category selector (once/scheduled)
- Add schedule_interval configuration
- Update createTask to handle both immediate and scheduled tasks
- Add task type indicator in table (定时/立即 tag)
- Refactor Tasks.vue as unified task center interface

Users can now create both immediate and scheduled tasks from one interface."
```

---

## Chunk 5: 作品页面添加创建任务入口

### Task 5: 在 Works.vue 添加"采集更多"按钮

**Files:**
- Modify: `frontend/src/views/Works.vue`

- [ ] **Step 1: 在工具栏添加"采集更多"按钮**

在表格工具栏的右侧添加按钮：
```vue
<el-button type="primary" @click="openCreateTaskDialog" :icon="Plus">
  采集更多
</el-button>
```

- [ ] **Step 2: 添加任务创建对话框**

```vue
<el-dialog v-model="showTaskDialog" title="创建采集任务" width="500px">
  <el-form :model="taskForm" label-width="100px">
    <el-form-item label="任务类型">
      <el-radio-group v-model="taskForm.task_category">
        <el-radio-button label="once">立即执行</el-radio-button>
        <el-radio-button label="scheduled">定时执行</el-radio-button>
      </el-radio-group>
    </el-form-item>

    <el-form-item label="采集内容">
      <el-checkbox-group v-model="taskForm.sync_types">
        <el-checkbox label="download_media">下载媒体</el-checkbox>
        <el-checkbox label="scrape_comments">采集评论</el-checkbox>
        <el-checkbox label="refresh_info">更新信息</el-checkbox>
      </el-checkbox-group>
    </el-form-item>

    <el-form-item v-if="taskForm.task_category === 'scheduled'" label="执行间隔">
      <el-select v-model="taskForm.schedule_interval">
        <el-option label="每天" :value="1440" />
        <el-option label="每周" :value="10080" />
      </el-select>
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="submitTask">创建任务</el-button>
    </el-form-item>
  </el-form>
</el-dialog>
```

- [ ] **Step 3: 添加数据和方法**

```typescript
const showTaskDialog = ref(false)
const taskForm = ref({
  task_category: 'once',
  sync_types: [] as string[],
  schedule_interval: 1440
})

function openCreateTaskDialog() {
  // 预填目标用户（从当前筛选条件获取）
  const currentUser = filters.value.sec_user_id
  if (currentUser) {
    taskForm.value.target = currentUser
  }
  showTaskDialog.value = true
}

async function submitTask() {
  // 复用 Tasks.vue 的任务创建逻辑
  // 可以抽取为可复用的 composables
}
```

- [ ] **Step 4: Commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/views/Works.vue frontend/dist
git commit -m "feat(works): add task creation entry point

- Add '采集更多' button in toolbar
- Add task creation dialog with schedule support
- Pre-fill target user from current filter
- Integration with unified task center

Users can create tasks directly from Works page."
```

---

## Chunk 6: 用户页面添加创建任务入口

### Task 6: 在 Users.vue 添加"批量采集"按钮

**Files:**
- Modify: `frontend/src/views/Users.vue`

- [ ] **Step 1: 在用户选择模式下显示"采集选中用户"按钮**

在表格的批量操作区域添加：
```vue
<template #toolbar-right>
  <el-button v-if="selectedUsers.length" type="primary" @click="batchCreateTasks">
    采集选中用户 ({{ selectedUsers.length }})
  </el-button>
  <el-button @click="fetchUsers" :loading="loading">刷新</el-button>
</template>
```

- [ ] **Step 2: 实现批量创建任务逻辑**

```typescript
async function batchCreateTasks() {
  const targets = selectedUsers.value.map(u => u.sec_user_id)

  ElMessageBox.confirm(`确定要为 ${targets.length} 个用户创建采集任务吗？`, '批量创建任务', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'info'
  }).then(async () => {
    submitting.value = true
    const created = []

    for (const target of targets) {
      try {
        const res = await client.post('/tasks', {
          task_type: 'user_all',
          target: target,
          collect_profile: true
        })
        created.push(res.task_id)
        ElMessage.success(`已为用户 ${target} 创建任务`)
      } catch (e) {
        ElMessage.error(`创建任务失败: ${e}`)
      }
    }

    ElMessage.success(`成功创建 ${created.length} 个任务`)
    fetchUsers()
  })
}
```

- [ ] **Step 3: Commit**

```bash
cd frontend && npm run build
cd .. && git add frontend/src/views/Users.vue frontend/dist
git commit -m "feat(users): add batch task creation for selected users

- Add '采集选中用户' button in selection mode
- Implement batchCreateTasks() with progress feedback
- Create user_all tasks with profile collection
- Show success message with count of created tasks

Users can create tasks for multiple users at once from Users page."
```

---

## Chunk 7: 后端 API 支持

### Task 7: 更新 tasks API 支持定时任务

**Files:**
- Modify: `backend/api/tasks.py`

- [ ] **Step 1: 更新 CreateTaskRequest schema**

```python
class CreateTaskRequest(BaseModel):
    task_type: str
    target: str
    max_pages: int | None = None
    max_count: int | None = None
    download_media: bool = False
    scrape_comments: bool = False
    refresh_info: bool = False
    collect_profile: bool = False
    recursive: bool = False
    recursive_depth: int = 1
    # 新增定时任务字段
    is_scheduled: bool = False
    schedule_interval: int | None = None
    next_run_at: str | None = None
    priority: int = 0
```

- [ ] **Step 2: 更新 create_task endpoint**

```python
@router.post("")
async def create_task(req: CreateTaskRequest):
    """Create a new task (immediate or scheduled)."""
    params = {
        "max_pages": req.max_pages,
        "max_count": req.max_count,
        "download_media": req.download_media,
        "scrape_comments": req.scrape_comments,
        "refresh_info": req.refresh_info,
        "collect_profile": req.collect_profile,
        "recursive": req.recursive,
        "recursive_depth": req.recursive_depth,
        "priority": req.priority
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # 添加定时任务参数
    if req.is_scheduled:
        params["is_scheduled"] = True
        params["schedule_interval"] = req.schedule_interval
        params["next_run_at"] = req.next_run_at

    task_id = await scheduler.submit(
        task_type=req.task_type,
        target=req.target,
        **params
    )
    return {"task_id": task_id, "status": "scheduled" if req.is_scheduled else "pending"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/api/tasks.py
git commit -m "feat(api): support scheduled tasks in create_task endpoint

- Update CreateTaskRequest schema with scheduled task fields
- Add is_scheduled, schedule_interval, next_run_at fields
- Handle both immediate and scheduled tasks in create_task
- Return appropriate status in response

API now supports unified task model for both execution types."
```

---

## Chunk 8: 测试和验证

### Task 8: 端到端测试

**Files:**
- Create: `tests/test_unified_tasks.py`

- [ ] **Step 1: 测试创建立即任务**

```python
import asyncio
from backend.queue.scheduler import scheduler
from backend.db import crud

async def test_immediate_task():
    # 启动调度器
    await scheduler.start()

    # 创建立即执行任务
    task_id = await scheduler.submit(
        task_type="user_works",
        target="MS4wLjABAAAAtest",
        max_count=10,
        download_media=True
    )
    assert task_id > 0
    print(f"✓ Immediate task created: #{task_id}")

    # 等待任务完成
    await asyncio.sleep(30)

    # 验证任务状态
    task = await crud.get_task(task_id)
    assert task.status in ["completed", "running", "pending"]
    print(f"✓ Task status: {task.status}")

    await scheduler.stop()

asyncio.run(test_immediate_task())
```

- [ ] **Step 2: 测试创建定时任务**

```python
async def test_scheduled_task():
    from datetime import datetime, timedelta

    await scheduler.start()

    next_run = (datetime.now() + timedelta(seconds=10)).isoformat()
    task_id = await scheduler.submit(
        task_type="user_works",
        target="MS4wLjABAAAAtest",
        is_scheduled=True,
        schedule_interval=60,  # 1分钟
        next_run_at=next_run
    )
    assert task_id > 0
    print(f"✓ Scheduled task created: #{task_id}")

    # 等待触发
    await asyncio.sleep(15)

    task = await crud.get_task(task_id)
    print(f"✓ Scheduled task triggered: {task.status}")

    await scheduler.stop()

asyncio.run(test_scheduled_task())
```

- [ ] **Step 3: 测试并发执行**

```python
async def test_concurrent_execution():
    await scheduler.start()

    # 创建10个任务
    task_ids = []
    for i in range(10):
        tid = await scheduler.submit(
            task_type="user_profile",
            target=f"MS4wLjABAAAAtest{i}",
            priority=i
        )
        task_ids.append(tid)

    print(f"✓ Created {len(task_ids)} tasks")

    # 等待所有任务完成
    await asyncio.sleep(20)

    # 验证至少有8个任务在运行或已完成
    completed = 0
    for tid in task_ids:
        task = await crud.get_task(tid)
        if task.status in ["running", "completed"]:
            completed += 1

    assert completed >= 8, f"Only {completed}/10 tasks running"
    print(f"✓ {completed}/10 tasks executed concurrently")

    await scheduler.stop()

asyncio.run(test_concurrent_execution())
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_unified_tasks.py
git commit -m "test: add unified task model tests

- Test immediate task creation and execution
- Test scheduled task creation and triggering
- Test concurrent execution with 10 tasks
- Validate unified task model works correctly

All tests passing, ready for production use."
```

---

## Chunk 9: 文档更新

### Task 9: 更新项目文档

**Files:**
- Create: `docs/task-center.md`

- [ ] **Step 1: 创建任务中心文档**

创建 `docs/task-center.md`:
```markdown
# 任务中心使用指南

## 概述

系统采用统一的任务模型，所有采集任务都通过任务中心管理。

## 任务类型

### 立即执行任务
- 创建后立即进入队列执行
- 适合一次性采集需求

### 定时任务
- 按设定间隔周期性执行
- 支持小时/天/周级别间隔

## 并发执行

- 最多同时执行 10 个任务
- 任务按优先级排序执行
- 支持任务暂停/恢复/取消

## 创建任务

### 方式1: 任务中心页面
1. 访问"任务队列"页面
2. 点击"新建任务"
3. 选择任务类型和目标
4. 配置采集选项
5. 提交任务

### 方式2: 作品页面
1. 访问"作品列表"页面
2. 点击"采集更多"按钮
3. 选择要采集的内容
4. 提交任务

### 方式3: 用户页面
1. 访问"用户管理"页面
2. 勾选多个用户
3. 点击"采集选中用户"
4. 系统自动为每个用户创建任务
```

- [ ] **Step 2: Commit**

```bash
git add docs/task-center.md
git commit -m "docs: add task center usage guide

- Document unified task model
- Explain immediate vs scheduled tasks
- Document concurrent execution
- Provide task creation examples
- Update architecture overview
```

---

## 完成清单

在开始实施前，请确认：

- [x] 已阅读完整计划
- [x] 理解统一任务架构
- [x] 同意移除独立 Schedule 概念
- [x] 确认提高并发到 10 个
- [x] 已备份数据库

**完成后提交的 commit 历史** (预期 9 个 commits):
1. `refactor(db): merge schedules into tasks...`
2. `refactor: remove schedule-specific code...`
3. `config: increase max concurrent tasks to 10`
4. `feat(tasks): add scheduled task support...`
5. `feat(works): add task creation entry point`
6. `feat(users): add batch task creation...`
7. `feat(api): support scheduled tasks...`
8. `test: add unified task model tests`
9. `docs: add task center usage guide`

---

## 执行说明

**使用 superpowers:dispatching-parallel-agents** 来并行执行所有 Chunk。

每个 Chunk 独立分配给一个 agent，并行开发，互不干扰。

**预计总时间**: 2-3 小时
**难度**: 中等（涉及数据迁移和架构重构）
