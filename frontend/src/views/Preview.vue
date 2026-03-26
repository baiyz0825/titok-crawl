<template>
  <div class="preview-container">
    <!-- 桌面端用户面板 -->
    <aside class="user-panel" :class="{ open: panelOpen }">
      <div class="panel-header">
        <h3>{{ feedMode === 'global' ? '全局 Feed' : '选择用户' }}</h3>
        <div class="panel-header-actions">
          <button
            class="mode-btn"
            :class="{ active: feedMode === 'global' }"
            @click="toggleFeedMode"
            :title="feedMode === 'global' ? '切换到单用户模式' : '切换到全局模式'"
          >
            <svg v-if="feedMode === 'global'" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12" stroke="#1a1a1a" stroke-width="2"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" fill="none" stroke="#1a1a1a" stroke-width="2"/></svg>
            <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          </button>
          <button
            class="auto-play-btn"
            :class="{ active: autoPlayEnabled }"
            @click="autoPlayEnabled = !autoPlayEnabled"
            :title="autoPlayEnabled ? '关闭自动播放' : '开启自动播放'"
          >
            <svg v-if="autoPlayEnabled" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
            <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          </button>
          <button class="panel-close" @click="panelOpen = false">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
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
          :key="user.uid || user.sec_user_id"
          class="user-item"
          :class="{ active: (selectedUser?.uid || selectedUser?.sec_user_id) === (user.uid || user.sec_user_id) }"
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
            <div class="user-meta">{{ userStats[user.uid || user.sec_user_id]?.works_count ?? (user.aweme_count || 0) }} 作品</div>
          </div>
        </div>
        <div v-if="filteredUsers.length === 0 && !loadingUsers" class="empty-hint">
          {{ searchQuery ? '无匹配用户' : '暂无用户数据' }}
        </div>
        <div v-if="loadingUsers" class="loading-hint">加载中...</div>
      </div>

      <!-- 选中用户统计信息 -->
      <div v-if="selectedUser && selectedUserDetail" class="user-stats-bar">
        <div class="stat-item">
          <span class="stat-num">{{ selectedUserDetail.works_count }}</span>
          <span class="stat-label">作品</span>
        </div>
        <div class="stat-item">
          <span class="stat-num">{{ selectedUserDetail.comments_count }}</span>
          <span class="stat-label">评论</span>
        </div>
        <div class="stat-item">
          <span class="stat-num">{{ selectedUserDetail.media_count }}</span>
          <span class="stat-label">媒体</span>
        </div>
      </div>
    </aside>

    <!-- 移动端面板遮罩 -->
    <div v-if="panelOpen" class="panel-overlay" @click="panelOpen = false"></div>

    <!-- 移动端导航栏 -->
    <div class="mobile-nav">
      <!-- 返回按钮 -->
      <button class="mobile-back-btn" @click="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
        <span>返回</span>
      </button>
      <!-- 模式切换按钮 -->
      <button
        class="mobile-mode-btn"
        :class="{ active: feedMode === 'global' }"
        @click="toggleFeedMode"
      >
        <svg v-if="feedMode === 'global'" viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12" stroke="#1a1a1a" stroke-width="2"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" fill="none" stroke="#1a1a1a" stroke-width="2"/></svg>
        <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </button>
      <!-- 自动播放按钮 -->
      <button
        class="mobile-auto-play-btn"
        :class="{ active: autoPlayEnabled }"
        @click="autoPlayEnabled = !autoPlayEnabled"
      >
        <svg v-if="autoPlayEnabled" viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
      </button>
      <!-- 浮动头像按钮 -->
      <button class="fab-avatar" @click="panelOpen = true">
        <img
          v-if="selectedUser?.avatar_url"
          :src="selectedUser.avatar_url"
          @error="(e: any) => e.target.style.display = 'none'"
        />
        <svg v-else viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      </button>
    </div>

    <!-- 视频 Feed -->
    <div class="feed-container" ref="feedRef">
      <div v-if="feedMode === 'user' && !selectedUser" class="feed-empty">
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
            :muted="isMuted"
            playsinline
            preload="auto"
            :poster="work.cover_url"
            @click="togglePlay($event)"
            @loadeddata="onVideoLoaded($event, work)"
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
            <div class="action-item" @click.stop="toggleMute">
              <svg v-if="isMuted" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
              <svg v-else viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
              <span>{{ isMuted ? '静音' : '声音' }}</span>
            </div>
            <div class="action-item" @click.stop="toggleFavorite(work)">
              <svg v-if="favoriteStatus[work.aweme_id]" viewBox="0 0 24 24" width="28" height="28" fill="#ef4444" stroke="#ef4444" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
              <svg v-else viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
              <span>{{ formatCount(work.digg_count) }}</span>
            </div>
            <div class="action-item" @click.stop="openComments(work)">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              <span>{{ formatCount(work.comment_count) }}</span>
            </div>
            <div class="action-item">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
              <span>{{ formatCount(work.collect_count) }}</span>
            </div>
          </div>

          <!-- 底部信息 -->
          <div class="feed-info">
            <!-- 全局模式显示作者信息（可点击） -->
            <div
              v-if="feedMode === 'global' && work._author"
              class="feed-author-row clickable"
              @click.stop="selectAuthor(work._author)"
            >
              <img
                v-if="work._author.avatar_url"
                :src="work._author.avatar_url"
                class="feed-author-avatar"
                @error="(e: any) => e.target.style.display = 'none'"
              />
              <div v-else class="feed-author-avatar-placeholder">{{ (work._author.nickname || '?')[0] }}</div>
              <span class="feed-author">@{{ work._author.nickname || '未知用户' }}</span>
            </div>
            <!-- 单用户模式显示作者 -->
            <div v-else class="feed-author">@{{ selectedUser?.nickname || '' }}</div>
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

    <!-- 评论面板（仿抖音） -->
    <div v-if="commentPanelOpen" class="comment-overlay" @click.self="closeComments">
      <div class="comment-panel" :class="{ open: commentPanelOpen }">
        <div class="comment-panel-header">
          <span class="comment-panel-count">{{ commentTotal }} 条评论</span>
          <button class="comment-panel-close" @click="closeComments">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="comment-list" v-if="!loadingComments && commentTree.length > 0">
          <div v-for="comment in commentTree" :key="comment.comment_id" class="comment-item">
            <img
              v-if="comment.user_avatar"
              :src="comment.user_avatar"
              class="comment-avatar"
              @error="(e: any) => e.target.style.display = 'none'"
            />
            <div v-else class="comment-avatar-placeholder">{{ (comment.user_nickname || '?')[0] }}</div>
            <div class="comment-body">
              <div class="comment-nickname">{{ comment.user_nickname || '匿名' }}
                <span v-if="comment.ip_label" class="comment-ip">{{ comment.ip_label }}</span>
              </div>
              <div class="comment-content">{{ comment.content }}</div>
              <div class="comment-meta">
                <span class="comment-time">{{ formatTime(comment.create_time) }}</span>
                <span v-if="comment.digg_count" class="comment-likes">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                  {{ comment.digg_count }}
                </span>
              </div>
              <!-- 子评论 -->
              <div v-if="comment.children && comment.children.length > 0" class="comment-replies">
                <div v-for="reply in comment.children" :key="reply.comment_id" class="reply-item">
                  <img
                    v-if="reply.user_avatar"
                    :src="reply.user_avatar"
                    class="reply-avatar"
                    @error="(e: any) => e.target.style.display = 'none'"
                  />
                  <div v-else class="reply-avatar-placeholder">{{ (reply.user_nickname || '?')[0] }}</div>
                  <div class="reply-body">
                    <div class="comment-nickname">{{ reply.user_nickname || '匿名' }}
                      <span v-if="reply.ip_label" class="comment-ip">{{ reply.ip_label }}</span>
                    </div>
                    <div class="comment-content">{{ reply.content }}</div>
                    <div class="comment-meta">
                      <span class="comment-time">{{ formatTime(reply.create_time) }}</span>
                      <span v-if="reply.digg_count" class="comment-likes">
                        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                        {{ reply.digg_count }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="loadingComments" class="comment-loading">
          <div class="loading-spinner"></div>
        </div>
        <div v-else class="comment-empty">暂无评论</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import client from '../api/client'

const router = useRouter()

// --- 状态 ---
const feedMode = ref<'user' | 'global'>('user')  // 'user' 单用户模式, 'global' 全局模式
const loadingUsers = ref(false)
const loadingWorks = ref(false)
const users = ref<any[]>([])
const searchQuery = ref('')
const selectedUser = ref<any>(null)
const selectedUserDetail = ref<any>(null)
const userStats = ref<Record<string, any>>({})
const works = ref<any[]>([])
const page = ref(1)
const hasMore = ref(true)
const panelOpen = ref(false)

// 评论面板
const commentPanelOpen = ref(false)
const commentTree = ref<any[]>([])
const commentTotal = ref(0)
const loadingComments = ref(false)

// 收藏功能
const favoriteStatus = ref<Record<string, boolean>>({})

// 自动播放控制
const autoPlayEnabled = ref(true)

// 音量控制
const isMuted = ref(true)

const feedRef = ref<HTMLDivElement | null>(null)
const sentinelRef = ref<HTMLDivElement | null>(null)

// --- 用户列表 ---
const filteredUsers = computed(() => {
  let result = users.value
  // 搜索过滤
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(
      (u: any) =>
        (u.nickname || '').toLowerCase().includes(q) ||
        (u.sec_user_id || '').toLowerCase().includes(q) ||
        (u.douyin_id || '').toLowerCase().includes(q)
    )
  }
  // 按昵称字母排序
  return [...result].sort((a, b) => {
    const nameA = (a.nickname || '').toLowerCase()
    const nameB = (b.nickname || '').toLowerCase()
    return nameA.localeCompare(nameB, 'zh-CN')
  })
})

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res: any = await client.get('/users', { params: { size: 200 } })
    users.value = res.items || res || []
  } catch { /* handled by interceptor */ }
  loadingUsers.value = false
}

async function selectUser(user: any) {
  selectedUser.value = user
  panelOpen.value = false
  works.value = []
  page.value = 1
  hasMore.value = true
  selectedUserDetail.value = null

  // 如果当前是全局模式，切换到单用户模式
  if (feedMode.value === 'global') {
    feedMode.value = 'user'
  }

  // 获取用户详细统计
  const userKey = user.uid || user.sec_user_id
  try {
    const detail: any = await client.get(`/users/${userKey}`)
    selectedUserDetail.value = detail.scrape_status || null
    userStats.value[userKey] = detail.scrape_status || {}
  } catch { /* ignore */ }

  loadWorks()
}

// --- 模式切换 ---
function toggleFeedMode() {
  const newMode = feedMode.value === 'user' ? 'global' : 'user'
  feedMode.value = newMode

  // 清空当前状态
  works.value = []
  page.value = 1
  hasMore.value = true

  // 如果切换到单用户模式，清空选中用户
  if (newMode === 'user') {
    selectedUser.value = null
    selectedUserDetail.value = null
  }

  // 重新加载视频
  loadWorks()
}

// --- 作品列表 ---
async function loadWorks() {
  // 单用户模式需要选择用户，全局模式不需要
  if (feedMode.value === 'user' && !selectedUser.value) return
  if (loadingWorks.value || !hasMore.value) return

  loadingWorks.value = true
  try {
    const params: any = {
      page: page.value,
      size: 20,
    }

    if (feedMode.value === 'user') {
      // 单用户模式：添加用户参数
      if (selectedUser.value.uid) {
        params.uid = selectedUser.value.uid
      } else if (selectedUser.value.sec_user_id) {
        params.sec_user_id = selectedUser.value.sec_user_id
      }
    }
    // 全局模式：不添加用户参数，加载所有用户的视频

    const res: any = await client.get('/works', { params })
    let items = res.items || res || []

    if (items.length === 0) {
      hasMore.value = false
    } else {
      // 全局模式：按发布时间排序（最新的在前）
      if (feedMode.value === 'global') {
        items = items.sort((a: any, b: any) => {
          const timeA = new Date(a.create_time || 0).getTime()
          const timeB = new Date(b.create_time || 0).getTime()
          return timeB - timeA
        })
      }

      // 添加内部状态字段
      items.forEach((w: any) => {
        w._videoUrl = null
        w._loading = false
        w._noVideo = false
        w._loaded = false

        // 全局模式：从users列表中查找作者信息
        if (feedMode.value === 'global') {
          const author = users.value.find(
            (u: any) => u.uid === w.uid || u.sec_user_id === w.sec_user_id
          )
          w._author = author ? {
            uid: w.uid,
            sec_user_id: w.sec_user_id,
            nickname: author.nickname,
            avatar_url: author.avatar_url
          } : null
        }

        // 检查收藏状态
        checkFavoriteStatus(w.aweme_id)
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
let currentVideoIndex = ref<number | null>(null)

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
            // 更新当前视频索引
            currentVideoIndex.value = idx

            // 懒加载视频 URL
            if (!work._loaded && !work._loading) {
              loadVideoUrl(work)
            }
            // 注意：不在这里尝试播放,
            // 自动播放将在 @loadeddata 事件中处理
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

  // 视频加载完成后，如果启用自动播放且卡片在视口内，自动播放
  if (autoPlayEnabled.value && work._videoUrl) {
    await nextTick()
    const card = feedRef.value?.querySelector(`[data-aweme-id="${work.aweme_id}"]`)
    if (card) {
      const video = card.querySelector('video')
      if (video) {
        video.play().catch(() => {})
      }
    }
  }
}

// --- 评论面板 ---
async function openComments(work: any) {
  commentPanelOpen.value = true
  commentTree.value = []
  commentTotal.value = 0
  loadingComments.value = true
  try {
    const res: any = await client.get(`/works/${work.aweme_id}/comments`, {
      params: { size: 500 },
    })
    commentTree.value = res.items || []
    commentTotal.value = res.total || 0
  } catch { /* handled by interceptor */ }
  loadingComments.value = false
}

function closeComments() {
  commentPanelOpen.value = false
  commentTree.value = []
}

// --- 全局模式下点击作者切换到单用户模式 ---
function selectAuthor(author: any) {
  // 从用户列表中查找对应的用户
  const user = users.value.find(
    (u: any) => u.uid === author.uid || u.sec_user_id === author.sec_user_id
  )

  if (user) {
    // 切换到单用户模式
    feedMode.value = 'user'
    // 选中该用户
    selectUser(user)
  }
}

// --- 收藏功能 ---
async function checkFavoriteStatus(aweme_id: string) {
  try {
    const res: any = await client.get(`/favorites/${aweme_id}/check`)
    favoriteStatus.value[aweme_id] = res.favorited
  } catch {
    favoriteStatus.value[aweme_id] = false
  }
}

async function toggleFavorite(work: any) {
  const aweme_id = work.aweme_id
  const isFav = favoriteStatus.value[aweme_id]

  try {
    if (isFav) {
      await client.delete(`/favorites/${aweme_id}`)
      favoriteStatus.value[aweme_id] = false
    } else {
      await client.post(`/favorites/${aweme_id}`)
      favoriteStatus.value[aweme_id] = true
    }
  } catch {
    // 忽略错误，保持原状态
  }
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

// --- 音量控制 ---
function toggleMute() {
  isMuted.value = !isMuted.value

  // 立即应用音量变化到当前播放的视频
  if (currentVideoIndex.value !== null) {
    const card = feedRef.value?.querySelector(`[data-index="${currentVideoIndex.value}"]`)
    if (card) {
      const video = card.querySelector('video') as HTMLVideoElement
      if (video) {
        video.muted = isMuted.value
      }
    }
  }
}

// 视频数据加载完成后自动播放
function onVideoLoaded(e: Event, work: any) {
  if (!autoPlayEnabled.value || !work._videoUrl) return
  const video = e.target as HTMLVideoElement
  // 检查视频是否在视口内
  const card = video.closest('.feed-card')
  if (card) {
    const rect = card.getBoundingClientRect()
    const inViewport = rect.top < window.innerHeight * 0.7 && rect.bottom > window.innerHeight * 0.3
    if (inViewport) {
      video.play().catch(() => {})
    }
  }
}

// --- 格式化 ---
function formatCount(n: number | undefined): string {
  if (!n) return '0'
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function formatTime(t: string | undefined): string {
  if (!t) return ''
  try {
    const d = new Date(t)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
    if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
    if (diff < 2592000000) return Math.floor(diff / 86400000) + '天前'
    return d.toLocaleDateString('zh-CN')
  } catch {
    return ''
  }
}

// --- 导航 ---
function goBack() {
  router.push('/users')
}

// --- 生命周期 ---
onMounted(async () => {
  await loadUsers()
  // 预加载所有用户的统计信息
  await loadAllUserStats()
})

async function loadAllUserStats() {
  // 为每个用户加载统计信息（使用 Promise.all 并发）
  const promises = users.value.map(async (user) => {
    const userKey = user.uid || user.sec_user_id
    try {
      const detail: any = await client.get(`/users/${userKey}`)
      userStats.value[userKey] = detail.scrape_status || {}
    } catch {
      // 如果获取失败，使用 aweme_count 作为后备
      userStats.value[userKey] = { works_count: user.aweme_count || 0 }
    }
  })
  await Promise.all(promises)
}

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
.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.auto-play-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: none;
  border: 1px solid #333;
  border-radius: 6px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}
.auto-play-btn:hover {
  background: #252525;
  color: #888;
}
.auto-play-btn.active {
  background: rgba(16, 185, 129, 0.2);
  border-color: #10b981;
  color: #10b981;
}

.mode-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: none;
  border: 1px solid #333;
  border-radius: 6px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}
.mode-btn:hover {
  background: #252525;
  color: #888;
}
.mode-btn.active {
  background: rgba(59, 130, 246, 0.2);
  border-color: #3b82f6;
  color: #3b82f6;
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

/* ===== 用户统计栏 ===== */
.user-stats-bar {
  display: flex;
  justify-content: space-around;
  padding: 12px 8px;
  border-top: 1px solid #2a2a2a;
  background: #1a1a1a;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.stat-num {
  font-size: 15px;
  font-weight: 700;
  color: #10b981;
}
.stat-label {
  font-size: 11px;
  color: #666;
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

/* ===== 移动端导航栏 ===== */
.mobile-nav {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 48px;
  background: rgba(15, 15, 15, 0.95);
  backdrop-filter: blur(10px);
  z-index: 98;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.mobile-back-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: rgba(16, 185, 129, 0.2);
  border: 1px solid #10b981;
  color: #10b981;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.mobile-back-btn:hover {
  background: rgba(16, 185, 129, 0.3);
}

.mobile-back-btn:active {
  transform: scale(0.96);
}

.mobile-auto-play-btn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid #333;
  border-radius: 50%;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.mobile-auto-play-btn.active {
  background: rgba(16, 185, 129, 0.2);
  border-color: #10b981;
  color: #10b981;
}

.mobile-mode-btn {
  display: none;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid #333;
  border-radius: 50%;
  color: #888;
  cursor: pointer;
  transition: all 0.2s;
}

.mobile-mode-btn.active {
  background: rgba(59, 130, 246, 0.2);
  border-color: #3b82f6;
  color: #3b82f6;
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
  cursor: pointer;
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
.feed-author-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.feed-author-row.clickable {
  cursor: pointer;
  padding: 4px 8px;
  margin-left: -8px;
  border-radius: 20px;
  transition: background 0.2s;
}
.feed-author-row.clickable:hover {
  background: rgba(255, 255, 255, 0.1);
}
.feed-author-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
  border: 1.5px solid rgba(255, 255, 255, 0.3);
}
.feed-author-avatar-placeholder {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #333;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #888;
  border: 1.5px solid rgba(255, 255, 255, 0.3);
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

/* ===== 评论面板（仿抖音） ===== */
.comment-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.comment-panel {
  width: 100%;
  max-width: 500px;
  max-height: 70vh;
  background: #1e1e1e;
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.comment-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px 12px;
  border-bottom: 1px solid #2a2a2a;
  flex-shrink: 0;
}
.comment-panel-count {
  font-size: 14px;
  font-weight: 600;
  color: #ddd;
}
.comment-panel-close {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  padding: 4px;
}

.comment-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.comment-item {
  display: flex;
  gap: 10px;
  padding: 10px 0;
}

.comment-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.comment-avatar-placeholder {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #333;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #888;
  flex-shrink: 0;
}

.comment-body {
  flex: 1;
  min-width: 0;
}
.comment-nickname {
  font-size: 13px;
  font-weight: 500;
  color: #888;
  margin-bottom: 4px;
}
.comment-ip {
  font-size: 11px;
  color: #555;
  margin-left: 6px;
}
.comment-content {
  font-size: 14px;
  color: #eee;
  line-height: 1.5;
  word-break: break-all;
}
.comment-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
  font-size: 11px;
  color: #555;
}
.comment-likes {
  display: flex;
  align-items: center;
  gap: 3px;
}
.comment-time {
  color: #555;
}

/* 子评论 */
.comment-replies {
  margin-top: 10px;
  padding-left: 4px;
  border-left: 2px solid #2a2a2a;
}
.reply-item {
  display: flex;
  gap: 8px;
  padding: 8px 0 8px 8px;
}
.reply-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.reply-avatar-placeholder {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #333;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #888;
  flex-shrink: 0;
}
.reply-body {
  flex: 1;
  min-width: 0;
}

.comment-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.comment-empty {
  text-align: center;
  color: #555;
  font-size: 14px;
  padding: 40px 0;
}

/* 评论列表自定义滚动条 */
.comment-list::-webkit-scrollbar {
  width: 4px;
}
.comment-list::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}
.comment-list::-webkit-scrollbar-track {
  background: transparent;
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

  .mobile-nav {
    display: flex;
  }

  .mobile-auto-play-btn {
    display: flex;
  }

  .mobile-mode-btn {
    display: flex;
  }

  .fab-avatar {
    display: flex;
    position: static;
    width: 36px;
    height: 36px;
    border-width: 1.5px;
  }

  .feed-container {
    padding-top: 48px;
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

  .comment-panel {
    max-width: 100%;
    max-height: 65vh;
  }

  .comment-panel-close {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
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
