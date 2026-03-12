<template>
  <div class="page">
    <div class="page-header">
      <h1>登录管理</h1>
      <p class="page-subtitle">管理抖音账号登录会话</p>
    </div>

    <!-- 已登录用户信息卡片 -->
    <div v-if="currentUser && loggedIn" class="user-card">
      <div class="user-avatar">
        <img :src="currentUser.avatar_url || '/default-avatar.png'" :alt="currentUser.nickname" />
      </div>
      <div class="user-info">
        <h3 class="user-name">{{ currentUser.nickname || '未知用户' }}</h3>
        <div class="user-meta">
          <span class="user-id">抖音号：{{ currentUser.douyin_id || secUserIdShort }}</span>
          <span class="sec-user-id" :title="currentUser.sec_user_id">ID: {{ secUserIdShort }}</span>
        </div>
        <div v-if="currentUser.signature" class="user-signature">{{ currentUser.signature }}</div>
        <div class="user-stats">
          <div class="stat-item">
            <span class="stat-label">关注</span>
            <span class="stat-value">{{ formatNumber(currentUser.following_count) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">粉丝</span>
            <span class="stat-value">{{ formatNumber(currentUser.follower_count) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">获赞</span>
            <span class="stat-value">{{ formatNumber(currentUser.total_favorited) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="session-card">
      <div class="status-section">
        <div class="status-indicator" :class="loggedIn ? 'online' : 'offline'">
          <span class="status-dot"></span>
          <span class="status-text">{{ loggedIn ? '已登录' : '未登录' }}</span>
        </div>
        <p class="status-desc">{{ loggedIn ? '会话有效，可正常采集数据' : '请扫码登录以开始使用' }}</p>
      </div>

      <!-- 未在登录流程中 -->
      <el-button
        v-if="!streaming"
        :type="loggedIn ? 'default' : 'primary'"
        size="large"
        @click="startLoginStream"
        style="width: 200px"
      >
        {{ loggedIn ? '重新登录' : '扫码登录' }}
      </el-button>

      <!-- 登录流程中：状态显示 -->
      <div v-if="streaming" class="login-stream">
        <!-- 二维码阶段 -->
        <template v-if="phase === 'qrcode'">
          <div v-if="screenshotImage" class="screenshot-container">
            <img :src="screenshotImage" class="screenshot-image" alt="二维码" />
            <p class="placeholder-text">请用抖音 App 扫描二维码</p>
          </div>
          <div v-else class="qrcode-placeholder">
            <el-icon :size="48" color="#94a3b8"><Monitor /></el-icon>
            <p class="placeholder-text">正在加载二维码...</p>
          </div>
        </template>

        <!-- 验证码阶段 -->
        <template v-else-if="phase === 'verify'">
          <div v-if="screenshotImage" class="screenshot-container">
            <img :src="screenshotImage" class="screenshot-image" alt="验证码" />
            <p class="placeholder-text">验证码已发送至 {{ verifyPhone }}</p>
          </div>
          <div v-else class="verify-placeholder">
            <el-icon :size="48" color="#94a3b8"><Iphone /></el-icon>
            <p class="placeholder-text">验证码已发送至 {{ verifyPhone }}</p>
          </div>
        </template>

        <!-- 成功阶段 -->
        <template v-else-if="phase === 'success'">
          <div class="success-placeholder">
            <el-icon :size="48" color="#22c55e"><CircleCheckFilled /></el-icon>
            <p class="placeholder-text">登录成功</p>
          </div>
        </template>

        <!-- 超时阶段 -->
        <template v-else-if="phase === 'timeout'">
          <div class="timeout-placeholder">
            <el-icon :size="48" color="#ef4444"><WarningFilled /></el-icon>
            <p class="placeholder-text">登录超时，请重试</p>
          </div>
        </template>

        <!-- 验证码输入 -->
        <div v-if="phase === 'verify'" class="verify-input">
          <el-input
            v-model="verifyCode"
            placeholder="请输入验证码"
            maxlength="6"
            size="large"
            style="width: 200px"
            @keyup.enter="submitCode"
          />
          <el-button type="primary" size="large" @click="submitCode" :loading="codeLoading">
            确认
          </el-button>
        </div>

        <!-- 取消按钮 -->
        <el-button v-if="phase !== 'success'" @click="stopStream" size="default">
          取消登录
        </el-button>
      </div>

      <div v-if="loginMessage && !streaming" class="login-hint">
        <el-icon :size="16"><InfoFilled /></el-icon>
        {{ loginMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Monitor, Iphone, CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import client from '../api/client'

const loggedIn = ref(false)
const loginMessage = ref('')
const currentUser = ref<any>(null)

// 计算属性：显示简短的 sec_user_id
const secUserIdShort = computed(() => {
  if (!currentUser.value?.sec_user_id) return '未知'
  const id = currentUser.value.sec_user_id
  return id.length > 12 ? `${id.slice(0, 8)}...` : id
})

// 格式化数字
function formatNumber(num: number | undefined): string {
  if (!num) return '0'
  if (num >= 10000) {
    return `${(num / 10000).toFixed(1)}万`
  }
  return num.toString()
}

// SSE 登录流状态
const streaming = ref(false)
const phase = ref<'qrcode' | 'verify' | 'success' | 'timeout'>('qrcode')
const verifyPhone = ref('')
const verifyCode = ref('')
const codeLoading = ref(false)
const screenshotImage = ref('')

let eventSource: EventSource | null = null

async function checkStatus() {
  const res: any = await client.get('/sessions/status')
  loggedIn.value = res.logged_in

  // 如果已登录，获取当前用户信息
  if (res.logged_in) {
    await getCurrentUser()
  } else {
    currentUser.value = null
  }
}

async function getCurrentUser() {
  try {
    const res: any = await client.get('/sessions/current-user')
    currentUser.value = res
    console.log('[Sessions] Current user:', res)
  } catch (error: any) {
    console.error('[Sessions] Failed to get current user:', error)
    if (error.response?.status === 401) {
      currentUser.value = null
    }
  }
}

function startLoginStream() {
  streaming.value = true
  phase.value = 'qrcode'
  verifyCode.value = ''
  loginMessage.value = ''
  screenshotImage.value = ''

  eventSource = new EventSource('/api/sessions/login-stream')

  eventSource.addEventListener('status', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    console.log('[SSE] Status event:', data)  // 调试日志
    phase.value = data.phase

    if (data.phase === 'verify') {
      verifyPhone.value = data.phone || ''
    } else if (data.phase === 'success') {
      loggedIn.value = true
      ElMessage.success('登录成功')

      // 登录成功后获取用户信息
      setTimeout(async () => {
        await getCurrentUser()
        stopStream()
      }, 1000)
    } else if (data.phase === 'timeout') {
      loginMessage.value = '登录超时，请重试'
      setTimeout(() => stopStream(), 2000)
    }
  })

  eventSource.addEventListener('screenshot', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    console.log('[SSE] Screenshot received')
    screenshotImage.value = data.image || ''
  })

  eventSource.onerror = (error) => {
    console.error('[SSE] Error:', error)
    stopStream()
  }
}

function stopStream() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  streaming.value = false
}

async function submitCode() {
  if (!verifyCode.value) return
  codeLoading.value = true
  try {
    await client.post('/sessions/input-code', { code: verifyCode.value })
    verifyCode.value = ''
  } catch {
    ElMessage.error('验证码提交失败')
  } finally {
    codeLoading.value = false
  }
}

onMounted(checkStatus)
onUnmounted(stopStream)
</script>

<style scoped>
.page { padding: 28px 32px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

/* 用户信息卡片 */
.user-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.user-avatar {
  flex-shrink: 0;
}

.user-avatar img {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid #f1f5f9;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin: 0 0 8px 0;
}

.user-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 8px;
}

.user-id,
.sec-user-id {
  font-size: 13px;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 10px;
  border-radius: 6px;
}

.user-signature {
  font-size: 14px;
  color: #64748b;
  margin: 8px 0 16px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.user-stats {
  display: flex;
  gap: 24px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.session-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 40px;
  max-width: 680px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.status-section { text-align: center; }
.status-indicator {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 20px; border-radius: 20px;
  font-size: 16px; font-weight: 600;
}
.status-indicator.online { background: #ecfdf5; color: #059669; }
.status-indicator.offline { background: #fef2f2; color: #dc2626; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-indicator.online .status-dot { background: #22c55e; }
.status-indicator.offline .status-dot { background: #ef4444; }
.status-desc { color: #64748b; margin: 12px 0 0; font-size: 14px; }

.login-stream {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  width: 100%;
}

.qrcode-placeholder,
.verify-placeholder,
.success-placeholder,
.timeout-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 60px 40px;
  background: #f8fafc;
  border: 2px dashed #e2e8f0;
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
}

.placeholder-text {
  color: #475569;
  font-size: 16px;
  font-weight: 500;
  margin: 0;
}

.success-placeholder {
  background: #ecfdf5;
  border-color: #22c55e;
}

.success-placeholder .placeholder-text {
  color: #15803d;
}

.timeout-placeholder {
  background: #fef2f2;
  border-color: #ef4444;
}

.timeout-placeholder .placeholder-text {
  color: #b91c1c;
}

.phase-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: #eff6ff;
  border-radius: 8px;
  color: #2563eb;
  font-size: 14px;
  font-weight: 500;
}

.verify-input {
  display: flex;
  align-items: center;
  gap: 12px;
}

.login-hint {
  display: flex; align-items: center; gap: 6px;
  padding: 12px 16px; background: #eff6ff; border-radius: 8px;
  color: #2563eb; font-size: 13px; width: 100%;
}

.screenshot-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 20px;
  background: #ffffff;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  width: 100%;
  max-width: 500px;
}

.screenshot-image {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
}
</style>
