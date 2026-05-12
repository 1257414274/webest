<template>
  <div class="opencode-chat">
    <aside class="session-panel">
      <div class="session-toolbar">
        <el-button type="primary" @click="handleCreateSession">新建会话</el-button>
        <el-button @click="loadSessions">刷新</el-button>
      </div>
      <el-scrollbar class="session-list" v-loading="sessionsLoading">
        <div
          v-for="item in sessions"
          :key="item.session_id"
          :class="['session-item', currentSessionId === item.session_id ? 'active' : '']"
          @click="selectSession(item.session_id)"
        >
          <div class="title">{{ item.title || 'OpenCode会话' }}</div>
          <div class="meta">{{ item.updated_at || '-' }}</div>
        </div>
      </el-scrollbar>
      <div class="session-actions" v-if="currentSessionId">
        <el-button size="small" @click="handleRenameSession">重命名</el-button>
        <el-button size="small" type="danger" @click="handleDeleteSession">删除</el-button>
      </div>
    </aside>

    <main class="chat-panel">
      <div class="chat-header">
        <div class="chat-title">OpenCode 实时对话</div>
        <div>
          <el-tag :type="healthOk ? 'success' : 'danger'">{{ healthOk ? '服务正常' : '服务异常' }}</el-tag>
          <span class="latency">{{ healthLatency }}ms</span>
          <el-button link @click="loadHealth">检测</el-button>
        </div>
      </div>

      <el-scrollbar ref="messageContainerRef" class="message-list">
        <div v-if="messages.length === 0" class="empty">开始一个会话后即可实时对话</div>
        <div v-for="item in messages" :key="item.id" :class="['msg', item.role === 'user' ? 'user' : 'assistant']">
          <div class="role">{{ item.role === 'user' ? '我' : 'OpenCode' }}</div>
          <pre class="text">{{ item.text || '(空消息)' }}</pre>
        </div>
      </el-scrollbar>

      <div class="input-area">
        <el-input
          v-model="prompt"
          type="textarea"
          :rows="4"
          placeholder="输入你的问题，按 Ctrl+Enter 发送"
          @keydown.ctrl.enter.prevent="sendMessage"
        />
        <div class="input-actions">
          <el-button type="primary" :loading="sending" @click="sendMessage">发送</el-button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import type { OpencodeChatMessage, OpencodeSessionItem } from '../../types/opencode'

const sessions = ref<OpencodeSessionItem[]>([])
const sessionsLoading = ref(false)
const currentSessionId = ref('')
const messages = ref<OpencodeChatMessage[]>([])
const prompt = ref('')
const sending = ref(false)
const healthOk = ref(false)
const healthLatency = ref(0)
const messageContainerRef = ref()

const getHeaders = () => {
  const token = localStorage.getItem('token')
  return token ? { 'x-token': token } : {}
}

const handleError = (error: any, fallback: string) => {
  if (error?.response?.data?.code === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('session_id')
    window.location.href = '/login'
    return
  }
  ElMessage.error(error?.response?.data?.msg || error?.message || fallback)
}

const scrollToBottom = async () => {
  await nextTick()
  const wrap = messageContainerRef.value?.wrapRef
  if (wrap) wrap.scrollTop = wrap.scrollHeight
}

const loadHealth = async () => {
  try {
    const res = await axios.post('/api/opencodeHealth', {}, { headers: getHeaders() })
    if (res.data.code === 0) {
      healthOk.value = true
      healthLatency.value = Number(res.data.data?.latency_ms || 0)
    } else {
      healthOk.value = false
    }
  } catch {
    healthOk.value = false
  }
}

const loadSessions = async () => {
  sessionsLoading.value = true
  try {
    const res = await axios.post('/api/opencodeSessionList', { limit: 100 }, { headers: getHeaders() })
    if (res.data.code === 0) {
      sessions.value = res.data.data?.list || []
      if (!currentSessionId.value && sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].session_id
        await loadMessages(currentSessionId.value)
      }
    } else {
      ElMessage.error(res.data.msg || '加载会话失败')
    }
  } catch (error: any) {
    handleError(error, '加载会话失败')
  } finally {
    sessionsLoading.value = false
  }
}

const loadMessages = async (sessionId: string) => {
  if (!sessionId) return
  try {
    const res = await axios.post(
      '/api/opencodeSessionMessages',
      { session_id: sessionId, limit: 100 },
      { headers: getHeaders() }
    )
    if (res.data.code === 0) {
      messages.value = res.data.data?.list || []
      await scrollToBottom()
    } else {
      ElMessage.error(res.data.msg || '加载消息失败')
    }
  } catch (error: any) {
    handleError(error, '加载消息失败')
  }
}

const selectSession = async (sessionId: string) => {
  currentSessionId.value = sessionId
  await loadMessages(sessionId)
}

const handleCreateSession = async () => {
  try {
    const res = await axios.post('/api/opencodeCreateSession', { title: '新会话' }, { headers: getHeaders() })
    if (res.data.code !== 0) {
      ElMessage.error(res.data.msg || '创建会话失败')
      return
    }
    currentSessionId.value = res.data.data?.session_id || ''
    messages.value = []
    await loadSessions()
    ElMessage.success('会话已创建')
  } catch (error: any) {
    handleError(error, '创建会话失败')
  }
}

const handleRenameSession = async () => {
  if (!currentSessionId.value) return
  try {
    const input = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    const title = input.value || ''
    const res = await axios.post(
      '/api/opencodeRenameSession',
      { session_id: currentSessionId.value, title },
      { headers: getHeaders() }
    )
    if (res.data.code === 0) {
      ElMessage.success('重命名成功')
      await loadSessions()
    } else {
      ElMessage.error(res.data.msg || '重命名失败')
    }
  } catch {
    // 用户取消
  }
}

const handleDeleteSession = async () => {
  if (!currentSessionId.value) return
  try {
    await ElMessageBox.confirm('确定删除当前会话吗？', '删除会话', {
      type: 'warning'
    })
    const res = await axios.post(
      '/api/opencodeDeleteSession',
      { session_id: currentSessionId.value },
      { headers: getHeaders() }
    )
    if (res.data.code === 0) {
      ElMessage.success('会话已删除')
      currentSessionId.value = ''
      messages.value = []
      await loadSessions()
    } else {
      ElMessage.error(res.data.msg || '删除会话失败')
    }
  } catch {
    // 用户取消
  }
}

const sendMessage = async () => {
  const text = prompt.value.trim()
  if (!text) {
    ElMessage.warning('请输入消息')
    return
  }
  const token = localStorage.getItem('token')
  if (!token) {
    window.location.href = '/login'
    return
  }

  sending.value = true
  prompt.value = ''
  const userMsg: OpencodeChatMessage = {
    id: `u-${Date.now()}`,
    role: 'user',
    text,
    create_time: ''
  }
  const assistantMsg: OpencodeChatMessage = {
    id: `a-${Date.now()}`,
    role: 'assistant',
    text: '',
    create_time: ''
  }
  messages.value.push(userMsg, assistantMsg)
  await scrollToBottom()

  try {
    const resp = await fetch('/api/opencodeStream', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-token': token
      },
      body: JSON.stringify({
        task_name: '实时对话',
        prompt: text,
        context: '',
        session_id: currentSessionId.value || ''
      })
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`SSE请求失败: HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''

      for (const chunk of chunks) {
        const lines = chunk.split('\n')
        let eventName = 'message'
        let dataLine = ''
        for (const line of lines) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim()
          if (line.startsWith('data:')) dataLine += line.slice(5).trim()
        }
        if (!dataLine) continue
        let payload: any = {}
        try {
          payload = JSON.parse(dataLine)
        } catch {
          payload = {}
        }

        if (eventName === 'meta' && payload.session_id) {
          currentSessionId.value = payload.session_id
          await loadSessions()
        } else if (eventName === 'thinking' && payload.text) {
          assistantMsg.text += `\n[思考] ${payload.text}`
          await scrollToBottom()
        } else if (eventName === 'delta' && payload.text) {
          assistantMsg.text += payload.text
          await scrollToBottom()
        } else if (eventName === 'error') {
          throw new Error(payload.message || '流式对话失败')
        } else if (eventName === 'done') {
          await loadMessages(currentSessionId.value)
          await loadSessions()
        }
      }
    }
  } catch (error: any) {
    handleError(error, '实时对话失败')
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  await loadHealth()
  await loadSessions()
})
</script>

<style scoped>
.opencode-chat {
  display: flex;
  min-height: calc(100vh - 120px);
  gap: 12px;
}

.session-panel {
  width: 280px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.session-toolbar {
  padding: 10px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  gap: 8px;
}

.session-list {
  flex: 1;
}

.session-item {
  padding: 10px 12px;
  border-bottom: 1px solid #f2f6fc;
  cursor: pointer;
}

.session-item.active {
  background: #ecf5ff;
}

.session-item .title {
  font-size: 14px;
  color: #303133;
}

.session-item .meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.session-actions {
  padding: 10px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 8px;
}

.chat-panel {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.chat-header {
  height: 52px;
  padding: 0 14px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
}

.latency {
  margin: 0 8px;
  font-size: 12px;
  color: #909399;
}

.message-list {
  flex: 1;
  padding: 12px;
}

.empty {
  color: #909399;
  text-align: center;
  margin-top: 120px;
}

.msg {
  margin-bottom: 12px;
}

.msg .role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.msg .text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 10px;
  border-radius: 8px;
  background: #f5f7fa;
}

.msg.user .text {
  background: #ecf5ff;
}

.input-area {
  border-top: 1px solid #ebeef5;
  padding: 12px;
}

.input-actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}
</style>
