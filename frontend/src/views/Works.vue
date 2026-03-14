<template>
  <div class="page">
    <div class="page-header">
      <h1>作品列表</h1>
      <p class="page-subtitle">浏览与管理采集的作品数据</p>
    </div>

    <div class="card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <el-input v-model="filters.sec_user_id" placeholder="按用户筛选" clearable style="width: 220px" @clear="fetchWorks" />
          <el-select v-model="filters.type" clearable placeholder="类型" style="width: 100px" @change="fetchWorks">
            <el-option label="视频" value="video" />
            <el-option label="图文" value="note" />
          </el-select>
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 240px"
            clearable
            @change="fetchWorks"
          />
          <el-select v-model="filters.scrapeStatus" clearable placeholder="采集状态" style="width: 140px" @change="fetchWorks">
            <el-option label="全部" value="" />
            <el-option label="已采集评论" value="has_comments" />
            <el-option label="未采集评论" value="no_comments" />
            <el-option label="已下载媒体" value="has_media" />
            <el-option label="未下载媒体" value="no_media" />
            <el-option label="已识别文案" value="has_transcript" />
            <el-option label="未识别文案" value="no_transcript" />
          </el-select>
          <div class="sort-group">
            <el-select v-model="sortBy" style="width: 120px" @change="fetchWorks">
              <el-option label="发布时间" value="publish_time" />
              <el-option label="点赞" value="digg_count" />
              <el-option label="播放" value="play_count" />
              <el-option label="评论" value="comment_count" />
              <el-option label="收藏" value="collect_count" />
            </el-select>
            <el-button
              :icon="sortOrder === 'DESC' ? 'SortDown' : 'SortUp'"
              @click="sortOrder = sortOrder === 'DESC' ? 'ASC' : 'DESC'; fetchWorks()"
              style="padding: 8px"
            >{{ sortOrder === 'DESC' ? '↓' : '↑' }}</el-button>
          </div>
        </div>
        <div class="toolbar-right">
          <el-tag v-if="selectedWorks.length" type="info" round>已选 {{ selectedWorks.length }}</el-tag>
          <el-button v-if="selectedWorks.length" type="danger" plain @click="batchDeleteWorks">删除选中</el-button>
          <el-button type="primary" plain @click="openCreateTaskDialog">采集更多</el-button>
          <el-button @click="fetchWorks" :loading="loading">刷新</el-button>
        </div>
      </div>

      <el-table
        :data="works"
        v-loading="loading"
        @row-click="openDetail"
        @selection-change="(val: any[]) => selectedWorks = val"
        style="width: 100%"
        row-class-name="clickable-row"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column label="封面" width="100">
          <template #default="{ row }">
            <el-image v-if="row.cover_url" :src="row.cover_url" fit="cover" class="cover-thumb" lazy />
            <div v-else class="cover-placeholder">无</div>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="描述" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="72" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">
            <el-tag :type="row.type === 'video' ? '' : 'success'" size="small" round>
              {{ row.type === 'video' ? '视频' : '图文' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="digg_count" label="点赞" width="80" sortable class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
        <el-table-column prop="comment_count" label="评论" width="80" sortable class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
        <el-table-column prop="collect_count" label="收藏" width="80" sortable class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
        <el-table-column prop="play_count" label="播放" width="80" sortable class-name="col-hide-mobile" label-class-name="col-hide-mobile" />
        <el-table-column prop="publish_time" label="发布时间" width="110" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">
            <span class="text-muted">{{ formatDate(row.publish_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" class-name="col-action" label-class-name="col-action">
          <template #default="{ row }">
            <div class="action-btns" @click.stop>
              <el-button size="small" type="primary" plain @click="openRescrape(row)">重新采集</el-button>
              <el-popconfirm title="确定删除？" @confirm="deleteOneWork(row.aweme_id)">
                <template #reference>
                  <el-button size="small" type="danger" plain>删除</el-button>
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
          @current-change="fetchWorks"
        />
      </div>
    </div>

    <!-- Work Detail Dialog (centered) -->
    <el-dialog v-model="drawerVisible" :title="detail?.title || '作品详情'" width="600px" align-center>
      <div v-if="detail" class="detail-content" style="max-height: 70vh; overflow-y: auto;">
        <!-- Media -->
        <div class="media-section">
          <template v-if="detail.type === 'video'">
            <video v-if="localVideo" :src="localVideo" controls class="media-player" />
            <template v-else>
              <div class="media-cover-wrapper">
                <el-image :src="detail.cover_url" fit="contain" class="media-cover" />
              </div>
              <p class="text-muted" style="text-align:center;margin-top:8px">视频未下载到本地</p>
            </template>
            <!-- Transcript / Speech Recognition -->
            <div class="transcript-section">
              <div v-if="detail.transcript" class="transcript-block">
                <div class="transcript-header" @click="transcriptExpanded = !transcriptExpanded">
                  <span class="transcript-label">文案</span>
                  <el-icon><component :is="transcriptExpanded ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
                </div>
                <div v-show="transcriptExpanded" class="transcript-text">{{ detail.transcript }}</div>
              </div>
              <div v-else class="transcript-action">
                <el-button size="small" :loading="recognizing" @click="recognizeSpeech">
                  {{ recognizing ? '识别中...' : '识别文案' }}
                </el-button>
              </div>
            </div>
          </template>
          <template v-else-if="detail.type === 'note' && imageUrls.length">
            <el-carousel :autoplay="false" height="320px" indicator-position="outside">
              <el-carousel-item v-for="(img, i) in imageUrls" :key="i">
                <div class="carousel-img-wrapper">
                  <el-image :src="img" fit="contain" style="max-width:100%;max-height:100%" />
                </div>
              </el-carousel-item>
            </el-carousel>
          </template>
        </div>

        <!-- Desc -->
        <div v-if="detail.title" class="desc-block">{{ detail.title }}</div>

        <!-- Stats Grid -->
        <div class="stats-row">
          <div class="mini-stat"><span class="mini-val">{{ formatCount(detail.digg_count) }}</span><span class="mini-label">点赞</span></div>
          <div class="mini-stat"><span class="mini-val">{{ formatCount(detail.comment_count) }}</span><span class="mini-label">评论</span></div>
          <div class="mini-stat"><span class="mini-val">{{ formatCount(detail.share_count) }}</span><span class="mini-label">分享</span></div>
          <div class="mini-stat"><span class="mini-val">{{ formatCount(detail.collect_count) }}</span><span class="mini-label">收藏</span></div>
          <div class="mini-stat"><span class="mini-val">{{ formatCount(detail.play_count) }}</span><span class="mini-label">播放</span></div>
        </div>

        <!-- Scrape Status -->
        <div v-if="detail?.scrape_status" class="scrape-status-section">
          <h4>采集状态</h4>
          <div class="scrape-status-list">
            <div class="scrape-status-item">
              <span class="scrape-status-dot done"></span>
              <span class="scrape-status-label">作品信息</span>
              <span class="scrape-status-info ok">已采集</span>
            </div>
            <div class="scrape-status-item">
              <span :class="['scrape-status-dot', detail.scrape_status.comments_scraped ? 'done' : 'pending']"></span>
              <span class="scrape-status-label">评论数据</span>
              <span :class="['scrape-status-info', detail.scrape_status.comments_scraped ? 'ok' : 'no']">
                {{ detail.scrape_status.comments_scraped ? `${detail.scrape_status.comments_count} 条` : '未采集' }}
              </span>
            </div>
            <div class="scrape-status-item">
              <span :class="['scrape-status-dot', detail.scrape_status.media_downloaded ? 'done' : 'pending']"></span>
              <span class="scrape-status-label">媒体文件</span>
              <span :class="['scrape-status-info', detail.scrape_status.media_downloaded ? 'ok' : 'no']">
                {{ detail.scrape_status.media_downloaded ? `${detail.scrape_status.media_count} 个` : '未下载' }}
              </span>
            </div>
            <div v-if="detail.scrape_status.last_updated" class="scrape-status-item">
              <span class="scrape-status-dot done"></span>
              <span class="scrape-status-label">最后更新</span>
              <span class="scrape-status-info ok">{{ detail.scrape_status.last_updated.slice(5,16).replace('T',' ') }}</span>
            </div>
          </div>
        </div>

        <!-- Comments -->
        <div class="comments-section">
          <div class="section-header">
            <h4>评论 ({{ detail.comment_total || 0 }})</h4>
          </div>
          <div v-if="!detail.comments?.length" class="empty-hint">暂无评论数据</div>
          <template v-for="c in detail.comments" :key="c.comment_id">
            <div class="comment-item">
              <el-avatar :src="c.user_avatar" :size="32">{{ (c.user_nickname||'?')[0] }}</el-avatar>
              <div class="comment-body">
                <div class="comment-author">
                  {{ c.user_nickname }}
                  <span v-if="c.ip_label" class="comment-ip">{{ c.ip_label }}</span>
                </div>
                <div class="comment-text">{{ c.content }}</div>
                <div class="comment-meta">{{ c.create_time }} · 👍 {{ c.digg_count }} · 回复 {{ c.reply_count }}</div>
              </div>
            </div>
            <!-- 子评论 (replies) -->
            <div v-if="c.children?.length" class="comment-replies">
              <template v-for="r in c.children" :key="r.comment_id">
                <div class="comment-item reply-item">
                  <el-avatar :src="r.user_avatar" :size="24">{{ (r.user_nickname||'?')[0] }}</el-avatar>
                  <div class="comment-body">
                    <div class="comment-author">
                      {{ r.user_nickname }}
                      <span v-if="r.ip_label" class="comment-ip">{{ r.ip_label }}</span>
                    </div>
                    <div class="comment-text">{{ r.content }}</div>
                    <div class="comment-meta">{{ r.create_time }} · 👍 {{ r.digg_count }}</div>
                  </div>
                </div>
                <!-- 二级子评论 -->
                <div v-if="r.children?.length" class="comment-replies nested">
                  <div v-for="rr in r.children" :key="rr.comment_id" class="comment-item reply-item">
                    <el-avatar :src="rr.user_avatar" :size="22">{{ (rr.user_nickname||'?')[0] }}</el-avatar>
                    <div class="comment-body">
                      <div class="comment-author">
                        {{ rr.user_nickname }}
                        <span v-if="rr.ip_label" class="comment-ip">{{ rr.ip_label }}</span>
                      </div>
                      <div class="comment-text">{{ rr.content }}</div>
                      <div class="comment-meta">{{ rr.create_time }} · 👍 {{ rr.digg_count }}</div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </div>
      </div>
    </el-dialog>

    <!-- Rescrape Dialog with status -->
    <el-dialog v-model="showRescrapeDialog" title="重新采集" width="460px" align-center>
      <div v-if="rescrapeTarget" class="rescrape-content">
        <div class="rescrape-user">
          <el-image v-if="rescrapeTarget.cover_url" :src="rescrapeTarget.cover_url" fit="cover" class="rescrape-cover" />
          <span class="rescrape-name">{{ rescrapeTarget.title || '作品' }}</span>
        </div>

        <div v-if="rescrapeStatus" class="rescrape-status-list">
          <div class="rescrape-item" v-for="item in rescrapeStatusItems" :key="item.key">
            <div class="rescrape-item-left">
              <span :class="['rescrape-dot', item.done ? 'done' : 'pending']"></span>
              <span class="rescrape-item-label">{{ item.label }}</span>
            </div>
            <div class="rescrape-item-right">
              <span v-if="item.done" class="rescrape-item-info">{{ item.info }}</span>
              <span v-else class="rescrape-item-info none">未采集</span>
            </div>
          </div>
        </div>
        <div v-else v-loading="true" class="rescrape-loading">
          加载中...
        </div>

        <el-divider />
        <p style="margin: 0 0 10px; font-size: 13px; color: #475569; font-weight: 500">选择要采集的内容：</p>
        <el-checkbox-group v-model="rescrapeSyncTypes" style="display: flex; flex-direction: column; gap: 8px">
          <el-checkbox value="work_info" label="更新作品信息（简介、点赞、播放、收藏等）" />
          <el-checkbox value="comments" label="采集评论数据" />
          <el-checkbox value="media" label="下载媒体文件（封面图/视频/图文图片）" />
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button @click="showRescrapeDialog = false">取消</el-button>
        <el-button type="primary" @click="doRescrape">开始采集</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client from '../api/client'

const works = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const filters = reactive({ sec_user_id: '', type: '', dateRange: null as string[] | null, scrapeStatus: '' })
const sortBy = ref('publish_time')
const sortOrder = ref('DESC')
const selectedWorks = ref<any[]>([])
const drawerVisible = ref(false)
const detail = ref<any>(null)
const showRescrapeDialog = ref(false)
const rescrapeSyncTypes = ref<string[]>(['comments'])
const rescrapeTarget = ref<any>(null)
const rescrapeStatus = ref<any>(null)
const transcriptExpanded = ref(false)
const recognizing = ref(false)
let recognizePollTimer: ReturnType<typeof setInterval> | null = null

// Clean up polling when detail dialog closes
watch(drawerVisible, (visible) => {
  if (!visible && recognizePollTimer) {
    clearInterval(recognizePollTimer)
    recognizePollTimer = null
    recognizing.value = false
  }
})

const rescrapeStatusItems = computed(() => {
  const s = rescrapeStatus.value
  if (!s) return []
  return [
    { key: 'info', label: '作品信息', done: true, info: '已采集' },
    { key: 'comments', label: '评论数据', done: s.comments_scraped, info: `${s.comments_count} 条评论` },
    { key: 'media', label: '媒体文件', done: s.media_downloaded, info: `${s.media_count} 个文件` },
  ]
})

const localVideo = computed(() => {
  if (!detail.value?.media_files) return null
  const vid = detail.value.media_files.find((m: any) => m.media_type === 'video' && m.download_status === 'completed' && m.local_path)
  if (!vid) return null
  return vid.local_path.replace(/.*data\/media\//, '/media/')
})

const imageUrls = computed(() => {
  if (!detail.value?.extra_data) return []
  try { const extra = JSON.parse(detail.value.extra_data); return extra.images || [] }
  catch { return [] }
})

function formatCount(n: number | undefined) {
  if (!n && n !== 0) return '-'
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n.toString()
}

function formatDate(d: string) {
  if (!d) return '-'
  return d.slice(0, 10)
}

async function fetchWorks() {
  loading.value = true
  const params: any = { page: page.value, size: pageSize, sort_by: sortBy.value, sort_order: sortOrder.value }
  if (filters.sec_user_id) params.sec_user_id = filters.sec_user_id
  if (filters.type) params.type = filters.type
  if (filters.dateRange && filters.dateRange.length === 2) {
    params.start_date = filters.dateRange[0]
    params.end_date = filters.dateRange[1]
  }
  if (filters.scrapeStatus) {
    const statusMap: Record<string, Record<string, boolean>> = {
      has_comments: { has_comments: true },
      no_comments: { has_comments: false },
      has_media: { has_media: true },
      no_media: { has_media: false },
      has_transcript: { has_transcript: true },
      no_transcript: { has_transcript: false },
    }
    const mapped = statusMap[filters.scrapeStatus]
    if (mapped) Object.assign(params, mapped)
  }
  const res: any = await client.get('/works', { params })
  works.value = res.items
  total.value = res.total
  loading.value = false
}

async function openDetail(row: any) {
  const res: any = await client.get(`/works/${row.aweme_id}`)
  detail.value = res
  transcriptExpanded.value = !!res.transcript
  recognizing.value = false
  drawerVisible.value = true
}

async function batchDeleteWorks() {
  const ids = selectedWorks.value.map(w => w.aweme_id)
  await ElMessageBox.confirm(`确定删除 ${ids.length} 个作品？`, '确认')
  await client.post('/works/batch-delete', { aweme_ids: ids })
  ElMessage.success('删除成功')
  fetchWorks()
}

async function deleteOneWork(aweme_id: string) {
  await client.delete(`/works/${aweme_id}`)
  ElMessage.success('删除成功')
  fetchWorks()
}

function openRescrape(row: any) {
  rescrapeTarget.value = row
  rescrapeStatus.value = null
  rescrapeSyncTypes.value = ['comments']
  showRescrapeDialog.value = true
  client.get(`/works/${row.aweme_id}`).then((res: any) => {
    rescrapeStatus.value = res.scrape_status
  }).catch(() => { rescrapeStatus.value = null })
}

async function doRescrape() {
  if (!rescrapeTarget.value || !rescrapeSyncTypes.value.length) return
  await client.post(`/works/${rescrapeTarget.value.aweme_id}/rescrape`, {
    sync_types: rescrapeSyncTypes.value,
  })
  ElMessage.success('已提交采集任务')
  showRescrapeDialog.value = false
}

async function recognizeSpeech() {
  if (!detail.value) return
  recognizing.value = true
  try {
    await client.post(`/works/${detail.value.aweme_id}/recognize`)
    ElMessage.success('语音识别任务已提交，请稍后刷新查看')
    // Poll for result
    let attempts = 0
    recognizePollTimer = setInterval(async () => {
      attempts++
      if (attempts > 30) { clearInterval(recognizePollTimer!); recognizePollTimer = null; recognizing.value = false; return }
      try {
        const res: any = await client.get(`/works/${detail.value.aweme_id}`)
        if (res.transcript) {
          detail.value.transcript = res.transcript
          transcriptExpanded.value = true
          recognizing.value = false
          clearInterval(recognizePollTimer!)
          recognizePollTimer = null
        }
      } catch { /* ignore */ }
    }, 3000)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '识别失败')
    recognizing.value = false
  }
}

onMounted(fetchWorks)
</script>

<style scoped>
.page { padding: 28px 32px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 10px; }
.toolbar-left { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 8px; }
.sort-group { display: flex; gap: 4px; align-items: center; }
.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }
.text-muted { color: #94a3b8; font-size: 13px; }
.action-btns { display: flex; gap: 4px; }

.cover-thumb { width: 72px; height: 72px; border-radius: 8px; object-fit: cover; cursor: pointer; }
.cover-placeholder { width: 72px; height: 72px; border-radius: 8px; background: #f1f5f9; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 12px; }

:deep(.clickable-row) { cursor: pointer; }
:deep(.clickable-row:hover td) { background: #f8fafc !important; }

/* Detail Dialog */
.detail-content { padding: 0 4px; }
.media-section { margin-bottom: 20px; }
.media-player { width: 100%; max-height: 360px; border-radius: 12px; background: #000; }
.media-cover-wrapper { display: flex; justify-content: center; background: #f8fafc; border-radius: 12px; padding: 8px; }
.media-cover { max-width: 100%; max-height: 280px; border-radius: 8px; }
.carousel-img-wrapper { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #f8fafc; border-radius: 8px; }

.transcript-section { margin-top: 12px; margin-bottom: 4px; }
.transcript-block { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; overflow: hidden; }
.transcript-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; cursor: pointer; user-select: none;
}
.transcript-header:hover { background: #dcfce7; }
.transcript-label { font-size: 13px; font-weight: 600; color: #166534; }
.transcript-text { padding: 0 14px 12px; font-size: 13px; color: #334155; line-height: 1.7; white-space: pre-wrap; }
.transcript-action { text-align: center; padding: 4px 0; }

.desc-block {
  padding: 14px 16px; background: #f8fafc; border-radius: 10px;
  margin-bottom: 20px; color: #334155; font-size: 14px; line-height: 1.6;
}

.stats-row {
  display: flex; gap: 0; margin-bottom: 20px;
  background: #f8fafc; border-radius: 10px; overflow: hidden;
}
.mini-stat {
  flex: 1; text-align: center; padding: 14px 8px;
  border-right: 1px solid #e2e8f0;
  display: flex; flex-direction: column; gap: 2px;
}
.mini-stat:last-child { border-right: none; }
.mini-val { font-size: 18px; font-weight: 700; color: #0f172a; }
.mini-label { font-size: 12px; color: #64748b; }

/* Scrape status in detail */
.scrape-status-section { margin-bottom: 20px; }
.scrape-status-section h4 { font-size: 14px; font-weight: 600; color: #334155; margin: 0 0 10px; }
.scrape-status-list { display: flex; flex-direction: column; }
.scrape-status-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; border-bottom: 1px solid #f1f5f9;
}
.scrape-status-item:last-child { border-bottom: none; }
.scrape-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.scrape-status-dot.done { background: #10b981; }
.scrape-status-dot.pending { background: #e2e8f0; }
.scrape-status-label { flex: 1; font-size: 13px; color: #334155; font-weight: 500; }
.scrape-status-info { font-size: 12px; }
.scrape-status-info.ok { color: #059669; }
.scrape-status-info.no { color: #94a3b8; }

.comments-section { margin-top: 4px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-header h4 { margin: 0; font-size: 15px; font-weight: 600; color: #0f172a; }
.empty-hint { text-align: center; color: #94a3b8; padding: 32px 0; }

.comment-item { display: flex; gap: 10px; padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
.comment-body { flex: 1; min-width: 0; }
.comment-author { font-weight: 500; font-size: 13px; color: #334155; }
.comment-ip { color: #94a3b8; font-weight: 400; margin-left: 8px; font-size: 12px; }
.comment-text { margin-top: 4px; font-size: 14px; color: #475569; }
.comment-meta { margin-top: 6px; font-size: 12px; color: #94a3b8; }
.comment-replies { padding-left: 42px; border-left: 2px solid #e8f5e9; margin-left: 16px; }
.comment-replies.nested { padding-left: 34px; margin-left: 12px; }
.reply-item { padding: 8px 0; }
.reply-item .comment-text { font-size: 13px; }
.reply-item .comment-author { font-size: 12px; }

/* Rescrape dialog */
.rescrape-content {}
.rescrape-user { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.rescrape-cover { width: 40px; height: 40px; border-radius: 6px; flex-shrink: 0; }
.rescrape-name { font-weight: 600; color: #1e293b; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rescrape-status-list { display: flex; flex-direction: column; gap: 0; }
.rescrape-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-bottom: 1px solid #f1f5f9;
}
.rescrape-item:last-child { border-bottom: none; }
.rescrape-item-left { display: flex; align-items: center; gap: 8px; }
.rescrape-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.rescrape-dot.done { background: #10b981; }
.rescrape-dot.pending { background: #e2e8f0; }
.rescrape-item-label { font-size: 13px; color: #334155; font-weight: 500; }
.rescrape-item-right {}
.rescrape-item-info { font-size: 12px; color: #059669; }
.rescrape-item-info.none { color: #94a3b8; }
.rescrape-loading { min-height: 60px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 13px; }

@media (max-width: 768px) {
  .table-toolbar { flex-direction: column; align-items: flex-start; }
  .toolbar-left { flex-wrap: wrap; width: 100%; }
  .toolbar-left .el-input { width: 100% !important; }
  .toolbar-left .el-select { width: 100% !important; }
  .toolbar-right { width: 100%; justify-content: flex-end; }
  .sort-group { width: 100%; }
  .sort-group .el-select { flex: 1; width: auto !important; }
  .cover-thumb { width: 48px; height: 48px; }
  .cover-placeholder { width: 48px; height: 48px; }
  .stats-row { flex-wrap: wrap; }
  .mini-stat { min-width: 33%; }
  .mini-val { font-size: 15px; }
  .comment-replies { padding-left: 24px; margin-left: 8px; }
  .comment-replies.nested { padding-left: 16px; margin-left: 8px; }
  .action-btns { flex-direction: column; gap: 2px; }
  :deep(.col-hide-mobile) { display: none !important; }
  :deep(.col-action) { width: 80px !important; min-width: 80px !important; }
}
</style>
