<template>
  <div class="page">
    <div class="page-header">
      <h1>搜索用户</h1>
      <p class="page-subtitle">搜索本地或抖音用户</p>
    </div>

    <div class="card" style="margin-bottom: 20px">
      <div class="search-bar">
        <el-input
          v-model="keyword"
          placeholder="输入用户名搜索"
          size="large"
          clearable
          @keyup.enter="doSearch"
          style="max-width: 500px"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" size="large" @click="doSearch" :loading="searching">搜索</el-button>
      </div>
    </div>

    <div v-if="searchSource" class="card">
      <div class="table-toolbar">
        <div class="toolbar-left">
          <span class="table-title">搜索结果</span>
          <el-tag :type="searchSource === 'local' ? 'success' : 'warning'" size="small" round>
            {{ searchSource === 'local' ? '本地数据' : '抖音搜索' }}
          </el-tag>
          <span class="text-muted">{{ results.length }} 个结果</span>
        </div>
      </div>

      <el-table :data="results" v-loading="searching" style="width: 100%">
        <el-table-column label="用户" min-width="220">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :src="row.avatar_url || row.avatar" :size="36">{{ (row.nickname||'?')[0] }}</el-avatar>
              <div>
                <div class="user-name">{{ row.nickname }}</div>
                <div class="user-id">{{ row.douyin_id || row.unique_id || '-' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="粉丝" width="100" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">{{ formatCount(row.follower_count) }}</template>
        </el-table-column>
        <el-table-column label="获赞" width="100" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">{{ formatCount(row.total_favorited) }}</template>
        </el-table-column>
        <el-table-column label="签名" min-width="200" show-overflow-tooltip class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">
            <span class="text-muted">{{ row.signature || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="80" class-name="col-hide-mobile" label-class-name="col-hide-mobile">
          <template #default="{ row }">
            <el-tag :type="row.source === 'local' ? 'success' : 'warning'" size="small" round>
              {{ row.source === 'local' ? '本地' : '抖音' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openScrapeDialog(row)">采集</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Scrape Config Dialog -->
    <el-dialog v-model="showScrapeDialog" title="采集配置" width="480px" align-center>
      <div class="scrape-target">
        <el-avatar :src="scrapeTarget?.avatar_url || scrapeTarget?.avatar" :size="40">{{ (scrapeTarget?.nickname||'?')[0] }}</el-avatar>
        <div>
          <div style="font-weight: 600">{{ scrapeTarget?.nickname }}</div>
          <div class="text-muted" style="font-size: 12px">{{ scrapeTarget?.sec_user_id || scrapeTarget?.sec_uid }}</div>
        </div>
      </div>
      <el-divider />
      <div class="collect-section">
        <div class="collect-label">选择采集内容</div>
        <el-checkbox-group v-model="collectOptions" class="collect-grid">
          <el-checkbox label="profile" border>用户资料</el-checkbox>
          <el-checkbox label="works" border>作品列表</el-checkbox>
          <el-checkbox label="comments" border>评论数据</el-checkbox>
          <el-checkbox label="video_cover" border>视频封面</el-checkbox>
          <el-checkbox label="video_data" border>视频文件</el-checkbox>
          <el-checkbox label="images" border>图文内容</el-checkbox>
          <el-checkbox label="stats" border>基本数据</el-checkbox>
        </el-checkbox-group>
      </div>
      <div style="margin-top: 16px">
        <span class="collect-label" style="margin-right: 12px">最大页数</span>
        <el-input-number v-model="maxPages" :min="1" :max="100" />
      </div>
      <template #footer>
        <el-button @click="showScrapeDialog = false">取消</el-button>
        <el-button type="primary" @click="doScrape">开始采集</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const keyword = ref('')
const results = ref<any[]>([])
const searching = ref(false)
const searchSource = ref('')

const showScrapeDialog = ref(false)
const scrapeTarget = ref<any>(null)
const collectOptions = ref(['profile', 'works', 'stats', 'video_cover'])
const maxPages = ref(10)

function formatCount(n: number | undefined) {
  if (!n && n !== 0) return '-'
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return n.toString()
}

async function doSearch() {
  if (!keyword.value.trim()) return
  searching.value = true
  try {
    const res: any = await client.get('/search/users', { params: { keyword: keyword.value.trim() } })
    results.value = res.items || []
    searchSource.value = res.source
  } finally {
    searching.value = false
  }
}

function openScrapeDialog(user: any) {
  scrapeTarget.value = user
  showScrapeDialog.value = true
}

async function doScrape() {
  const secUserId = scrapeTarget.value.sec_user_id || scrapeTarget.value.sec_uid
  if (!secUserId) { ElMessage.warning('无法获取 sec_user_id'); return }
  const opts: Record<string, boolean> = {}
  for (const key of ['profile', 'works', 'comments', 'video_cover', 'video_data', 'images', 'stats']) {
    opts[key] = collectOptions.value.includes(key)
  }
  await client.post('/users/scrape', {
    sec_user_id: secUserId,
    scrape_works: opts.works,
    download_media: opts.video_data || opts.images || opts.video_cover,
    max_pages: maxPages.value,
    collect_options: opts,
  })
  ElMessage.success('采集任务已提交')
  showScrapeDialog.value = false
}
</script>

<style scoped>
.page { padding: 28px 32px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }
.search-bar { display: flex; gap: 10px; align-items: center; }
.table-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.toolbar-left { display: flex; align-items: center; gap: 10px; }
.table-title { font-size: 15px; font-weight: 600; color: #334155; }
.text-muted { color: #94a3b8; font-size: 13px; }

.user-cell { display: flex; align-items: center; gap: 10px; }
.user-name { font-weight: 500; color: #1e293b; }
.user-id { font-size: 12px; color: #94a3b8; }

.scrape-target { display: flex; align-items: center; gap: 12px; }
.collect-section { margin-top: 0; }
.collect-label { font-size: 14px; font-weight: 600; color: #334155; margin-bottom: 10px; display: inline-block; }
.collect-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.collect-grid .el-checkbox { margin-right: 0 !important; }

@media (max-width: 768px) {
  .search-bar { flex-direction: column; }
  .search-bar .el-input { max-width: 100% !important; width: 100% !important; }
  .search-bar .el-button { width: 100%; }
  .toolbar-left { flex-wrap: wrap; }
  :deep(.col-hide-mobile) { display: none !important; }
}
</style>
