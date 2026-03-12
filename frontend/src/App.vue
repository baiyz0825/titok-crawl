<template>
  <div class="layout">
    <!-- 移动端汉堡按钮 (预览页隐藏) -->
    <button v-if="route.path !== '/preview'" class="hamburger" @click="sidebarOpen = true">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="21" y2="6"/>
        <line x1="3" y1="12" x2="21" y2="12"/>
        <line x1="3" y1="18" x2="21" y2="18"/>
      </svg>
    </button>

    <!-- 移动端遮罩 -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <aside class="sidebar" :class="{ open: sidebarOpen }">
      <div class="sidebar-header">
        <div class="logo">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
          <span>抖音采集器</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.path === item.path }"
          @click="sidebarOpen = false"
        >
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="version-badge">v1.0.0</div>
      </div>
    </aside>

    <main class="main-content" :class="{ 'preview-mode': route.path === '/preview' }">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { Odometer, User, VideoCamera, List, Key, Search, Timer, Document, VideoPlay } from '@element-plus/icons-vue'

const route = useRoute()
const sidebarOpen = ref(false)

const menuItems = [
  { path: '/dashboard', label: '概览', icon: Odometer },
  { path: '/search', label: '搜索', icon: Search },
  { path: '/users', label: '用户', icon: User },
  { path: '/works', label: '作品', icon: VideoCamera },
  { path: '/tasks', label: '任务', icon: List },
  { path: '/schedules', label: '定时任务', icon: Timer },
  { path: '/logs', label: '日志', icon: Document },
  { path: '/sessions', label: '登录', icon: Key },
  { path: '/preview', label: '预览', icon: VideoPlay },
]
</script>

<style>
/* Import theme - no scoped for global effect */
@import './styles/theme.css';
</style>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.hamburger {
  display: none;
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 1001;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  color: #334155;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.1);
}

.sidebar-overlay {
  display: none;
}

.sidebar {
  width: 240px;
  min-width: 240px;
  background: #ffffff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 20px 20px 16px;
  border-bottom: 1px solid #f1f5f9;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.logo svg {
  color: #10b981;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  color: #64748b;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
  position: relative;
}
.nav-item:hover {
  background: #f1f5f9;
  color: #334155;
}
.nav-item.active {
  background: #ecfdf5;
  color: #059669;
  font-weight: 600;
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  background: #10b981;
  border-radius: 0 3px 3px 0;
}
.nav-item .el-icon {
  flex-shrink: 0;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid #f1f5f9;
}
.version-badge {
  font-size: 11px;
  color: #94a3b8;
  text-align: center;
}

.main-content {
  flex: 1;
  background: #f8fafc;
  overflow-y: auto;
  overflow-x: hidden;
}

.main-content.preview-mode {
  background: #0f0f0f;
  overflow: hidden;
}

@media (max-width: 768px) {
  .hamburger {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }

  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    box-shadow: 4px 0 12px rgb(0 0 0 / 0.1);
  }
  .sidebar.open {
    transform: translateX(0);
  }

  .main-content {
    width: 100%;
  }
}
</style>
