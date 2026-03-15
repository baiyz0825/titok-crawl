<template>
  <div class="page">
    <div class="page-header">
      <h1>用户管理</h1>
      <p class="page-subtitle">管理已采集的用户数据</p>
    </div>

    <div class="card" style="margin-bottom: 20px">
      <div class="card-title">采集用户</div>
      <div class="form-row">
        <el-input v-model="scrapeId" placeholder="输入用户名、抖音号或 sec_user_id" style="width: 420px" @keyup.enter="scrapeUser" />
        <el-button type="primary" @click="scrapeUser" :loading="scraping">采集资料</el-button>
      </div>
    </div>

    <div class="card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <span class="table-title">用户列表</span>
          <el-input v-model="searchKeyword" placeholder="搜索用户名/抖音号" clearable style="width: 200px" @input="debouncedSearch" prefix-icon="Search" />
          <el-select v-model="sortBy" placeholder="排序方式" style="width: 140px" @change="fetchUsers">
            <el-option label="更新时间" value="updated_at" />
            <el-option label="用户名称" value="nickname" />
            <el-option label="粉丝数量" value="follower_count" />
            <el-option label="获赞数量" value="total_favorited" />
            <el-option label="作品数量" value="aweme_count" />
          </el-select>
          <el-select v-model="sortOrder" placeholder="排序顺序" style="width: 100px" @change="fetchUsers">
            <el-option label="降序" value="DESC" />
            <el-option label="升序" value="ASC" />
          </el-select>
          <el-tag v-if="selectedUsers.length" type="info" round>已选 {{ selectedUsers.length }}</el-tag>
        </div>
        <div class="toolbar-right">
          <el-button v-if="selectedUsers.length" type="danger" plain @click="openDeleteDialog(selectedUsers.map(u => u.sec_user_id))">删除选中</el-button>
          <el-button v-if="selectedUsers.length" type="primary" plain @click="batchCreateTasks">采集选中用户</el-button>
          <el-button @click="fetchUsers" :loading="loading">刷新</el-button>
        </div>
      </div>

      <el-table :data="users" v-loading="loading" @selection-change="(val: any[]) => selectedUsers = val" style="width: 100%">
        <el-table-column type="selection" width="44" />
        <el-table-column label="用户" min-width="220">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :src="row.avatar_url" :size="36">{{ (row.nickname||'?')[0] }}</el-avatar>
              <div>
                <div class="user-name">{{ row.nickname || '-' }}</div>
                <div class="user-id">{{ row.douyin_id || row.sec_user_id?.slice(0, 20) + '...' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="粉丝" width="90" class-name="col-hide-mobile" label-class-name="col-hide-mobile" sortable="custom">
          <template #default="{ row }">{{ formatCount(row.follower_count) }}</template>
        </el-table-column>
        <el-table-column label="获赞" width="90" class-name="col-hide-mobile" label-class-name="col-hide-mobile" sortable="custom">
          <template #default="{ row }">{{ formatCount(row.total_favorited) }}</template>
        </el-table-column>
        <el-table-column prop="aweme_count" label="作品" width="70" class-name="col-hide-mobile" label-class-name="col-hide-mobile" sortable="custom" />
        <el-table-column label="更新时间" width="110" class-name="col-hide-mobile" label-class-name="col-hide-mobile" sortable="custom">
          <template #default="{ row }">
            <span class="text-muted">{{ row.updated_at ? row.updated_at.slice(5,16).replace('T',' ') : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right" class-name="col-action" label-class-name="col-action">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button size="small" @click="viewDetail(row)">详情</el-button>
              <el-button size="small" type="primary" plain @click="openRescrape(row)">更新资料</el-button>
              <el-button size="small" type="danger" plain @click="openDeleteDialog([row.sec_user_id])">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination layout="total, prev, pager, next" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="fetchUsers" />
      </div>
    </div>

    <!-- Detail Dialog (centered) -->
    <el-dialog v-model="drawerVisible" :title="detailData?.nickname || '用户详情'" width="560px" align-center>
      <div v-if="detailData" class="detail-content">
        <div class="detail-profile">
          <el-avatar :src="detailData.avatar_url" :size="64">{{ (detailData.nickname||'?')[0] }}</el-avatar>
          <h3>{{ detailData.nickname }}</h3>
          <p class="text-muted">{{ detailData.signature || '暂无签名' }}</p>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="抖音号">{{ detailData.douyin_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ detailData.location || '-' }}</el-descriptions-item>
          <el-descriptions-item label="粉丝">{{ formatCount(detailData.follower_count) }}</el-descriptions-item>
          <el-descriptions-item label="关注">{{ formatCount(detailData.following_count) }}</el-descriptions-item>
          <el-descriptions-item label="获赞">{{ formatCount(detailData.total_favorited) }}</el-descriptions-item>
          <el-descriptions-item label="作品数">{{ detailData.aweme_count }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="detailData.scrape_status" class="scrape-status">
          <h4>数据概览</h4>
          <div class="status-grid">
            <div class="status-item">
              <div class="status-label">作品</div>
              <div :class="['status-val', detailData.scrape_status.works_count > 0 ? 'ok' : 'no']">
                {{ detailData.scrape_status.works_count > 0 ? `${detailData.scrape_status.works_count} 个` : '未采集' }}
              </div>
            </div>
            <div class="status-item">
              <div class="status-label">评论</div>
              <div :class="['status-val', detailData.scrape_status.comments_count > 0 ? 'ok' : 'no']">
                {{ detailData.scrape_status.comments_count > 0 ? `${detailData.scrape_status.comments_count} 条` : '未采集' }}
              </div>
            </div>
            <div class="status-item">
              <div class="status-label">媒体</div>
              <div :class="['status-val', detailData.scrape_status.media_count > 0 ? 'ok' : 'no']">
                {{ detailData.scrape_status.media_count > 0 ? `${detailData.scrape_status.media_count} 个` : '未下载' }}
              </div>
            </div>
            <div class="status-item">
              <div class="status-label">资料更新</div>
              <div class="status-val ok">
                {{ detailData.scrape_status.profile_updated_at ? detailData.scrape_status.profile_updated_at.slice(5,16).replace('T',' ') : '已采集' }}
              </div>
            </div>
          </div>
        </div>

        <div class="detail-id">
          <span class="text-muted" style="font-size: 11px; word-break: break-all">sec_user_id: {{ detailData.sec_user_id }}</span>
        </div>
      </div>
    </el-dialog>

    <!-- Rescrape Dialog - profile only -->
    <el-dialog v-model="showRescrapeDialog" title="更新用户资料" width="420px" align-center>
      <div v-if="rescrapeTarget" class="rescrape-content">
        <div class="rescrape-user">
          <el-avatar :src="rescrapeTarget.avatar_url" :size="32">{{ (rescrapeTarget.nickname||'?')[0] }}</el-avatar>
          <span class="rescrape-name">{{ rescrapeTarget.nickname }}</span>
        </div>

        <div v-if="rescrapeStatus" class="rescrape-status-list">
          <div class="rescrape-item">
            <div class="rescrape-item-left">
              <span class="rescrape-dot done"></span>
              <span class="rescrape-item-label">用户资料</span>
            </div>
            <div class="rescrape-item-right">
              <span class="rescrape-item-info">{{ rescrapeStatus.profile_updated_at ? rescrapeStatus.profile_updated_at.slice(5,16).replace('T',' ') : '已采集' }}</span>
            </div>
          </div>
        </div>
        <div v-else v-loading="true" class="rescrape-loading">
          加载中...
        </div>

        <el-divider />
        <p style="margin: 0; font-size: 13px; color: #475569">将重新从抖音获取该用户的最新资料信息（昵称、头像、签名、粉丝数等）。</p>
        <p style="margin: 8px 0 0; font-size: 12px; color: #94a3b8">如需采集作品、评论等数据，请在「任务管理」中提交采集任务。</p>
      </div>
      <template #footer>
        <el-button @click="showRescrapeDialog = false">取消</el-button>
        <el-button type="primary" @click="doRescrape">更新资料</el-button>
      </template>
    </el-dialog>

    <!-- Delete Dialog -->
    <el-dialog v-model="showDeleteDialog" title="删除确认" width="500px" align-center @close="resetDeleteDialog">
      <p style="margin: 0 0 16px; font-size: 14px; color: #475569">
        确定要删除 <strong>{{ deleteTarget.length }}</strong> 个用户吗？
      </p>

      <div v-if="deletePreview.loading" v-loading="true" style="min-height: 100px">
        <span style="color: #94a3b8; font-size: 13px">正在计算影响范围...</span>
      </div>

      <div v-else-if="deletePreview.data" class="delete-preview">
        <div class="delete-option-selector">
          <el-radio-group v-model="deleteCascade" @change="recalculateDeletePreview">
            <el-radio :value="false" size="large">
              <div class="radio-content">
                <div class="radio-title">仅删除用户记录</div>
                <div class="radio-desc">作品、评论等数据将保留，但失去关联</div>
              </div>
            </el-radio>
            <el-radio :value="true" size="large">
              <div class="radio-content">
                <div class="radio-title danger">删除用户及所有相关数据</div>
                <div class="radio-desc">包括作品、评论、收藏、喜欢等所有数据</div>
              </div>
            </el-radio>
          </el-radio-group>
        </div>

        <el-divider />

        <div class="delete-summary">
          <div class="summary-title">预计删除内容：</div>
          <div class="summary-stats">
            <div class="stat-item">
              <span class="stat-label">用户记录</span>
              <span class="stat-value">{{ deleteTarget.length }}</span>
            </div>
            <div v-if="deleteCascade" class="stat-item">
              <span class="stat-label">作品数据</span>
              <span class="stat-value danger">{{ deletePreview.data.works_count || 0 }}</span>
            </div>
            <div v-if="deleteCascade && deletePreview.data.comments_count" class="stat-item">
              <span class="stat-label">评论数据</span>
              <span class="stat-value danger">{{ deletePreview.data.comments_count }}</span>
            </div>
            <div v-if="deleteCascade && deletePreview.data.favorites_count" class="stat-item">
              <span class="stat-label">收藏记录</span>
              <span class="stat-value danger">{{ deletePreview.data.favorites_count }}</span>
            </div>
          </div>
          <div v-if="deleteCascade" class="delete-warning">
            <el-icon><WarningFilled /></el-icon>
            <span>此操作不可恢复，请谨慎操作</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button
          v-if="!deletePreview.loading && deletePreview.data"
          type="danger"
          @click="confirmDelete"
          :disabled="deletePreviewConfirmed"
        >
          {{ deletePreviewConfirmed ? '已确认' : '确认删除' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Batch Create Task Dialog -->
    <el-dialog v-model="showBatchTaskDialog" title="批量创建采集任务" width="480px" align-center>
      <p style="margin: 0 0 16px; font-size: 14px; color: #475569">
        为选中的 <strong>{{ selectedUsers.length }}</strong> 个用户创建采集任务
      </p>
      <el-form :model="batchTaskForm" label-width="100px" label-position="left">
        <el-form-item label="任务类型">
          <el-select v-model="batchTaskForm.task_type" style="width: 100%">
            <el-option label="用户资料" value="user_profile" />
            <el-option label="用户作品" value="user_works" />
            <el-option label="全量采集" value="user_all" />
            <el-option label="喜欢列表" value="user_likes" />
            <el-option label="收藏列表" value="user_favorites" />
            <el-option label="关注列表" value="user_following" />
          </el-select>
        </el-form-item>

        <el-form-item label="执行方式">
          <el-radio-group v-model="batchTaskForm.task_category">
            <el-radio value="once">立即执行</el-radio>
            <el-radio value="scheduled">定时执行</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="batchTaskForm.task_category === 'scheduled'" label="执行间隔">
          <el-select v-model="batchTaskForm.schedule_interval" style="width: 100%">
            <el-option label="每小时" value="hourly" />
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="['user_works', 'user_all', 'user_likes', 'user_favorites', 'user_following'].includes(batchTaskForm.task_type)" label="最大采集数量">
          <el-input-number v-model="batchTaskForm.max_count" :min="1" :max="1000" placeholder="不限制" style="width: 100%" />
          <span style="font-size: 12px; color: #94a3b8; margin-top: 4px; display: block;">留空则采集全部</span>
        </el-form-item>

        <el-form-item v-if="['user_works', 'user_all', 'user_likes', 'user_favorites'].includes(batchTaskForm.task_type)" label="采集选项">
          <el-checkbox-group v-model="batchTaskForm.sync_types" style="display: flex; flex-direction: column; gap: 8px">
            <el-checkbox v-if="['user_works', 'user_all'].includes(batchTaskForm.task_type)" label="refresh_info">更新作品信息（简介、点赞、播放、收藏等）</el-checkbox>
            <el-checkbox label="scrape_comments">采集评论数据</el-checkbox>
            <el-checkbox label="download_media">下载媒体文件（封面图/视频/图文图片）</el-checkbox>
            <el-checkbox v-if="['user_likes', 'user_favorites'].includes(batchTaskForm.task_type)" label="collect_creators">采集作者信息</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item v-if="batchTaskForm.task_type === 'user_following'" label="关注列表选项">
          <el-checkbox-group v-model="batchTaskForm.sync_types" style="display: flex; flex-direction: column; gap: 8px">
            <el-checkbox value="collect_profile" label="采集用户资料（头像、昵称、简介等）" />
            <el-checkbox value="recursive" label="递归采集（采集关注用户的关注列表）">
              <template #default>
                <div style="display: flex; flex-direction: column; gap: 8px; margin-left: 24px; margin-top: 8px;" v-if="batchTaskForm.sync_types.includes('recursive')">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 13px; color: #64748b;">递归深度：</span>
                    <el-input-number v-model="batchTaskForm.recursive_depth" :min="1" :max="3" placeholder="最多3层" style="width: 120px" />
                    <span style="font-size: 12px; color: #94a3b8;">（1=仅关注，2=关注+关注的朋友，3=再扩展一层）</span>
                  </div>
                </div>
              </template>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showBatchTaskDialog = false">取消</el-button>
        <el-button type="primary" @click="submitBatchTasks" :loading="submittingBatchTasks">创建 {{ selectedUsers.length }} 个任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import client from '../api/client'

const users = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const scrapeId = ref('')
const scraping = ref(false)
const searchKeyword = ref('')
const sortBy = ref('updated_at')
const sortOrder = ref('DESC')
const drawerVisible = ref(false)
const detailData = ref<any>(null)
const selectedUsers = ref<any[]>([])
const showDeleteDialog = ref(false)
const deleteCascade = ref(false)
const deleteTarget = ref<string[]>([])
const deletePreview = ref<{ loading: boolean; data: any }>({ loading: false, data: null })
const deletePreviewConfirmed = ref(false)
const showRescrapeDialog = ref(false)
const rescrapeTarget = ref<any>(null)
const rescrapeStatus = ref<any>(null)
let searchTimer: ReturnType<typeof setTimeout> | null = null

// Batch task creation related
const showBatchTaskDialog = ref(false)
const submittingBatchTasks = ref(false)
const batchTaskForm = ref({
  task_type: 'user_profile',
  task_category: 'once',
  schedule_interval: 'daily',
  max_count: undefined,
  sync_types: [] as string[],
  recursive_depth: 1
})

function formatCount(n: number | undefined) {
  if (!n && n !== 0) return '-'
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n.toString()
}

function debouncedSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; fetchUsers() }, 300)
}

async function fetchUsers() {
  loading.value = true
  const params: any = { page: page.value, size: pageSize }
  if (searchKeyword.value.trim()) params.keyword = searchKeyword.value.trim()
  if (sortBy.value) params.sort_by = sortBy.value
  if (sortOrder.value) params.sort_order = sortOrder.value
  const res: any = await client.get('/users', { params })
  users.value = res.items
  total.value = res.total
  loading.value = false
}

async function scrapeUser() {
  if (!scrapeId.value.trim()) return
  scraping.value = true
  try {
    await client.post('/users/scrape', {
      identifier: scrapeId.value.trim(),
      sync_type: 'profile',
    })
    ElMessage.success('采集任务已创建')
    scrapeId.value = ''
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '采集失败')
  }
  scraping.value = false
}

async function viewDetail(user: any) {
  const res: any = await client.get(`/users/${user.sec_user_id}`)
  detailData.value = res
  drawerVisible.value = true
}

async function openRescrape(row: any) {
  rescrapeTarget.value = row
  rescrapeStatus.value = null
  showRescrapeDialog.value = true
  try {
    const res: any = await client.get(`/users/${row.sec_user_id}`)
    rescrapeStatus.value = res.scrape_status
  } catch { rescrapeStatus.value = null }
}

async function doRescrape() {
  if (!rescrapeTarget.value) return
  await client.post(`/users/${rescrapeTarget.value.sec_user_id}/rescrape`, {
    sync_type: 'profile',
  })
  ElMessage.success('已提交更新资料任务')
  showRescrapeDialog.value = false
}

async function openDeleteDialog(targets: string[]) {
  deleteTarget.value = targets
  deleteCascade.value = false
  deletePreviewConfirmed.value = false
  showDeleteDialog.value = true
  await recalculateDeletePreview()
}

async function recalculateDeletePreview() {
  if (!deleteTarget.value.length) return

  deletePreview.value = { loading: true, data: null }

  try {
    const params = new URLSearchParams()
    deleteTarget.value.forEach(id => params.append('sec_user_ids', id))
    params.append('cascade', deleteCascade.value.toString())

    const res: any = await client.get(`/users/delete-preview?${params.toString()}`)
    deletePreview.value = { loading: false, data: res }
  } catch (error) {
    console.error('Failed to fetch delete preview:', error)
    deletePreview.value = { loading: false, data: { works_count: 0, comments_count: 0, favorites_count: 0 } }
  }
}

function resetDeleteDialog() {
  deleteTarget.value = []
  deleteCascade.value = false
  deletePreview.value = { loading: false, data: null }
  deletePreviewConfirmed.value = false
}

async function confirmDelete() {
  if (deletePreviewConfirmed.value) {
    // Second click - actually delete
    if (deleteTarget.value.length === 1) {
      await client.delete(`/users/${deleteTarget.value[0]}?cascade=${deleteCascade.value}`)
    } else {
      await client.delete('/users/batch', { data: { sec_user_ids: deleteTarget.value, cascade: deleteCascade.value } })
    }
    ElMessage.success('删除成功')
    showDeleteDialog.value = false
    resetDeleteDialog()
    if (selectedUsers.value.length) {
      selectedUsers.value = []
    }
    fetchUsers()
  } else {
    // First click - show confirmation
    deletePreviewConfirmed.value = true
  }
}

// Batch task creation methods
function batchCreateTasks() {
  if (selectedUsers.value.length === 0) return
  batchTaskForm.value = {
    task_type: 'user_profile',
    task_category: 'once',
    schedule_interval: 'daily',
    max_count: undefined,
    sync_types: [],
    recursive_depth: 1
  }
  showBatchTaskDialog.value = true
}

async function submitBatchTasks() {
  if (selectedUsers.value.length === 0) return

  submittingBatchTasks.value = true
  let successCount = 0
  let failCount = 0

  try {
    for (const user of selectedUsers.value) {
      try {
        const params: any = {
          task_type: batchTaskForm.value.task_type,
          target: user.sec_user_id,
          is_scheduled: batchTaskForm.value.task_category === 'scheduled'
        }
        if (batchTaskForm.value.task_category === 'scheduled') {
          params.schedule_interval = batchTaskForm.value.schedule_interval
        }
        if (batchTaskForm.value.max_count) params.max_count = batchTaskForm.value.max_count

        // 处理采集选项
        if (batchTaskForm.value.sync_types.includes('refresh_info')) {
          params.refresh_info = true
        }
        if (batchTaskForm.value.sync_types.includes('scrape_comments')) {
          params.scrape_comments = true
        }
        if (batchTaskForm.value.sync_types.includes('download_media')) {
          params.download_media = true
        }
        if (batchTaskForm.value.sync_types.includes('collect_creators')) {
          params.collect_creators = true
        }
        if (batchTaskForm.value.sync_types.includes('collect_profile')) {
          params.collect_profile = true
        }
        if (batchTaskForm.value.sync_types.includes('recursive')) {
          params.recursive = true
          params.recursive_depth = batchTaskForm.value.recursive_depth || 1
        }

        await client.post('/tasks', params)
        successCount++
      } catch {
        failCount++
      }
    }

    if (successCount > 0) {
      ElMessage.success(`成功创建 ${successCount} 个任务${failCount > 0 ? `，${failCount} 个失败` : ''}`)
      showBatchTaskDialog.value = false
    } else {
      ElMessage.error('创建任务失败')
    }
  } finally {
    submittingBatchTasks.value = false
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.page { padding: 28px 32px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.card-title { font-size: 15px; font-weight: 600; color: #334155; margin-bottom: 14px; }
.form-row { display: flex; gap: 10px; align-items: center; }

.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.table-title { font-size: 15px; font-weight: 600; color: #334155; }
.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }

.user-cell { display: flex; align-items: center; gap: 10px; }
.user-name { font-weight: 500; color: #1e293b; font-size: 14px; }
.user-id { font-size: 12px; color: #94a3b8; }
.text-muted { color: #94a3b8; font-size: 13px; }
.action-btns { display: flex; gap: 4px; }

.detail-content { padding: 0 4px; }
.detail-profile { text-align: center; margin-bottom: 24px; }
.detail-profile h3 { margin: 12px 0 4px; font-size: 18px; color: #0f172a; }
.detail-profile .text-muted { margin: 0; }
.detail-id { margin-top: 20px; padding: 12px; background: #f8fafc; border-radius: 8px; }

.scrape-status { margin-top: 20px; }
.scrape-status h4 { font-size: 14px; font-weight: 600; color: #334155; margin: 0 0 12px; }
.status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.status-item { padding: 12px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; }
.status-label { font-size: 12px; color: #64748b; margin-bottom: 4px; }
.status-val { font-size: 13px; font-weight: 600; }
.status-val.ok { color: #059669; }
.status-val.no { color: #94a3b8; }

/* Rescrape dialog */
.rescrape-content {}
.rescrape-user { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.rescrape-name { font-weight: 600; color: #1e293b; font-size: 15px; }
.rescrape-status-list { display: flex; flex-direction: column; gap: 0; }
.rescrape-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-bottom: 1px solid #f1f5f9;
}
.rescrape-item:last-child { border-bottom: none; }
.rescrape-item-left { display: flex; align-items: center; gap: 8px; }
.rescrape-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.rescrape-dot.done { background: #10b981; }
.rescrape-dot.pending { background: #e2e8f0; }
.rescrape-item-label { font-size: 13px; color: #334155; font-weight: 500; }
.rescrape-item-right {}
.rescrape-item-info { font-size: 12px; color: #059669; }
.rescrape-item-info.none { color: #94a3b8; }
.rescrape-loading { min-height: 60px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 13px; }

@media (max-width: 768px) {
  .form-row { flex-direction: column; }
  .form-row .el-input { width: 100% !important; }
  .table-toolbar { flex-direction: column; align-items: flex-start; }
  .toolbar-left { flex-wrap: wrap; width: 100%; }
  .toolbar-left .el-input { width: 100% !important; }
  .toolbar-right { width: 100%; justify-content: flex-end; }
  .action-btns { flex-wrap: wrap; gap: 2px; }
  :deep(.col-hide-mobile) { display: none !important; }
  :deep(.col-action) { width: 100px !important; min-width: 100px !important; }
}

/* Delete Preview Styles */
.delete-preview { margin-top: 16px; }
.delete-option-selector { margin-bottom: 16px; }
.delete-option-selector .el-radio { display: flex; margin-bottom: 12px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; transition: all 0.2s; }
.delete-option-selector .el-radio:hover { background: #f8fafc; border-color: #cbd5e1; }
.delete-option-selector .el-radio.is-checked { border-color: #3b82f6; background: #eff6ff; }
.radio-content { display: flex; flex-direction: column; gap: 4px; }
.radio-title { font-size: 14px; font-weight: 500; color: #1e293b; }
.radio-title.danger { color: #dc2626; }
.radio-desc { font-size: 12px; color: #64748b; }

.delete-summary { background: #fef2f2; border-radius: 8px; padding: 16px; border: 1px solid #fecaca; }
.summary-title { font-size: 13px; font-weight: 600; color: #991b1b; margin-bottom: 12px; }
.summary-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 12px; }
.stat-item { display: flex; justify-content: space-between; align-items: center; background: white; padding: 10px 12px; border-radius: 6px; }
.stat-label { font-size: 12px; color: #64748b; }
.stat-value { font-size: 16px; font-weight: 600; color: #1e293b; }
.stat-value.danger { color: #dc2626; }
.delete-warning { display: flex; align-items: center; gap: 6px; padding-top: 8px; border-top: 1px solid #fecaca; color: #dc2626; font-size: 12px; }
</style>
