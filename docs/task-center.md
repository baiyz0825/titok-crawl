# Task Center Usage Guide

## Overview

The Task Center is a unified task management system that supports both immediate and scheduled tasks with concurrent execution capabilities. It provides a single interface for creating, managing, and monitoring all types of data collection tasks.

## Key Features

- **Unified Task Model**: Single task type supporting both immediate and scheduled execution
- **Concurrent Execution**: Process multiple tasks simultaneously (configurable, default: 3)
- **Priority-Based Queue**: Higher priority tasks execute first
- **Flexible Scheduling**: Set tasks to run immediately or at scheduled intervals
- **Real-Time Progress**: SSE-based progress streaming for live updates
- **Automatic Retry**: Failed tasks automatically retry with configurable limits

## Task Types

### Immediate Tasks

Tasks that execute as soon as resources are available. These are one-time tasks that:

- Execute immediately when worker capacity is available
- Do not recur after completion
- Are queued based on priority (higher priority first)
- Suitable for on-demand data collection

**Example scenarios:**
- One-time user profile scrape
- Immediate works collection
- Manual favorites export
- On-demand comment retrieval

### Scheduled Tasks

Recurring tasks that run at specified intervals. These tasks:

- Execute on a schedule (e.g., every 60 minutes)
- Automatically reschedule after completion
- Maintain a `next_run_at` timestamp for tracking
- Ideal for periodic data synchronization

**Example scenarios:**
- Daily user profile updates
- Hourly new works monitoring
- Regular favorites sync
- Periodic statistics collection

## Task Parameters

### Common Parameters (All Tasks)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_type` | string | Yes | - | Type of task: `user_profile`, `user_works`, `user_all`, `user_likes`, `user_favorites` |
| `target` | string | Yes | - | Target identifier (e.g., `sec_user_id`) |
| `max_pages` | integer | No | None | Maximum pages to collect |
| `max_count` | integer | No | None | Maximum items to collect |
| `download_media` | boolean | No | false | Whether to download media files |
| `priority` | integer | No | 0 | Task priority (higher = earlier execution) |

### Scheduled Task Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `is_scheduled` | boolean | No | false | Enable scheduled execution |
| `schedule_interval` | integer | No | None | Interval in minutes between runs |
| `next_run_at` | string | No | None | ISO 8601 timestamp for next run |

## Creating Tasks

### Entry Point 1: Web API

Create tasks via the REST API:

```bash
# Immediate task
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "user_profile",
    "target": "MS4wLjABAAAA_user_id_here",
    "priority": 5
  }'

# Scheduled task (runs every 60 minutes)
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "user_works",
    "target": "MS4wLjABAAAA_user_id_here",
    "is_scheduled": true,
    "schedule_interval": 60,
    "next_run_at": "2026-03-14T12:00:00",
    "priority": 3
  }'
```

**Response:**
```json
{
  "task_id": 123,
  "status": "pending"
}
```

### Entry Point 2: Python API

Create tasks programmatically:

```python
from backend.queue.scheduler import scheduler

# Immediate task
task_id = await scheduler.submit(
    task_type="user_profile",
    target="MS4wLjABAAAA_user_id_here",
    max_pages=5,
    priority=5
)

# Scheduled task
from datetime import datetime, timedelta

next_run = datetime.now() + timedelta(minutes=5)
task_id = await scheduler.submit(
    task_type="user_works",
    target="MS4wLjABAAAA_user_id_here",
    is_scheduled=True,
    schedule_interval=60,
    next_run_at=next_run.isoformat(),
    priority=3
)
```

### Entry Point 3: Direct CRUD

Create tasks with full control:

```python
from backend.db import crud
from backend.db.models import Task
from datetime import datetime, timedelta
import json

# Immediate task
task = Task(
    task_type="user_profile",
    target="MS4wLjABAAAA_user_id_here",
    params=json.dumps({"max_pages": 5}),
    priority=5
)
task_id = await crud.create_task(task)

# Scheduled task
next_run = datetime.now() + timedelta(minutes=5)
task = Task(
    task_type="user_works",
    target="MS4wLjABAAAA_user_id_here",
    params=json.dumps({"download_media": True}),
    is_scheduled=True,
    schedule_interval=60,
    next_run_at=next_run,
    priority=3
)
task_id = await crud.create_task(task)
```

## Task Lifecycle

### Status Flow

```
pending → running → completed
                ↓
              failed → pending (retry)
                ↓
             cancelled
```

### Status Descriptions

| Status | Description |
|--------|-------------|
| `pending` | Task is queued and waiting to execute |
| `running` | Task is currently executing |
| `paused` | Task execution is paused (can be resumed) |
| `completed` | Task finished successfully |
| `failed` | Task failed after max retries |
| `cancelled` | Task was cancelled by user |

## Concurrent Execution

The task center supports concurrent task execution:

```python
# Configuration (in backend/config.py)
MAX_CONCURRENT_TASKS = 3  # Default: 3 concurrent tasks
```

### How It Works

1. **Semaphore Control**: Uses asyncio.Semaphore to limit concurrent tasks
2. **Priority Queue**: Higher priority tasks are executed first
3. **Auto-Cleanup**: Completed tasks are automatically removed from the running pool
4. **Dynamic Scaling**: Adjust `MAX_CONCURRENT_TASKS` based on system resources

### Example: Creating 10 Concurrent Tasks

```python
import asyncio
from backend.queue.scheduler import scheduler

async def create_batch_tasks():
    task_ids = []
    for i in range(10):
        task_id = await scheduler.submit(
            task_type="user_profile",
            target=f"USER_{i}",
            priority=i % 5  # Varying priorities
        )
        task_ids.append(task_id)

    print(f"Created {len(task_ids)} tasks")
    print("Tasks will execute in priority order")
    print("Maximum 3 tasks will run concurrently")

asyncio.run(create_batch_tasks())
```

## Monitoring Tasks

### List All Tasks

```bash
curl "http://localhost:8000/api/tasks?page=1&size=20"
```

**Response:**
```json
{
  "items": [
    {
      "id": 123,
      "task_type": "user_profile",
      "target": "MS4wLjABAAAA_user_id_here",
      "status": "running",
      "priority": 5,
      "progress": 0.6,
      "is_scheduled": false,
      "created_at": "2026-03-14T10:00:00"
    }
  ],
  "total": 42,
  "page": 1,
  "size": 20
}
```

### Get Task Details

```bash
curl "http://localhost:8000/api/tasks/123"
```

### Stream Progress (SSE)

```javascript
const eventSource = new EventSource('/api/tasks/progress/stream?task_id=123');

eventSource.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log('Progress:', progress.progress);
  console.log('Current:', progress.current);
  console.log('Total:', progress.total);
};
```

### Filter by Status

```bash
# Get only running tasks
curl "http://localhost:8000/api/tasks?status=running"

# Get only pending tasks
curl "http://localhost:8000/api/tasks?status=pending"

# Get failed tasks
curl "http://localhost:8000/api/tasks?status=failed"
```

## Task Management

### Cancel a Task

```bash
curl -X POST http://localhost:8000/api/tasks/123/cancel
```

### Retry a Failed Task

```bash
curl -X POST http://localhost:8000/api/tasks/123/retry
```

### Pause a Running Task

```bash
curl -X POST http://localhost:8000/api/tasks/123/pause
```

### Resume a Paused Task

```bash
curl -X POST http://localhost:8000/api/tasks/123/resume
```

### Update Task Priority

```bash
curl -X POST http://localhost:8000/api/tasks/123/priority \
  -H "Content-Type: application/json" \
  -d '{"priority": 10}'
```

### Batch Delete Tasks

```bash
curl -X POST http://localhost:8000/api/tasks/batch-delete \
  -H "Content-Type: application/json" \
  -d '{"task_ids": [123, 124, 125]}'
```

## Scheduled Task Management

### How Scheduled Tasks Work

1. **Creation**: Task created with `is_scheduled=True` and `schedule_interval`
2. **Initial Run**: Task executes at `next_run_at` or immediately if in the past
3. **Completion**: After execution, `next_run_at` is updated to future time
4. **Recurrence**: Task becomes pending again and waits for next run
5. **Cycle**: Process repeats automatically

### Example: Daily User Sync

```python
from datetime import datetime, timedelta

# Schedule daily sync at 2 AM
next_run = datetime.now().replace(hour=2, minute=0, second=0)
if next_run < datetime.now():
    next_run += timedelta(days=1)

task_id = await scheduler.submit(
    task_type="user_all",
    target="MS4wLjABAAAA_user_id_here",
    is_scheduled=True,
    schedule_interval=1440,  # 24 hours in minutes
    next_run_at=next_run.isoformat(),
    priority=1
)
```

### Updating Scheduled Tasks

```python
# Update next run time
from datetime import datetime, timedelta

new_next_run = datetime.now() + timedelta(hours=1)
await crud.update_task(
    task_id,
    next_run_at=new_next_run.isoformat()
)
```

## Best Practices

### 1. Use Appropriate Priorities

```python
# High priority for urgent tasks
await scheduler.submit("user_profile", target="...", priority=10)

# Normal priority (default)
await scheduler.submit("user_works", target="...", priority=0)

# Low priority for background tasks
await scheduler.submit("user_all", target="...", priority=-5)
```

### 2. Set Realistic Limits

```python
# Don't overwhelm the system
await scheduler.submit(
    "user_works",
    target="...",
    max_pages=10,  # Limit pages
    max_count=100,  # Limit total items
    priority=5
)
```

### 3. Handle Scheduled Task Intervals

```python
# Common intervals (in minutes)
INTERVAL_HOURLY = 60
INTERVAL_DAILY = 1440
INTERVAL_WEEKLY = 10080
INTERVAL_MONTHLY = 43200

await scheduler.submit(
    "user_profile",
    target="...",
    is_scheduled=True,
    schedule_interval=INTERVAL_DAILY,
    next_run_at=next_run.isoformat()
)
```

### 4. Monitor Progress

Always implement progress monitoring for long-running tasks:

```python
import asyncio

async def monitor_task(task_id):
    from backend.queue.progress import progress_manager

    q = progress_manager.subscribe(task_id)
    try:
        while True:
            event = await q.get()
            print(f"Progress: {event['progress']*100:.1f}%")
            if event.get('status') == 'completed':
                break
    finally:
        progress_manager.unsubscribe(q, task_id)
```

## Troubleshooting

### Tasks Not Executing

**Symptom**: Tasks stay in "pending" status

**Solutions:**
1. Check if scheduler is running: `await scheduler._running`
2. Verify `MAX_CONCURRENT_TASKS` limit
3. Check task priority (higher priority tasks go first)
4. Review scheduler logs for errors

### Scheduled Tasks Not Triggering

**Symptom**: Scheduled tasks don't run at expected time

**Solutions:**
1. Verify `next_run_at` is in correct ISO format
2. Check `is_scheduled=True` is set
3. Ensure `schedule_interval` is in minutes
4. Verify scheduler's `_schedule_check_loop` is running

### High Memory Usage

**Symptom**: Memory grows with many concurrent tasks

**Solutions:**
1. Reduce `MAX_CONCURRENT_TASKS`
2. Implement task result size limits
3. Clean up completed tasks regularly
4. Monitor task completion with `batch-delete`

### Database Lock Issues

**Symptom**: "database is locked" errors

**Solutions:**
1. Ensure single database connection
2. Use proper async/await patterns
3. Close database connections properly
4. Check for long-running transactions

## API Reference

### POST /api/tasks

Create a new task.

**Request Body:**
```json
{
  "task_type": "string",
  "target": "string",
  "max_pages": "integer (optional)",
  "max_count": "integer (optional)",
  "download_media": "boolean (optional)",
  "priority": "integer (optional)",
  "is_scheduled": "boolean (optional)",
  "schedule_interval": "integer (optional)",
  "next_run_at": "string (optional, ISO 8601)"
}
```

**Response:**
```json
{
  "task_id": 123,
  "status": "pending"
}
```

### GET /api/tasks

List tasks with pagination.

**Query Parameters:**
- `status`: Filter by status (optional)
- `page`: Page number (default: 1)
- `size`: Items per page (default: 20)

### GET /api/tasks/{task_id}

Get task details.

### POST /api/tasks/{task_id}/cancel

Cancel a task.

### POST /api/tasks/{task_id}/retry

Retry a failed task.

### POST /api/tasks/{task_id}/pause

Pause a running task.

### POST /api/tasks/{task_id}/resume

Resume a paused task.

### GET /api/tasks/progress/stream

SSE stream for task progress updates.

**Query Parameters:**
- `task_id`: Filter by task ID (optional)

## Summary

The Task Center provides a unified, flexible, and scalable solution for managing both immediate and scheduled data collection tasks. With support for concurrent execution, priority-based queuing, and real-time progress monitoring, it offers the foundation for building robust automation workflows.

For more information, see:
- API documentation: `/docs` (when running)
- Test suite: `tests/test_unified_tasks.py`
- Implementation: `backend/queue/scheduler.py`
