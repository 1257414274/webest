export interface OpencodeTaskItem {
  id: number
  task_name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
  remote_task_id: string
  latency_ms: number
  retry_count: number
  error_message: string
  create_time: string
  update_time: string
}

export interface OpencodeTaskDetail extends OpencodeTaskItem {
  prompt: string
  context: string
  request_payload: string
  response_payload: string
}

export interface OpencodeMetrics {
  total: number
  success: number
  failed: number
  running: number
  success_rate: number
}

export interface OpencodeSessionItem {
  session_id: string
  title: string
  updated_at: string
}

export interface OpencodeChatMessage {
  id: string
  role: 'user' | 'assistant' | string
  text: string
  create_time: string
}
