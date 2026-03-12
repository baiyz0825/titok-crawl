<template>
  <div class="page">
    <div class="page-header">
      <h1>登录管理</h1>
      <p class="page-subtitle">管理抖音账号登录会话</p>
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

      <!-- 登录流程中：截图 + 状态 -->
      <div v-if="streaming" class="login-stream">
        <div class="screenshot-wrapper">
          <img v-if="screenshot" :src="screenshot" class="screenshot" />
          <div v-else class="screenshot-placeholder">正在加载页面...</div>
        </div>

        <!-- 阶段提示 -->
        <div class="phase-hint">
          <template v-if="phase === 'qrcode'">
            <el-icon :size="16"><Monitor /></el-icon>
            请用抖音 App 扫描二维码
          </template>
          <template v-else-if="phase === 'verify'">
            <el-icon :size="16"><Iphone /></el-icon>
            请输入手机 {{ verifyPhone }} 收到的验证码
          </template>
          <template v-else-if="phase === 'success'">
            <el-icon :size="16"><CircleCheckFilled /></el-icon>
            登录成功
          </template>
          <template v-else-if="phase === 'timeout'">
            <el-icon :size="16"><WarningFilled /></el-icon>
            登录超时，请重试
          </template>
        </div>

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
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled, Monitor, Iphone, CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import client from '../api/client'

const loggedIn = ref(false)
const loginMessage = ref('')

// SSE 登录流状态
const streaming = ref(false)
const screenshot = ref('')
const phase = ref<'qrcode' | 'verify' | 'success' | 'timeout'>('qrcode')
const verifyPhone = ref('')
const verifyCode = ref('')
const codeLoading = ref(false)

let eventSource: EventSource | null = null

async function checkStatus() {
  const res: any = await client.get('/sessions/status')
  loggedIn.value = res.logged_in
}

function startLoginStream() {
  streaming.value = true
  screenshot.value = ''
  phase.value = 'qrcode'
  verifyCode.value = ''
  loginMessage.value = ''

  eventSource = new EventSource('/api/sessions/login-stream')

  eventSource.addEventListener('screenshot', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    screenshot.value = data.image
  })

  eventSource.addEventListener('status', (e: MessageEvent) => {
    const data = JSON.parse(e.data)
    phase.value = data.phase

    if (data.phase === 'verify') {
      verifyPhone.value = data.phone || ''
    } else if (data.phase === 'success') {
      loggedIn.value = true
      ElMessage.success('登录成功')
      setTimeout(() => stopStream(), 1500)
    } else if (data.phase === 'timeout') {
      loginMessage.value = '登录超时，请重试'
      setTimeout(() => stopStream(), 2000)
    }
  })

  eventSource.onerror = () => {
    stopStream()
  }
}

function stopStream() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  streaming.value = false
  screenshot.value = ''
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
  gap: 16px;
  width: 100%;
}

.screenshot-wrapper {
  width: 100%;
  max-width: 600px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}

.screenshot {
  width: 100%;
  display: block;
}

.screenshot-placeholder {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 14px;
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
</style>
