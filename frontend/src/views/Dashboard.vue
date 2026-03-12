<template>
  <div class="page">
    <div class="page-header">
      <h1>系统概览</h1>
      <p class="page-subtitle">实时数据监控与统计</p>
    </div>

    <div class="stats-grid">
      <div class="stat-card" v-for="stat in statCards" :key="stat.label">
        <div class="stat-icon" :style="{ background: stat.bg, color: stat.color }">
          <el-icon :size="24"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stat.value }}</span>
          <span class="stat-label">{{ stat.label }}</span>
        </div>
      </div>
    </div>

    <div class="content-grid">
      <div class="card">
        <div class="card-header">
          <h3>任务状态</h3>
        </div>
        <div class="task-stats">
          <div class="task-stat-item">
            <span class="task-stat-dot" style="background: #3b82f6"></span>
            <span class="task-stat-label">等待中</span>
            <span class="task-stat-value">{{ overview.tasks?.pending ?? 0 }}</span>
          </div>
          <div class="task-stat-item">
            <span class="task-stat-dot" style="background: #f59e0b"></span>
            <span class="task-stat-label">运行中</span>
            <span class="task-stat-value">{{ overview.tasks?.running ?? 0 }}</span>
          </div>
          <div class="task-stat-item">
            <span class="task-stat-dot" style="background: #22c55e"></span>
            <span class="task-stat-label">已完成</span>
            <span class="task-stat-value">{{ overview.tasks?.completed ?? 0 }}</span>
          </div>
          <div class="task-stat-item">
            <span class="task-stat-dot" style="background: #ef4444"></span>
            <span class="task-stat-label">失败</span>
            <span class="task-stat-value">{{ overview.tasks?.failed ?? 0 }}</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3>登录状态</h3>
        </div>
        <div class="login-status">
          <div class="login-indicator" :class="loginStatus === 'logged_in' ? 'online' : 'offline'">
            <span class="login-dot"></span>
            <span>{{ loginStatus === 'logged_in' ? '已连接抖音' : '未登录' }}</span>
          </div>
          <router-link to="/sessions" class="login-link">
            {{ loginStatus === 'logged_in' ? '管理会话' : '前往登录' }} →
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { User, VideoCamera, Document, List } from '@element-plus/icons-vue'
import client from '../api/client'

const overview = ref<any>({})
const loginStatus = ref('unknown')

const statCards = computed(() => [
  { label: '用户数', value: overview.value.users_count ?? '-', icon: User, bg: '#ecfdf5', color: '#059669' },
  { label: '作品数', value: overview.value.works_count ?? '-', icon: VideoCamera, bg: '#eff6ff', color: '#2563eb' },
  { label: '媒体文件', value: overview.value.media_files_count ?? '-', icon: Document, bg: '#fefce8', color: '#ca8a04' },
  { label: '任务总数', value: overview.value.tasks?.total ?? '-', icon: List, bg: '#faf5ff', color: '#9333ea' },
])

async function fetchOverview() {
  overview.value = await client.get('/analysis/overview')
}
async function fetchLoginStatus() {
  const res: any = await client.get('/sessions/status')
  loginStatus.value = res.logged_in ? 'logged_in' : 'not_logged_in'
}

onMounted(() => { fetchOverview(); fetchLoginStatus() })
</script>

<style scoped>
.page { padding: 28px 32px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: border-color 0.2s;
}
.stat-card:hover { border-color: #cbd5e1; }
.stat-icon {
  width: 48px; height: 48px;
  border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.stat-info { display: flex; flex-direction: column; }
.stat-value { font-size: 28px; font-weight: 700; color: #0f172a; line-height: 1.2; }
.stat-label { font-size: 13px; color: #64748b; margin-top: 2px; }

.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 24px;
}
.card-header h3 { font-size: 16px; font-weight: 600; color: #0f172a; margin: 0 0 20px; }

.task-stats { display: flex; flex-direction: column; gap: 14px; }
.task-stat-item { display: flex; align-items: center; gap: 10px; }
.task-stat-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.task-stat-label { flex: 1; color: #64748b; font-size: 14px; }
.task-stat-value { font-size: 18px; font-weight: 600; color: #0f172a; }

.login-status { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 20px 0; }
.login-indicator { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 500; color: #334155; }
.login-dot { width: 10px; height: 10px; border-radius: 50%; }
.login-indicator.online .login-dot { background: #22c55e; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.2); }
.login-indicator.offline .login-dot { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.2); }
.login-link { color: #10b981; font-size: 14px; text-decoration: none; font-weight: 500; }
.login-link:hover { color: #059669; }

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .stat-card { padding: 14px; gap: 10px; }
  .stat-icon { width: 40px; height: 40px; }
  .stat-value { font-size: 22px; }
  .content-grid { grid-template-columns: 1fr; gap: 12px; }
  .card { padding: 16px; }
}
@media (min-width: 769px) and (max-width: 1024px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
