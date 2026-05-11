export interface ClassifiedAssetItem {
  id: number
  company: string
  ip: string
  port: string
  domain: string
  url: string
  predicted_tactic: string
  confidence: number
  classification_status: string
  penetration_status: 'pending' | 'completed'
  penetration_remark: string
  deepseek_priority?: string
  deepseek_framework?: string
  deepseek_reason?: string
  deepseek_action?: string
  updated_at?: string
}

export interface ClassifiedAssetListResponse {
  list: ClassifiedAssetItem[]
  total: number
  page: number
  size: number
}
