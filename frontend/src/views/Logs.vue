<template>
  <div class="page logs-layout">
    <div class="page-header">
      <h1>服务器日志</h1>
      <p class="page-subtitle">实时查看系统运行日志</p>
    </div>

    <div class="toolbar">
      <el-select v-model="levelFilter" clearable placeholder="全部级别" style="width: 130px">
        <el-option label="INFO" value="INFO" />
        <el-option label="WARNING" value="WARNING" />
        <el-option label="ERROR" value="ERROR" />
        <el-option label="DEBUG" value="DEBUG" />
      </el-select>
      <el-button :type="paused ? 'success' : 'default'" @click="paused = !paused">
        {{ paused ? '▶ 恢复' : '⏸ 暂停' }}
      </el-button>
      <el-button @click="logs = []">清屏</el-button>
      <el-button @click="loadHistory" :loading="loadingHistory">历史日志</el-button>
      <div style="flex:1"></div>
      <el-switch v-model="autoScroll" active-text="自动滚动" />
    </div>

    <div ref="logContainer" class="log-terminal">
      <div
        v-for="(log, i) in filteredLogs"
        :key="i"
        class="log-line"
        :class="'level-' + log.level.toLowerCase()"
      >
        <span class="log-time">{{ log.full_timestamp || log.timestamp }}</span>
        <span class="log-level">{{ log.level }}</span>
        <span class="log-name">{{ log.name }}</span>
        <span class="log-msg">{{ log.message }}</span>
      </div>
      <div v-if="!filteredLogs.length" class="log-empty">等待日志...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import client from '../api/client'

const logs = ref<any[]>([])
const levelFilter = ref('')
const paused = ref(false)
const autoScroll = ref(true)
const logContainer = ref<HTMLElement | null>(null)
const loadingHistory = ref(false)
let eventSource: EventSource | null = null

const filteredLogs = computed(() => {
  if (!levelFilter.value) return logs.value
  return logs.value.filter(l => l.level === levelFilter.value)
})

function scrollToBottom() {
  if (autoScroll.value && logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

watch(filteredLogs, () => nextTick(scrollToBottom), { deep: true })

function startSSE() {
  eventSource = new EventSource('/api/logs/stream')
  eventSource.onmessage = (event) => {
    if (paused.value) return
    const entry = JSON.parse(event.data)
    logs.value.push(entry)
    if (logs.value.length > 2000) {
      logs.value = logs.value.slice(-1500)
    }
  }
}

onMounted(startSSE)
onUnmounted(() => eventSource?.close())

async function loadHistory() {
  loadingHistory.value = true
  try {
    const res: any = await client.get('/logs/recent', { params: { source: 'file', count: 500 } })
    if (res.items?.length) {
      // Merge history at the top, dedup by full_timestamp+message
      const existing = new Set(logs.value.map((l: any) => l.full_timestamp + l.message))
      const newEntries = res.items.filter((e: any) => !existing.has(e.full_timestamp + e.message))
      logs.value = [...newEntries, ...logs.value]
    }
  } catch (e) {
    console.error('Failed to load history', e)
  } finally {
    loadingHistory.value = false
  }
}
</script>

<style scoped>
.page { padding: 28px 32px; }
.logs-layout { display: flex; flex-direction: column; height: calc(100vh - 0px); }
.page-header { margin-bottom: 20px; flex-shrink: 0; }
.page-header h1 { font-size: 24px; font-weight: 700; color: #0f172a; margin: 0 0 4px; }
.page-subtitle { color: #64748b; font-size: 14px; margin: 0; }

.toolbar {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 16px; flex-shrink: 0;
}

.log-terminal {
  flex: 1;
  background: #0f172a;
  border-radius: 12px;
  padding: 16px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12.5px;
  line-height: 1.7;
  min-height: 0;
}
.log-line { white-space: pre-wrap; word-break: break-all; padding: 1px 0; }
.log-time { color: #4ade80; margin-right: 10px; opacity: 0.7; }
.log-level { font-weight: 600; margin-right: 10px; display: inline-block; width: 56px; }
.log-name { color: #60a5fa; margin-right: 10px; opacity: 0.6; }
.log-msg { color: #e2e8f0; }
.level-info .log-level { color: #34d399; }
.level-warning .log-level { color: #fbbf24; }
.level-warning .log-msg { color: #fbbf24; }
.level-error .log-level { color: #f87171; }
.level-error .log-msg { color: #f87171; }
.level-debug .log-level { color: #64748b; }
.level-debug .log-msg { color: #64748b; }
.log-empty { color: #475569; text-align: center; padding: 60px 0; }

@media (max-width: 768px) {
  .toolbar { flex-wrap: wrap; }
  .log-terminal { font-size: 11px; padding: 10px; }
  .log-time { margin-right: 6px; }
  .log-level { margin-right: 6px; width: auto; }
  .log-name { display: none; }
}
</style>
