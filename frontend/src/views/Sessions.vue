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

      <el-button
        :type="loggedIn ? 'default' : 'primary'"
        size="large"
        @click="triggerLogin"
        :loading="loginLoading"
        style="width: 200px"
      >
        {{ loggedIn ? '重新登录' : '扫码登录' }}
      </el-button>

      <div v-if="loginMessage" class="login-hint">
        <el-icon :size="16"><InfoFilled /></el-icon>
        {{ loginMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import client from '../api/client'

const loggedIn = ref(false)
const loginLoading = ref(false)
const loginMessage = ref('')

async function checkStatus() {
  const res: any = await client.get('/sessions/status')
  loggedIn.value = res.logged_in
}

async function triggerLogin() {
  loginLoading.value = true
  loginMessage.value = '浏览器已打开，请在抖音页面扫码登录...'
  try {
    const force = loggedIn.value
    const res: any = await client.post(`/sessions/login?force=${force}`)
    if (res.logged_in) {
      loggedIn.value = true
      loginMessage.value = ''
      ElMessage.success('登录成功')
    } else {
      loginMessage.value = '登录超时，请重试'
    }
  } finally {
    loginLoading.value = false
  }
}

onMounted(checkStatus)
</script>

<style scoped>
.page { padding: 28px 32px; max-width: 1200px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.session-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 40px;
  max-width: 480px;
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

.login-hint {
  display: flex; align-items: center; gap: 6px;
  padding: 12px 16px; background: #eff6ff; border-radius: 8px;
  color: #2563eb; font-size: 13px; width: 100%;
}
</style>
