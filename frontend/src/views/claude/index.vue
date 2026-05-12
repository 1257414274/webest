<template>
  <div class="claude-page">
    <el-card class="mcp-status-card" style="margin-bottom: 12px;">
      <template #header>
        <div class="card-header">
          <span>MCP 状态</span>
          <el-button link type="primary" @click="loadMcpStatus">刷新</el-button>
        </div>
      </template>
      <div v-loading="mcpLoading">
        <el-tag :type="mcpLoaded ? 'success' : 'warning'">
          {{ mcpLoaded ? 'MCP 已加载' : 'MCP 未加载' }}
        </el-tag>
        <div class="mcp-tools">
          <el-tag
            v-for="item in mcpTools"
            :key="item.name"
            size="small"
            style="margin-right: 6px; margin-top: 6px;"
          >
            {{ item.name }} ({{ item.category }})
          </el-tag>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="conversation-card">
          <template #header>
            <div class="card-header">
              <span>Claude 会话</span>
              <el-button type="primary" link @click="handleCreateConversation">新建会话</el-button>
            </div>
          </template>

          <div class="conversation-list" v-loading="conversationLoading">
            <el-empty v-if="!conversationList.length" description="暂无会话" />
            <div
              v-for="item in conversationList"
              :key="item.id"
              class="conversation-item"
              :class="{ active: item.id === activeConversationId }"
              @click="selectConversation(item.id)"
            >
              <div class="title-row">
                <div class="title">{{ item.title }}</div>
                <div class="conversation-actions">
                  <el-button
                    size="small"
                    text
                    type="primary"
                    @click.stop="handleRenameConversation(item)"
                  >
                    重命名
                  </el-button>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    @click.stop="handleDeleteConversation(item)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
              <div class="meta">{{ item.model_name }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="18">
        <el-card class="chat-card">
          <template #header>
            <div class="card-header">
              <span>Claude 对话</span>
              <el-tag type="success">Anthropic SDK</el-tag>
            </div>
          </template>

          <div class="message-list" ref="messageListRef" v-loading="messageLoading">
            <el-empty v-if="!messages.length" description="发送第一条消息开始对话" />
            <div v-for="item in messages" :key="item.id" class="message-item" :class="item.role">
              <div class="role">{{ item.role === 'assistant' ? 'Claude' : '我' }}</div>
              <div class="content">{{ item.content }}</div>
              <div v-if="item.role === 'assistant' && item.toolCalls.length" class="tool-calls">
                <div class="tool-title">本轮工具调用：</div>
                <div v-for="(tool, idx) in item.toolCalls" :key="idx" class="tool-row">
                  <el-tag :type="tool.status === 'success' ? 'success' : 'danger'" size="small">
                    {{ tool.tool }}
                  </el-tag>
                  <span class="tool-result">{{ tool.result_preview || tool.error || '-' }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="input-panel">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="5"
              resize="none"
              placeholder="请输入你想交给 Claude 的问题，例如：请帮我总结这个 ICP 资产的攻击面。"
              @keyup.ctrl.enter="handleSendMessage"
            />
            <div class="action-bar">
              <span class="tip">`Ctrl + Enter` 发送</span>
              <el-button type="primary" :loading="sending" @click="handleSendMessage">发送给 Claude</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import type { ConversationItem, McpToolItem, MessageItem } from '../../types/claude'

const conversationList = ref<ConversationItem[]>([])
const messages = ref<MessageItem[]>([])
const activeConversationId = ref<number | null>(null)
const inputMessage = ref('')
const sending = ref(false)
const conversationLoading = ref(false)
const messageLoading = ref(false)
const mcpLoading = ref(false)
const mcpLoaded = ref(false)
const mcpTools = ref<McpToolItem[]>([])
const messageListRef = ref<HTMLElement | null>(null)

const getAuthHeaders = () => {
  const token = localStorage.getItem('token')
  return token ? { 'x-token': token } : {}
}

const handleRequestError = (error: any, fallback = '请求失败') => {
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
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const loadConversationList = async () => {
  conversationLoading.value = true
  try {
    const res = await axios.post(
      '/api/getClaudeConversations',
      { limit: 100 },
      { headers: getAuthHeaders() }
    )
    if (res.data.code === 0) {
      conversationList.value = res.data.data.list || []
      if (!activeConversationId.value && conversationList.value.length > 0) {
        activeConversationId.value = conversationList.value[0].id
        await loadMessages()
      }
    } else {
      ElMessage.error(res.data.msg || '获取会话失败')
    }
  } catch (error: any) {
    handleRequestError(error, '获取会话失败')
  } finally {
    conversationLoading.value = false
  }
}

const loadMessages = async () => {
  if (!activeConversationId.value) {
    messages.value = []
    return
  }

  messageLoading.value = true
  try {
    const res = await axios.post(
      '/api/getClaudeMessages',
      { conversation_id: activeConversationId.value },
      { headers: getAuthHeaders() }
    )
    if (res.data.code === 0) {
      messages.value = (res.data.data.list || []).map((item: any) => {
        let toolCalls: any[] = []
        if (item.tool_calls) {
          try {
            toolCalls = JSON.parse(item.tool_calls)
          } catch {
            toolCalls = []
          }
        }
        return {
          ...item,
          toolCalls
        }
      })
      scrollToBottom()
    } else {
      ElMessage.error(res.data.msg || '获取消息失败')
    }
  } catch (error: any) {
    handleRequestError(error, '获取消息失败')
  } finally {
    messageLoading.value = false
  }
}

const loadMcpStatus = async () => {
  mcpLoading.value = true
  try {
    const res = await axios.post('/api/getClaudeMcpStatus', {}, { headers: getAuthHeaders() })
    if (res.data.code === 0) {
      mcpLoaded.value = !!res.data.data.loaded
      mcpTools.value = res.data.data.tools || []
    } else {
      ElMessage.error(res.data.msg || '获取 MCP 状态失败')
    }
  } catch (error: any) {
    handleRequestError(error, '获取 MCP 状态失败')
  } finally {
    mcpLoading.value = false
  }
}

const handleCreateConversation = async () => {
  try {
    const res = await axios.post(
      '/api/createClaudeConversation',
      { title: '新对话' },
      { headers: getAuthHeaders() }
    )
    if (res.data.code === 0) {
      activeConversationId.value = res.data.data.conversation_id
      messages.value = []
      await loadConversationList()
      ElMessage.success('会话已创建')
    } else {
      ElMessage.error(res.data.msg || '创建会话失败')
    }
  } catch (error: any) {
    handleRequestError(error, '创建会话失败')
  }
}

const selectConversation = async (conversationId: number) => {
  activeConversationId.value = conversationId
  await loadMessages()
}

const handleRenameConversation = async (item: ConversationItem) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      inputValue: item.title,
      inputValidator: (val: string) => {
        if (!val || !val.trim()) return '会话名称不能为空'
        if (val.trim().length > 100) return '会话名称不能超过100个字符'
        return true
      }
    })
    const res = await axios.post(
      '/api/renameClaudeConversation',
      {
        conversation_id: item.id,
        title: value.trim()
      },
      { headers: getAuthHeaders() }
    )
    if (res.data.code === 0) {
      ElMessage.success('重命名成功')
      await loadConversationList()
    } else {
      ElMessage.error(res.data.msg || '重命名失败')
    }
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    handleRequestError(error, '重命名失败')
  }
}

const handleDeleteConversation = async (item: ConversationItem) => {
  try {
    await ElMessageBox.confirm(
      `确认删除会话「${item.title}」吗？删除后不可恢复。`,
      '删除会话',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    const res = await axios.post(
      '/api/deleteClaudeConversation',
      { conversation_id: item.id },
      { headers: getAuthHeaders() }
    )
    if (res.data.code === 0) {
      ElMessage.success('会话已删除')
      if (activeConversationId.value === item.id) {
        activeConversationId.value = null
        messages.value = []
      }
      await loadConversationList()
      if (!activeConversationId.value && conversationList.value.length > 0) {
        activeConversationId.value = conversationList.value[0].id
        await loadMessages()
      }
    } else {
      ElMessage.error(res.data.msg || '删除失败')
    }
  } catch (error: any) {
    if (error === 'cancel' || error === 'close') return
    handleRequestError(error, '删除失败')
  }
}

const handleSendMessage = async () => {
  const content = inputMessage.value.trim()
  if (!content) {
    ElMessage.warning('请输入消息内容')
    return
  }

  if (!activeConversationId.value) {
    await handleCreateConversation()
  }

  if (!activeConversationId.value) {
    return
  }

  sending.value = true
  try {
    const res = await axios.post(
      '/api/sendClaudeMessage',
      {
        conversation_id: activeConversationId.value,
        content
      },
      { headers: getAuthHeaders() }
    )
    if (res.data.code === 0) {
      inputMessage.value = ''
      await loadMessages()
      await loadConversationList()
    } else {
      ElMessage.error(res.data.msg || 'Claude 调用失败')
    }
  } catch (error: any) {
    handleRequestError(error, 'Claude 调用失败')
  } finally {
    sending.value = false
  }
}

onMounted(() => {
  loadConversationList()
  loadMcpStatus()
})
</script>

<style scoped>
.claude-page {
  min-height: calc(100vh - 120px);
}

.mcp-status-card {
  border-radius: 8px;
}

.mcp-tools {
  margin-top: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.conversation-card,
.chat-card {
  height: calc(100vh - 120px);
}

.conversation-list {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}

.conversation-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  background: #f7f8fa;
  margin-bottom: 10px;
  border: 1px solid transparent;
}

.conversation-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.conversation-item .title {
  font-weight: 600;
  color: #303133;
}

.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.conversation-actions {
  display: flex;
  align-items: center;
}

.conversation-item .meta {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.message-list {
  height: calc(100vh - 320px);
  overflow-y: auto;
  padding-right: 8px;
}

.message-item {
  margin-bottom: 16px;
  padding: 14px;
  border-radius: 10px;
}

.message-item.user {
  background: #ecf5ff;
}

.message-item.assistant {
  background: #f6f8fa;
}

.message-item .role {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 8px;
}

.message-item .content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: #303133;
}

.tool-calls {
  margin-top: 10px;
  padding: 8px;
  border-radius: 6px;
  background: #fff;
  border: 1px dashed #dcdfe6;
}

.tool-title {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}

.tool-row {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  gap: 8px;
}

.tool-result {
  font-size: 12px;
  color: #909399;
}

.input-panel {
  margin-top: 16px;
}

.action-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tip {
  color: #909399;
  font-size: 12px;
}
</style>
