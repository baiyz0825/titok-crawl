<template>
  <div class="page">
    <div class="page-header">
      <h1>任务队列</h1>
      <p class="page-subtitle">管理和创建数据采集任务</p>
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
          <el-button type="primary" @click="showCreateDialog = true">新建任务</el-button>
          <el-button v-if="selectedTasks.length" type="danger" plain @click="batchDelete">删除选中</el-button>
          <el-button @click="fetchTasks" :loading="loading">刷新</el-button>
        </div>
      </div>

      <el-table :data="tasks" v-loading="loading" @selection-change="(val: any[]) => selectedTasks = val" style="width: 100%">
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="#" width="56" class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
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
        <el-table-column label="进度" width="220" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">
            <div v-if="row.status === 'running' && progressMap[row.id]" class="progress-cell">
              <el-progress :percentage="Math.round(progressMap[row.id].progress * 100)" :stroke-width="6" :show-text="false" />
              <div class="progress-detail">
                <span class="progress-text">{{ progressMap[row.id].step }}</span>
                <span v-if="progressMap[row.id].target" class="progress-target">{{ progressMap[row.id].target }}</span>
              </div>
            </div>
            <div v-else-if="row.status === 'completed'" class="completed-cell">
              <el-icon color="#10b981" :size="16"><SuccessFilled /></el-icon>
              <span style="margin-left: 6px; font-size: 13px; color: #10b981;">完成</span>
              <span v-if="row.result" class="completed-result">{{ formatTaskResult(row.result) }}</span>
            </div>
            <div v-else-if="row.status === 'failed'" class="failed-cell">
              <el-icon color="#ef4444" :size="16"><CircleCloseFilled /></el-icon>
              <span style="margin-left: 6px; font-size: 13px; color: #ef4444;">失败</span>
            </div>
            <div v-else-if="row.status === 'pending'" class="pending-cell">
              <el-icon color="#94a3b8" :size="16"><Clock /></el-icon>
              <span style="margin-left: 6px; font-size: 13px; color: #94a3b8;">等待中</span>
            </div>
            <div v-else-if="row.status === 'paused'" class="paused-cell">
              <el-icon color="#f59e0b" :size="16"><VideoPause /></el-icon>
              <span style="margin-left: 6px; font-size: 13px; color: #f59e0b;">已暂停</span>
            </div>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="target" label="目标" min-width="160" show-overflow-tooltip class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
        <el-table-column label="错误" min-width="120" show-overflow-tooltip class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">
            <span v-if="row.error_message" style="color: #ef4444; font-size: 12px">{{ row.error_message }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="110" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }"><span class="text-muted">{{ formatDate(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" class-name="col-action" label-class-name="col-action">
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

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建采集任务" width="500px" @close="resetForm">
      <el-form :model="form" label-width="100px" label-position="left">
        <el-form-item label="任务类型">
          <el-select v-model="form.task_type" style="width: 100%">
            <el-option label="用户资料" value="user_profile" />
            <el-option label="用户作品" value="user_works" />
            <el-option label="全量采集" value="user_all" />
            <el-option label="喜欢列表" value="user_likes" />
            <el-option label="收藏列表" value="user_favorites" />
            <el-option label="关注列表" value="user_following" />
          </el-select>
        </el-form-item>

        <el-form-item label="目标用户">
          <div style="display: flex; gap: 8px;">
            <el-select
              v-model="form.target"
              filterable
              remote
              :remote-method="searchUsers"
              :loading="userSearchLoading"
              placeholder="搜索或选择用户"
              style="flex: 1"
              @visible-change="onSelectVisibleChange"
            >
              <el-option
                v-for="u in userOptions"
                :key="u.sec_user_id"
                :label="u.nickname || u.douyin_id || u.sec_user_id"
                :value="u.sec_user_id"
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
            <el-button
              type="success"
              plain
              @click="selectCurrentUser"
              :loading="currentUserLoading"
              title="当前登录用户"
            >
              我
            </el-button>
          </div>
        </el-form-item>

        <el-form-item v-if="['user_works', 'user_all', 'user_likes', 'user_favorites', 'user_following'].includes(form.task_type)" label="最大采集数量">
          <el-input-number v-model="form.max_count" :min="1" :max="1000" placeholder="不限制" style="width: 100%" />
          <span style="font-size: 12px; color: #94a3b8; margin-top: 4px; display: block;">留空则采集全部</span>
        </el-form-item>

        <el-form-item v-if="['user_works', 'user_all'].includes(form.task_type)" label="采集选项">
          <el-checkbox-group v-model="form.sync_types" style="display: flex; flex-direction: column; gap: 8px">
            <el-checkbox label="refresh_info">更新作品信息（简介、点赞、播放、收藏等）</el-checkbox>
            <el-checkbox label="scrape_comments">采集评论数据</el-checkbox>
            <el-checkbox label="download_media">下载媒体文件（封面图/视频/图文图片）</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item v-if="form.task_type === 'user_following'" label="关注列表选项">
          <el-checkbox-group v-model="form.sync_types" style="display: flex; flex-direction: column; gap: 8px">
            <el-checkbox value="collect_profile" label="采集用户资料（头像、昵称、简介等）" />
            <el-checkbox value="recursive" label="递归采集（采集关注用户的关注列表）">
              <template #default>
                <div style="display: flex; flex-direction: column; gap: 8px; margin-left: 24px; margin-top: 8px;" v-if="form.sync_types.includes('recursive')">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 13px; color: #64748b;">递归深度：</span>
                    <el-input-number v-model="form.recursive_depth" :min="1" :max="3" placeholder="最多3层" style="width: 120px" />
                    <span style="font-size: 12px; color: #94a3b8;">（1=仅关注，2=关注+关注的朋友，3=再扩展一层）</span>
                  </div>
                </div>
              </template>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask" :loading="submitting">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { SuccessFilled, CircleCloseFilled, Clock, VideoPause } from '@element-plus/icons-vue'
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

// 创建任务相关
const showCreateDialog = ref(false)
const submitting = ref(false)
const form = ref({
  task_type: 'user_profile',
  target: '',
  max_pages: undefined,
  max_count: undefined,
  sync_types: [] as string[],
  recursive_depth: 1
})
const userOptions = ref<any[]>([])
const userSearchLoading = ref(false)
const currentUserLoading = ref(false)

function typeLabel(t: string) {
  return ({
    user_profile: '用户资料',
    user_works: '用户作品',
    user_all: '全量采集',
    user_likes: '喜欢列表',
    user_favorites: '收藏列表',
    user_following: '关注列表',
    search: '搜索',
    comments: '评论',
    media_download: '媒体下载',
    work_info: '作品信息',
    speech_recognition: '语音识别'
  } as Record<string, string>)[t] || t
}

function statusLabel(s: string) {
  return ({ pending: '等待中', running: '运行中', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[s] || s
}

function formatDate(d: string) { return d ? d.slice(5, 16).replace('T', ' ') : '-' }

function formatTaskResult(result: any) {
  if (!result) return ''
  const parts = []
  if (result.count !== undefined) parts.push(`${result.count} 个作品`)
  if (result.works_count !== undefined) parts.push(`${result.works_count} 个作品`)
  if (result.comments_count > 0) parts.push(`${result.comments_count} 条评论`)
  if (result.refreshed_count > 0) parts.push(`刷新 ${result.refreshed_count}`)
  if (result.media_downloaded > 0) parts.push(`下载 ${result.media_downloaded}`)
  if (result.total !== undefined && result.total > 0) parts.push(`${result.total} 个用户`)
  return parts.length > 0 ? `（${parts.join('，')}）` : ''
}

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

// 创建任务相关方法
async function searchUsers(query: string = '') {
  userSearchLoading.value = true
  try {
    const params: any = { size: 20 }
    if (query) {
      params.keyword = query
    }
    const res: any = await client.get('/users', { params })
    userOptions.value = res.items || []
  } catch {
    userOptions.value = []
  }
  userSearchLoading.value = false
}

async function onSelectVisibleChange(visible: boolean) {
  // 当下拉框展开时，如果列表为空，自动加载用户列表
  if (visible && userOptions.value.length === 0) {
    await searchUsers('')
  }
}

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
    if (form.value.max_pages) params.max_pages = form.value.max_pages
    if (form.value.max_count) params.max_count = form.value.max_count

    // 处理采集选项
    if (form.value.sync_types.includes('refresh_info')) {
      params.refresh_info = true
    }
    if (form.value.sync_types.includes('scrape_comments')) {
      params.scrape_comments = true
    }
    if (form.value.sync_types.includes('download_media')) {
      params.download_media = true
    }
    if (form.value.sync_types.includes('collect_profile')) {
      params.collect_profile = true
    }
    if (form.value.sync_types.includes('recursive')) {
      params.recursive = true
      params.recursive_depth = form.value.recursive_depth || 1
    }

    await client.post('/tasks', params)
    ElMessage.success('任务已创建')
    showCreateDialog.value = false
    fetchTasks()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  form.value = {
    task_type: 'user_profile',
    target: '',
    max_pages: undefined,
    max_count: undefined,
    sync_types: [],
    recursive_depth: 1
  }
}

async function selectCurrentUser() {
  currentUserLoading.value = true
  try {
    const res: any = await client.get('/sessions/current-user')
    // 设置目标用户
    form.value.target = res.sec_user_id
    // 如果有完整用户信息，也添加到选项列表中显示
    if (res.nickname || res.douyin_id || res.avatar_url) {
      userOptions.value = [res]
    }
    ElMessage.success('已选择当前登录用户')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '获取当前用户失败，请确保已登录')
  } finally {
    currentUserLoading.value = false
  }
}

function startProgressSSE() {
  eventSource = new EventSource('/api/tasks/progress/stream')
  eventSource.onmessage = (event) => { progressMap.value[JSON.parse(event.data).task_id] = JSON.parse(event.data) }
}

onMounted(async () => {
  await fetchTasks()
  await searchUsers('') // 初始加载用户列表
  refreshTimer = setInterval(fetchTasks, 5000)
  startProgressSSE()
})
onUnmounted(() => { clearInterval(refreshTimer); eventSource?.close() })
</script>

<style scoped>
.page { padding: 28px 32px; }
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

.progress-cell { display: flex; flex-direction: column; gap: 4px; }
.progress-detail { display: flex; justify-content: space-between; align-items: center; }
.progress-text { font-size: 12px; color: #64748b; }
.progress-target { font-size: 11px; color: #94a3b8; max-width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.completed-cell, .failed-cell, .pending-cell, .paused-cell { display: flex; align-items: center; }
.completed-result { font-size: 12px; color: #10b981; margin-left: 8px; }
.status-failed { background: #fef2f2; color: #dc2626; }
.status-cancelled { background: #f1f5f9; color: #94a3b8; }

.progress-cell { display: flex; flex-direction: column; gap: 2px; }
.progress-text { font-size: 11px; color: #64748b; }

@media (max-width: 768px) {
  .table-toolbar { flex-direction: column; align-items: flex-start; }
  .toolbar-left { flex-wrap: wrap; width: 100%; }
  .toolbar-right { width: 100%; justify-content: flex-end; }
  .action-btns { gap: 2px; }
  :deep(.col-hide-mobile) { display: none !important; }
  :deep(.col-action) { width: 120px !important; min-width: 120px !important; }
}

/* 创建任务对话框样式 */
.user-option { display: flex; align-items: center; gap: 8px; padding: 2px 0; }
.user-option-info { display: flex; flex-direction: column; min-width: 0; }
.user-option-name { font-size: 13px; font-weight: 500; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-option-id { font-size: 11px; color: #94a3b8; }
</style>
