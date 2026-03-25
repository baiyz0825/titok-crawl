<template>
  <div class="page">
    <div class="page-header">
      <h1>定时任务</h1>
      <p class="page-subtitle">配置自动同步任务</p>
    </div>

    <div class="card" style="margin-bottom: 20px">
      <div class="card-title">添加定时任务</div>
      <div class="form-grid">
        <div class="form-field">
          <label>选择用户</label>
          <el-select
            v-model="form.sec_user_id"
            filterable
            remote
            :remote-method="searchUsers"
            :loading="userSearchLoading"
            placeholder="搜索用户名/抖音号"
            style="width: 100%"
            @change="onUserSelect"
          >
            <el-option
              v-for="u in userOptions"
              :key="u.uid || u.sec_user_id"
              :label="u.nickname || u.douyin_id || u.sec_user_id"
              :value="u.uid || u.sec_user_id"
            >
              <div class="user-option">
                <el-avatar :src="u.avatar_url" :size="24">{{ (u.nickname||'?')[0] }}</el-avatar>
                <div class="user-option-info">
                  <span class="user-option-name">{{ u.nickname || '-' }}</span>
                  <span class="user-option-id">{{ u.douyin_id || u.sec_user_id?.slice(0, 18) + '...' }}</span>
                </div>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="form-field">
          <label>同步类型</label>
          <el-select v-model="form.sync_type" style="width: 100%">
            <el-option label="全部（资料+作品）" value="all" />
            <el-option label="仅资料" value="profile" />
            <el-option label="仅作品" value="works" />
            <el-option label="喜欢列表" value="likes" />
            <el-option label="收藏列表" value="favorites" />
          </el-select>
        </div>
        <div class="form-field">
          <label>间隔(分钟)</label>
          <el-input-number v-model="form.interval_minutes" :min="10" :step="60" style="width: 100%" />
        </div>
        <div class="form-field" style="align-self: flex-end">
          <el-button type="primary" @click="createSchedule" :disabled="!form.sec_user_id" style="width: 100%">添加</el-button>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="table-toolbar">
        <span class="table-title">任务列表</span>
      </div>

      <el-table :data="schedules" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="#" width="56" class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
        <el-table-column label="用户" min-width="200">
          <template #default="{ row }">
            <div>
              <span style="font-weight: 500; color: #1e293b">{{ row.nickname || '-' }}</span>
              <div class="text-muted" style="font-size: 12px">{{ row.sec_user_id }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" round>{{ ({ all: '全部', profile: '资料', works: '作品', likes: '喜欢', favorites: '收藏' } as Record<string,string>)[row.sync_type] || row.sync_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="间隔" width="90" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">{{ formatInterval(row.interval_minutes) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="70">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="toggleEnabled(row)" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="上次执行" width="110" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }"><span class="text-muted">{{ row.last_run_at ? row.last_run_at.slice(5,16).replace('T',' ') : '-' }}</span></template>
        </el-table-column>
        <el-table-column label="下次执行" width="110" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }"><span class="text-muted">{{ row.next_run_at ? row.next_run_at.slice(5,16).replace('T',' ') : '-' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="72">
          <template #default="{ row }">
            <el-popconfirm title="确定删除？" @confirm="deleteSchedule(row.id)">
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchSchedules"
          @size-change="handleSizeChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const schedules = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const form = reactive({ sec_user_id: '', nickname: '', sync_type: 'all', interval_minutes: 1440 })
const userOptions = ref<any[]>([])
const userSearchLoading = ref(false)

function formatInterval(m: number) {
  if (m >= 1440) return `${(m / 1440).toFixed(0)}天`
  if (m >= 60) return `${(m / 60).toFixed(0)}小时`
  return `${m}分钟`
}

async function searchUsers(query: string) {
  if (!query) {
    // Load initial list
    await loadInitialUsers()
    return
  }
  userSearchLoading.value = true
  try {
    const res: any = await client.get('/users', { params: { keyword: query, size: 20 } })
    userOptions.value = res.items || []
  } catch {
    userOptions.value = []
  }
  userSearchLoading.value = false
}

async function loadInitialUsers() {
  userSearchLoading.value = true
  try {
    const res: any = await client.get('/users', { params: { size: 50 } })
    userOptions.value = res.items || []
  } catch {
    userOptions.value = []
  }
  userSearchLoading.value = false
}

function onUserSelect(userId: string) {
  const user = userOptions.value.find(u => (u.uid || u.sec_user_id) === userId)
  if (user) {
    form.nickname = user.nickname || ''
  }
}

async function fetchSchedules() {
  loading.value = true
  const res: any = await client.get('/schedules', {
    params: { page: page.value, size: pageSize.value }
  })
  schedules.value = res.items
  total.value = res.total
  loading.value = false
}

function handleSizeChange() {
  page.value = 1
  fetchSchedules()
}

async function createSchedule() {
  if (!form.sec_user_id) return
  await client.post('/schedules', { ...form })
  ElMessage.success('定时任务已创建')
  form.sec_user_id = ''
  form.nickname = ''
  fetchSchedules()
}

async function toggleEnabled(row: any) {
  await client.put(`/schedules/${row.id}`, { enabled: !row.enabled })
  fetchSchedules()
}

async function deleteSchedule(id: number) {
  await client.delete(`/schedules/${id}`)
  ElMessage.success('已删除')
  fetchSchedules()
}

onMounted(() => {
  fetchSchedules()
  loadInitialUsers()
})
</script>

<style scoped>
.page { padding: 28px 32px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.card-title { font-size: 15px; font-weight: 600; color: #334155; margin-bottom: 16px; }
.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.table-title { font-size: 15px; font-weight: 600; color: #334155; }
.text-muted { color: #94a3b8; font-size: 13px; }

.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }

.form-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr auto;
  gap: 12px;
  align-items: flex-end;
}
.form-field label {
  display: block; font-size: 13px; font-weight: 500; color: #475569; margin-bottom: 6px;
}

.user-option { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.user-option-info { display: flex; flex-direction: column; min-width: 0; }
.user-option-name { font-size: 13px; font-weight: 500; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-option-id { font-size: 11px; color: #94a3b8; }

@media (max-width: 768px) {
  .form-grid { grid-template-columns: 1fr; }
  :deep(.col-hide-mobile) { display: none !important; }
}
</style>
