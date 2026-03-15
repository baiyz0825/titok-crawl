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
          <el-select v-model="typeFilter" clearable placeholder="全部类型" style="width: 140px" @change="fetchTasks">
            <el-option label="用户资料" value="user_profile" />
            <el-option label="用户作品" value="user_works" />
            <el-option label="全量采集" value="user_all" />
            <el-option label="喜欢列表" value="user_likes" />
            <el-option label="收藏列表" value="user_favorites" />
            <el-option label="关注列表" value="user_following" />
            <el-option label="搜索" value="search" />
          </el-select>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
            @change="fetchTasks"
            clearable
          />
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
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" round>{{ typeLabel(row.task_type) }}</el-tag>
            <el-tag v-if="row.is_scheduled" size="small" type="warning" style="margin-left: 4px">定时</el-tag>
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
        <el-table-column label="操作" width="220" fixed="right" class-name="col-action" label-class-name="col-action">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button v-if="['completed', 'failed'].includes(row.status)" size="small" type="info" text @click="showTaskDetail(row)">详情</el-button>
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

        <el-form-item label="执行方式">
          <el-radio-group v-model="form.task_category">
            <el-radio value="once">立即执行</el-radio>
            <el-radio value="scheduled">定时执行</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.task_category === 'scheduled'" label="执行间隔">
          <el-select v-model="form.schedule_interval" style="width: 100%">
            <el-option label="每小时" value="hourly" />
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
          </el-select>
        </el-form-item>

        <el-form-item label="目标用户">
          <el-select
            v-model="form.target"
            filterable
            remote
            :remote-method="searchUsers"
            :loading="userSearchLoading"
            placeholder="搜索或选择用户"
            style="width: 100%"
            @visible-change="onSelectVisibleChange"
          >
            <el-option
              v-if="currentUser"
              key="current-user"
              :label="`我 (${currentUser.nickname || currentUser.douyin_id || '当前用户'})`"
              :value="currentUser.sec_user_id"
            >
              <div class="user-option current-user-option">
                <el-tag type="success" size="small" style="margin-right: 8px">我</el-tag>
                <el-avatar :src="currentUser.avatar_url" :size="24">{{ (currentUser.nickname||'?')[0] }}</el-avatar>
                <div class="user-option-info">
                  <span class="user-option-name">{{ currentUser.nickname || '-' }}</span>
                  <span class="user-option-id">{{ currentUser.douyin_id || currentUser.sec_user_id?.slice(0, 18) + '...' }}</span>
                </div>
              </div>
            </el-option>
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

        <el-form-item v-if="['user_likes', 'user_favorites'].includes(form.task_type)" label="采集选项">
          <el-checkbox-group v-model="form.sync_types" style="display: flex; flex-direction: column; gap: 8px">
            <el-checkbox label="scrape_comments">采集评论数据</el-checkbox>
            <el-checkbox label="download_media">下载媒体文件（封面图/视频/图文图片）</el-checkbox>
            <el-checkbox label="collect_creators">采集视频作者信息（将视频发布者的资料一并采集）</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item v-if="form.task_type === 'user_following'" label="关注列表选项">
          <el-checkbox-group v-model="form.sync_types" style="display: flex; flex-direction: column; gap: 8px">
            <el-checkbox label="collect_profile">采集用户资料（头像、昵称、简介等）</el-checkbox>
            <el-checkbox label="recursive">
              <template #default>
                <div>递归采集（采集关注用户的关注列表）</div>
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

    <!-- 任务详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="任务详情" width="600px">
      <div v-if="currentTask" class="task-detail">
        <div class="detail-section">
          <div class="detail-row">
            <span class="detail-label">任务 ID：</span>
            <span class="detail-value">{{ currentTask.id }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">任务类型：</span>
            <span class="detail-value">{{ typeLabel(currentTask.task_type) }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">目标：</span>
            <span class="detail-value text-muted">{{ currentTask.target }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">状态：</span>
            <el-tag v-if="currentTask.status === 'completed'" type="success">完成</el-tag>
            <el-tag v-else-if="currentTask.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else-if="currentTask.status === 'running'" type="primary">运行中</el-tag>
            <el-tag v-else-if="currentTask.status === 'pending'" type="info">等待中</el-tag>
            <el-tag v-else>{{ currentTask.status }}</el-tag>
          </div>
          <div class="detail-row">
            <span class="detail-label">创建时间：</span>
            <span class="detail-value">{{ currentTask.created_at || '-' }}</span>
          </div>
          <div v-if="currentTask.started_at" class="detail-row">
            <span class="detail-label">开始时间：</span>
            <span class="detail-value">{{ currentTask.started_at }}</span>
          </div>
          <div v-if="currentTask.completed_at" class="detail-row">
            <span class="detail-label">完成时间：</span>
            <span class="detail-value">{{ currentTask.completed_at }}</span>
          </div>
        </div>

        <div v-if="parsedResult" class="detail-section">
          <div class="section-title">执行结果</div>
          <div class="result-stats">
            <div v-if="parsedResult.count !== undefined" class="stat-item">
              <span class="stat-label">作品总数</span>
              <span class="stat-value">{{ parsedResult.count }}</span>
            </div>
            <div v-if="parsedResult.new !== undefined" class="stat-item">
              <span class="stat-label">新增作品</span>
              <span class="stat-value success">{{ parsedResult.new }}</span>
            </div>
            <div v-if="parsedResult.updated !== undefined" class="stat-item">
              <span class="stat-label">更新作品</span>
              <span class="stat-value info">{{ parsedResult.updated }}</span>
            </div>
            <div v-if="parsedResult.refreshed_count" class="stat-item">
              <span class="stat-label">刷新作品</span>
              <span class="stat-value info">{{ parsedResult.refreshed_count }}</span>
            </div>
            <div v-if="parsedResult.comments_count" class="stat-item">
              <span class="stat-label">评论数量</span>
              <span class="stat-value">{{ parsedResult.comments_count }}</span>
            </div>
            <div v-if="parsedResult.media_downloaded" class="stat-item">
              <span class="stat-label">下载媒体</span>
              <span class="stat-value success">{{ parsedResult.media_downloaded }}</span>
            </div>
            <div v-if="parsedResult.creators_collected" class="stat-item">
              <span class="stat-label">采集作者</span>
              <span class="stat-value success">{{ parsedResult.creators_collected }}</span>
            </div>
            <div v-if="parsedResult.total !== undefined && parsedResult.works_count === undefined" class="stat-item">
              <span class="stat-label">用户总数</span>
              <span class="stat-value">{{ parsedResult.total }}</span>
            </div>
            <div v-if="parsedResult.types" class="stat-item">
              <span class="stat-label">视频/图文</span>
              <span class="stat-value">{{ parsedResult.types.video || 0 }} / {{ parsedResult.types.note || 0 }}</span>
            </div>
          </div>
        </div>

        <div v-if="currentTask.error_message" class="detail-section error-section">
          <div class="section-title">错误信息</div>
          <div class="error-message">{{ currentTask.error_message }}</div>
        </div>

        <div v-if="currentTask.params" class="detail-section">
          <div class="section-title">任务参数</div>
          <pre class="params-json">{{ formatParams(currentTask.params) }}</pre>
        </div>
      </div>
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
const typeFilter = ref('')
const dateRange = ref<[string, string] | null>(null)
const progressMap = ref<Record<number, any>>({})
const selectedTasks = ref<any[]>([])
let refreshTimer: ReturnType<typeof setInterval>
let eventSource: EventSource | null = null

// 创建任务相关
const showCreateDialog = ref(false)
const submitting = ref(false)
const form = ref({
  task_type: 'user_profile',
  task_category: 'once',
  schedule_interval: 'daily',
  target: '',
  max_count: undefined,
  sync_types: [] as string[],
  recursive_depth: 1
})

// 任务详情相关
const showDetailDialog = ref(false)
const currentTask = ref<any>(null)
const parsedResult = ref<any>(null)
const userOptions = ref<any[]>([])
const userSearchLoading = ref(false)
const currentUser = ref<any>(null)

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
  if (typeFilter.value) params.task_type = typeFilter.value
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0]
    params.end_date = dateRange.value[1]
  }
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
  if (visible) {
    // 如果列表为空，自动加载用户列表
    if (userOptions.value.length === 0) {
      await searchUsers('')
    }
    // 如果还没有当前用户信息，自动加载
    if (!currentUser.value) {
      try {
        const res: any = await client.get('/sessions/current-user')
        currentUser.value = res
      } catch {
        // 忽略错误，可能未登录
      }
    }
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
      target: form.value.target,
      is_scheduled: form.value.task_category === 'scheduled'
    }
    if (form.value.task_category === 'scheduled') {
      params.schedule_interval = form.value.schedule_interval
    }
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
    if (form.value.sync_types.includes('collect_creators')) {
      params.collect_creators = true
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
    task_category: 'once',
    schedule_interval: 'daily',
    target: '',
    max_count: undefined,
    sync_types: [],
    recursive_depth: 1
  }
}

function showTaskDetail(task: any) {
  currentTask.value = task
  try {
    parsedResult.value = task.result ? JSON.parse(task.result) : null
  } catch {
    parsedResult.value = null
  }
  showDetailDialog.value = true
}

function formatParams(params: any) {
  if (!params) return ''
  try {
    const parsed = typeof params === 'string' ? JSON.parse(params) : params
    return JSON.stringify(parsed, null, 2)
  } catch {
    return params
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
.user-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  min-height: 40px;
}
.current-user-option {
  background: #f0fdf4;
  border-radius: 6px;
  padding: 6px 10px;
  margin: 4px 0;
}
.user-option-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
  line-height: 1.4;
}
.user-option-name {
  font-size: 13px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
}
.user-option-id {
  font-size: 11px;
  color: #94a3b8;
}

/* 修复下拉选项重叠问题 */
:deep(.el-select-dropdown__item) {
  padding: 8px 12px !important;
  height: auto !important;
  min-height: 48px !important;
}

/* 任务详情对话框样式 */
.task-detail { display: flex; flex-direction: column; gap: 16px; }
.detail-section { background: #f8fafc; border-radius: 8px; padding: 16px; }
.detail-row { display: flex; align-items: center; margin-bottom: 8px; }
.detail-row:last-child { margin-bottom: 0; }
.detail-label { font-size: 13px; color: #64748b; width: 80px; flex-shrink: 0; }
.detail-value { font-size: 13px; color: #1e293b; font-weight: 500; }
.section-title { font-size: 14px; font-weight: 600; color: #1e293b; margin-bottom: 12px; }
.result-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.stat-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: white; border-radius: 6px; }
.stat-label { font-size: 12px; color: #64748b; }
.stat-value { font-size: 14px; font-weight: 600; color: #1e293b; }
.stat-value.success { color: #10b981; }
.stat-value.info { color: #3b82f6; }
.error-section { background: #fef2f2 !important; }
.error-message { font-size: 13px; color: #dc2626; white-space: pre-wrap; word-break: break-word; }
.params-json { font-size: 12px; color: #475569; background: white; padding: 12px; border-radius: 6px; overflow-x: auto; margin: 0; }
</style>
