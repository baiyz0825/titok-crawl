<template>
  <div class="page">
    <div class="page-header">
      <h1>任务队列</h1>
      <p class="page-subtitle">管理数据采集任务</p>
    </div>

    <div class="card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <span class="table-title">任务列表</span>
          <el-select v-model="statusFilter" clearable placeholder="全部状态" style="width: 130px" @change="fetchTasks">
            <el-option label="等待中" value="pending" />
            <el-option label="运行中" value="running" />
            <el-option label="已暂停" value="paused" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
          </el-select>
          <el-tag v-if="selectedTasks.length" type="info" round>已选 {{ selectedTasks.length }}</el-tag>
        </div>
        <div class="toolbar-right">
          <el-button v-if="selectedTasks.length" type="danger" plain @click="batchDelete">删除选中</el-button>
          <el-button @click="fetchTasks" :loading="loading">刷新</el-button>
        </div>
      </div>

      <el-table :data="tasks" v-loading="loading" @selection-change="(val: any[]) => selectedTasks = val" style="width: 100%">
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="#" width="56" />
        <el-table-column prop="task_type" label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" round>{{ typeLabel(row.task_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="status-badge" :class="'status-' + row.status">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <div v-if="row.status === 'running' && progressMap[row.id]" class="progress-cell">
              <el-progress :percentage="Math.round(progressMap[row.id].progress * 100)" :stroke-width="6" :show-text="false" />
              <span class="progress-text">{{ progressMap[row.id].step }}</span>
            </div>
            <el-progress v-else-if="row.status === 'completed'" :percentage="100" status="success" :stroke-width="6" :show-text="false" />
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="target" label="目标" min-width="160" show-overflow-tooltip />
        <el-table-column label="错误" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_message" style="color: #ef4444; font-size: 12px">{{ row.error_message }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="110">
          <template #default="{ row }"><span class="text-muted">{{ formatDate(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button v-if="row.status === 'pending'" size="small" type="warning" plain @click="prioritize(row.id)">插队</el-button>
              <el-button v-if="row.status === 'running'" size="small" plain @click="pauseTask(row.id)">暂停</el-button>
              <el-button v-if="row.status === 'paused'" size="small" type="success" plain @click="resumeTask(row.id)">继续</el-button>
              <el-button v-if="row.status === 'failed'" size="small" plain @click="retryTask(row.id)">重试</el-button>
              <el-button v-if="['pending','running','paused'].includes(row.status)" size="small" type="danger" plain @click="cancelTask(row.id)">取消</el-button>
              <el-popconfirm title="确定删除？" @confirm="deleteTask(row.id)">
                <template #reference>
                  <el-button size="small" type="danger" text>删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          v-model:current-page="page"
          @current-change="fetchTasks"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '../api/client'

const tasks = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')
const progressMap = ref<Record<number, any>>({})
const selectedTasks = ref<any[]>([])
let refreshTimer: ReturnType<typeof setInterval>
let eventSource: EventSource | null = null

function typeLabel(t: string) {
  return ({ user_profile: '用户资料', user_works: '用户作品', user_all: '全量采集', search: '搜索', comments: '评论', media_download: '媒体下载' } as Record<string, string>)[t] || t
}

function statusLabel(s: string) {
  return ({ pending: '等待中', running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[s] || s
}

function formatDate(d: string) { return d ? d.slice(5, 16).replace('T', ' ') : '-' }

async function fetchTasks() {
  loading.value = true
  const params: any = { page: page.value, size: pageSize }
  if (statusFilter.value) params.status = statusFilter.value
  const res: any = await client.get('/tasks', { params })
  tasks.value = res.items
  total.value = res.total
  loading.value = false
}

async function cancelTask(id: number) { await client.post(`/tasks/${id}/cancel`); ElMessage.success('已取消'); fetchTasks() }
async function retryTask(id: number) { await client.post(`/tasks/${id}/retry`); ElMessage.success('已重试'); fetchTasks() }
async function prioritize(id: number) { await client.post(`/tasks/${id}/priority`, { priority: 100 }); ElMessage.success('已插队'); fetchTasks() }
async function pauseTask(id: number) { await client.post(`/tasks/${id}/pause`); ElMessage.success('已暂停'); fetchTasks() }
async function resumeTask(id: number) { await client.post(`/tasks/${id}/resume`); ElMessage.success('已恢复'); fetchTasks() }
async function deleteTask(id: number) { await client.post('/tasks/batch-delete', { task_ids: [id] }); ElMessage.success('已删除'); fetchTasks() }

async function batchDelete() {
  const ids = selectedTasks.value.map(t => t.id)
  await ElMessageBox.confirm(`确定删除 ${ids.length} 个任务？`, '确认')
  await client.post('/tasks/batch-delete', { task_ids: ids })
  ElMessage.success('删除成功')
  fetchTasks()
}

function startProgressSSE() {
  eventSource = new EventSource('/api/tasks/progress/stream')
  eventSource.onmessage = (event) => { progressMap.value[JSON.parse(event.data).task_id] = JSON.parse(event.data) }
}

onMounted(() => { fetchTasks(); refreshTimer = setInterval(fetchTasks, 5000); startProgressSSE() })
onUnmounted(() => { clearInterval(refreshTimer); eventSource?.close() })
</script>

<style scoped>
.page { padding: 28px 32px; max-width: 1400px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.table-title { font-size: 15px; font-weight: 600; color: #334155; }
.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }
.text-muted { color: #94a3b8; font-size: 13px; }
.action-btns { display: flex; gap: 4px; flex-wrap: wrap; }

.status-badge {
  display: inline-flex; align-items: center; padding: 2px 10px;
  border-radius: 10px; font-size: 12px; font-weight: 600;
}
.status-pending { background: #eff6ff; color: #2563eb; }
.status-running { background: #fffbeb; color: #d97706; }
.status-paused { background: #f1f5f9; color: #64748b; }
.status-completed { background: #ecfdf5; color: #059669; }
.status-failed { background: #fef2f2; color: #dc2626; }
.status-cancelled { background: #f1f5f9; color: #94a3b8; }

.progress-cell { display: flex; flex-direction: column; gap: 2px; }
.progress-text { font-size: 11px; color: #64748b; }
</style>
