export interface ConversationItem {
  id: number
  title: string
  model_name: string
  update_time: string
}

export interface ToolCallItem {
  tool: string
  status: string
  result_preview?: string
  error?: string
  input?: Record<string, any>
}

export interface MessageItem {
  id: number
  role: 'user' | 'assistant'
  content: string
  tool_calls?: string | null
  toolCalls: ToolCallItem[]
  create_time: string
}

export interface McpToolItem {
  name: string
  category: string
  description: string
}

export interface McpStatus {
  loaded: boolean
  tools: McpToolItem[]
  health: Record<string, any>
}
