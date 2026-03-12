<template>
  <div class="preview-container">
    <!-- 桌面端用户面板 -->
    <aside class="user-panel" :class="{ open: panelOpen }">
      <div class="panel-header">
        <h3>选择用户</h3>
        <button class="panel-close" @click="panelOpen = false">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="panel-search">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="搜索用户..."
          class="search-input"
        />
      </div>
      <div class="user-list">
        <div
          v-for="user in filteredUsers"
          :key="user.sec_user_id"
          class="user-item"
          :class="{ active: selectedUser?.sec_user_id === user.sec_user_id }"
          @click="selectUser(user)"
        >
          <img
            v-if="user.avatar_url"
            :src="user.avatar_url"
            class="user-avatar"
            @error="(e: any) => e.target.style.display = 'none'"
          />
          <div v-else class="user-avatar-placeholder">{{ (user.nickname || '?')[0] }}</div>
          <div class="user-info">
            <div class="user-name">{{ user.nickname || user.sec_user_id }}</div>
            <div class="user-meta">{{ user.scrape_status?.works_count || 0 }} 作品</div>
          </div>
        </div>
        <div v-if="filteredUsers.length === 0 && !loadingUsers" class="empty-hint">
          {{ searchQuery ? '无匹配用户' : '暂无用户数据' }}
        </div>
        <div v-if="loadingUsers" class="loading-hint">加载中...</div>
      </div>
    </aside>

    <!-- 移动端面板遮罩 -->
    <div v-if="panelOpen" class="panel-overlay" @click="panelOpen = false"></div>

    <!-- 移动端浮动头像按钮 -->
    <button class="fab-avatar" @click="panelOpen = true">
      <img
        v-if="selectedUser?.avatar_url"
        :src="selectedUser.avatar_url"
        @error="(e: any) => e.target.style.display = 'none'"
      />
      <svg v-else viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
    </button>

    <!-- 视频 Feed -->
    <div class="feed-container" ref="feedRef">
      <div v-if="!selectedUser" class="feed-empty">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        <p>选择一个用户开始浏览</p>
      </div>

      <div v-else-if="works.length === 0 && !loadingWorks" class="feed-empty">
        <p>该用户暂无视频作品</p>
      </div>

      <template v-else>
        <div
          v-for="(work, index) in works"
          :key="work.aweme_id"
          class="feed-card"
          :data-index="index"
          :data-aweme-id="work.aweme_id"
        >
          <!-- 视频或封面 -->
          <video
            v-if="work._videoUrl"
            :src="work._videoUrl"
            class="feed-media"
            loop
            muted
            playsinline
            preload="auto"
            :poster="work.cover_url"
            @click="togglePlay($event)"
          ></video>
          <div v-else class="feed-cover" @click="togglePlay($event)">
            <img v-if="work.cover_url" :src="work.cover_url" @error="(e: any) => e.target.style.display = 'none'" />
            <div class="cover-overlay">
              <div v-if="work._loading" class="loading-spinner"></div>
              <div v-else-if="work._noVideo" class="no-video-badge">未下载</div>
            </div>
          </div>

          <!-- 右侧互动栏 -->
          <div class="feed-actions">
            <div class="action-item">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
              <span>{{ formatCount(work.digg_count) }}</span>
            </div>
            <div class="action-item">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              <span>{{ formatCount(work.comment_count) }}</span>
            </div>
            <div class="action-item">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
              <span>{{ formatCount(work.share_count) }}</span>
            </div>
          </div>

          <!-- 底部信息 -->
          <div class="feed-info">
            <div class="feed-author">@{{ selectedUser?.nickname || '' }}</div>
            <div class="feed-title">{{ work.title || '无标题' }}</div>
          </div>
        </div>

        <!-- 底部哨兵 -->
        <div ref="sentinelRef" class="feed-sentinel">
          <div v-if="loadingWorks" class="loading-spinner"></div>
          <div v-else-if="!hasMore" class="end-hint">没有更多了</div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import client from '../api/client'

// --- 状态 ---
const loadingUsers = ref(false)
const loadingWorks = ref(false)
const users = ref<any[]>([])
const searchQuery = ref('')
const selectedUser = ref<any>(null)
const works = ref<any[]>([])
const page = ref(1)
const hasMore = ref(true)
const panelOpen = ref(false)

const feedRef = ref<HTMLDivElement | null>(null)
const sentinelRef = ref<HTMLDivElement | null>(null)

// --- 用户列表 ---
const filteredUsers = computed(() => {
  if (!searchQuery.value) return users.value
  const q = searchQuery.value.toLowerCase()
  return users.value.filter(
    (u: any) =>
      (u.nickname || '').toLowerCase().includes(q) ||
      (u.sec_user_id || '').toLowerCase().includes(q) ||
      (u.douyin_id || '').toLowerCase().includes(q)
  )
})

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res: any = await client.get('/users', { params: { size: 200 } })
    users.value = res.items || res || []
  } catch { /* handled by interceptor */ }
  loadingUsers.value = false
}

function selectUser(user: any) {
  selectedUser.value = user
  panelOpen.value = false
  works.value = []
  page.value = 1
  hasMore.value = true
  loadWorks()
}

// --- 作品列表 ---
async function loadWorks() {
  if (!selectedUser.value || loadingWorks.value || !hasMore.value) return
  loadingWorks.value = true
  try {
    const res: any = await client.get('/works', {
      params: {
        sec_user_id: selectedUser.value.sec_user_id,
        type: 'video',
        page: page.value,
        size: 20,
      },
    })
    const items = res.items || res || []
    if (items.length === 0) {
      hasMore.value = false
    } else {
      // 添加内部状态字段
      items.forEach((w: any) => {
        w._videoUrl = null
        w._loading = false
        w._noVideo = false
        w._loaded = false
      })
      works.value.push(...items)
      page.value++
    }
  } catch { /* handled by interceptor */ }
  loadingWorks.value = false
  await nextTick()
  observeCards()
}

// --- IntersectionObserver 视频懒加载 + 自动播放 ---
let cardObserver: IntersectionObserver | null = null
let sentinelObserver: IntersectionObserver | null = null

function observeCards() {
  if (!cardObserver) {
    cardObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const el = entry.target as HTMLDivElement
          const idx = Number(el.dataset.index)
          const work = works.value[idx]
          if (!work) return

          if (entry.isIntersecting) {
            // 懒加载视频 URL
            if (!work._loaded && !work._loading) {
              loadVideoUrl(work)
            }
            // 自动播放
            const video = el.querySelector('video')
            if (video) video.play().catch(() => {})
          } else {
            // 暂停
            const video = el.querySelector('video')
            if (video) video.pause()
          }
        })
      },
      { threshold: 0.6 }
    )
  }

  // 观察所有卡片
  const container = feedRef.value
  if (container) {
    container.querySelectorAll('.feed-card').forEach((el) => {
      cardObserver!.observe(el)
    })
  }

  // 底部哨兵 - 无限滚动
  if (sentinelRef.value && !sentinelObserver) {
    sentinelObserver = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          loadWorks()
        }
      },
      { threshold: 0.1 }
    )
    sentinelObserver.observe(sentinelRef.value)
  }
}

async function loadVideoUrl(work: any) {
  work._loading = true
  try {
    const res: any = await client.get(`/works/${work.aweme_id}`)
    const detail = res || {}
    const mediaFiles = detail.media_files || []
    const videoFile = mediaFiles.find(
      (f: any) => f.media_type === 'video' && f.local_path
    )
    if (videoFile) {
      work._videoUrl = videoFile.local_path.replace(/.*data\/media\//, '/media/')
    } else {
      work._noVideo = true
    }
  } catch {
    work._noVideo = true
  }
  work._loading = false
  work._loaded = true
}

// --- 播放控制 ---
function togglePlay(e: Event) {
  const card = (e.target as HTMLElement).closest('.feed-card')
  if (!card) return
  const video = card.querySelector('video')
  if (!video) return
  if (video.paused) {
    video.play().catch(() => {})
  } else {
    video.pause()
  }
}

// --- 格式化数字 ---
function formatCount(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

// --- 生命周期 ---
onMounted(() => {
  loadUsers()
})

onUnmounted(() => {
  cardObserver?.disconnect()
  sentinelObserver?.disconnect()
})

// 当 sentinelRef 出现时观察它
watch(sentinelRef, (el) => {
  if (el && sentinelObserver) {
    sentinelObserver.observe(el)
  }
})
</script>

<style scoped>
.preview-container {
  display: flex;
  height: 100vh;
  background: #0f0f0f;
  color: #fff;
  overflow: hidden;
}

/* ===== 用户面板 ===== */
.user-panel {
  width: 260px;
  min-width: 260px;
  background: #1a1a1a;
  border-right: 1px solid #2a2a2a;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid #2a2a2a;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.panel-close {
  display: none;
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 4px;
}

.panel-search {
  padding: 12px 16px;
}
.search-input {
  width: 100%;
  padding: 8px 12px;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}
.search-input:focus {
  border-color: #10b981;
}
.search-input::placeholder {
  color: #666;
}

.user-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
}

.user-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.user-item:hover {
  background: #252525;
}
.user-item.active {
  background: rgba(16, 185, 129, 0.15);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.user-avatar-placeholder {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #333;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #888;
  flex-shrink: 0;
}

.user-info {
  min-width: 0;
}
.user-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.user-meta {
  font-size: 11px;
  color: #666;
  margin-top: 2px;
}

.empty-hint, .loading-hint {
  text-align: center;
  color: #555;
  font-size: 13px;
  padding: 24px 0;
}

/* ===== 移动端浮动按钮 ===== */
.fab-avatar {
  display: none;
  position: fixed;
  top: 14px;
  right: 14px;
  z-index: 100;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid #10b981;
  background: #1a1a1a;
  cursor: pointer;
  overflow: hidden;
  padding: 0;
  align-items: center;
  justify-content: center;
  color: #888;
}
.fab-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.panel-overlay {
  display: none;
}

/* ===== Feed ===== */
.feed-container {
  flex: 1;
  overflow-y: auto;
  scroll-snap-type: y mandatory;
  -webkit-overflow-scrolling: touch;
}

.feed-empty {
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #555;
  font-size: 15px;
}

.feed-card {
  height: 100vh;
  scroll-snap-align: start;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  overflow: hidden;
}

.feed-media {
  width: 100%;
  height: 100%;
  object-fit: contain;
  cursor: pointer;
}

.feed-cover {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.feed-cover img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.cover-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #333;
  border-top-color: #10b981;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

.no-video-badge {
  background: rgba(0, 0, 0, 0.6);
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  color: #aaa;
}

/* ===== 右侧互动栏 ===== */
.feed-actions {
  position: absolute;
  right: 12px;
  bottom: 140px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  z-index: 10;
}
.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #fff;
  filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.5));
}
.action-item span {
  font-size: 12px;
}

/* ===== 底部信息 ===== */
.feed-info {
  position: absolute;
  left: 12px;
  bottom: 40px;
  right: 80px;
  z-index: 10;
  text-shadow: 0 1px 3px rgb(0 0 0 / 0.6);
}
.feed-author {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
}
.feed-title {
  font-size: 13px;
  color: #ddd;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ===== 底部哨兵 ===== */
.feed-sentinel {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  scroll-snap-align: none;
}
.end-hint {
  color: #444;
  font-size: 13px;
}

/* ===== 响应式 - 移动端 ===== */
@media (max-width: 768px) {
  .user-panel {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 200;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: 4px 0 20px rgb(0 0 0 / 0.5);
  }
  .user-panel.open {
    transform: translateX(0);
  }

  .panel-close {
    display: block;
  }

  .panel-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    z-index: 199;
  }

  .fab-avatar {
    display: flex;
  }

  .feed-actions {
    right: 8px;
    bottom: 120px;
  }

  .feed-info {
    left: 8px;
    bottom: 30px;
    right: 60px;
  }
}

/* 用户列表自定义滚动条（暗色） */
.user-list::-webkit-scrollbar {
  width: 4px;
}
.user-list::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}
.user-list::-webkit-scrollbar-track {
  background: transparent;
}
</style>
