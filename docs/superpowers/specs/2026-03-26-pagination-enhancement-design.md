# 分页功能增强设计

## 概述

为用户界面、作品界面、任务界面、定时任务界面添加分页功能，支持选择每页显示的元素数量（10、20、50）。

## 当前状态

| 页面 | 分页状态 | 每页数量 |
|------|----------|----------|
| Users.vue | ✅ 已有 | 固定 20 |
| Works.vue | ✅ 已有 | 固定 20 |
| Tasks.vue | ✅ 已有 | 固定 20 |
| Schedules.vue | ❌ 无 | - |

## 设计方案

### 前端改动

#### 1. Users.vue、Works.vue、Tasks.vue

在现有 `el-pagination` 组件上添加页大小选择功能：

```vue
<el-pagination
  v-model:current-page="page"
  v-model:page-size="pageSize"
  :page-sizes="[10, 20, 50]"
  :total="total"
  layout="total, sizes, prev, pager, next"
  @size-change="handleSizeChange"
/>
```

**改动点：**
- 添加 `v-model:page-size="pageSize"` 双向绑定
- 添加 `:page-sizes="[10, 20, 50]"` 可选数量
- 修改 `layout` 添加 `sizes` 显示数量选择器
- 添加 `@size-change` 事件处理（页大小变化时重置到第一页并重新获取数据）

#### 2. Schedules.vue

添加完整的分页功能：

```vue
<script setup>
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const fetchSchedules = async () => {
  const res = await api.get('/schedules', {
    params: { page: page.value, size: pageSize.value }
  })
  schedules.value = res.data.items
  total.value = res.data.total
}

const handleSizeChange = () => {
  page.value = 1
  fetchSchedules()
}
</script>

<template>
  <el-pagination
    v-model:current-page="page"
    v-model:page-size="pageSize"
    :page-sizes="[10, 20, 50]"
    :total="total"
    layout="total, sizes, prev, pager, next"
    @current-change="fetchSchedules"
    @size-change="handleSizeChange"
  />
</template>
```

### 后端改动

#### Schedules API (`backend/api/schedules.py`)

添加分页参数支持：

```python
@router.get("")
async def list_schedules(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    enabled: bool | None = Query(None),
):
    """List all schedules with pagination."""
    offset = (page - 1) * size

    query = select(Schedule)
    if enabled is not None:
        query = query.where(Schedule.enabled == enabled)

    # Get total count
    count_query = select(func.count()).select_from(Schedule)
    if enabled is not None:
        count_query = count_query.where(Schedule.enabled == enabled)
    total = (await db.execute(count_query)).scalar()

    # Get paginated items
    query = query.offset(offset).limit(size).order_by(Schedule.id.desc())
    schedules = (await db.execute(query)).scalars().all()

    return {
        "items": [s.to_dict() for s in schedules],
        "total": total,
        "page": page,
        "size": size
    }
```

## 涉及文件

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `frontend/src/views/Users.vue` | 修改 | 添加页大小选择 |
| `frontend/src/views/Works.vue` | 修改 | 添加页大小选择 |
| `frontend/src/views/Tasks.vue` | 修改 | 添加页大小选择 |
| `frontend/src/views/Schedules.vue` | 修改 | 添加完整分页功能 |
| `backend/api/schedules.py` | 修改 | 添加分页参数 |

## UI 布局

采用 Element Plus 标准布局：
- 分页器放在表格底部
- 左侧显示总数和页大小选择器
- 右侧显示页码导航

## 验收标准

1. 四个页面都能显示分页器
2. 页大小选择器提供 10、20、50 三个选项
3. 切换页大小时自动跳转到第一页
4. Schedules 页面分页正常工作
5. 后端 API 正确返回分页数据
