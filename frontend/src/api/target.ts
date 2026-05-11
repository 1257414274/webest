import axios from 'axios'
import type { ClassifiedAssetListResponse } from '../types/target'

export interface TargetHttpClient {
  post: (url: string, body?: any) => Promise<{ data: any }>
}

let httpClient: TargetHttpClient = axios as unknown as TargetHttpClient

function _getAccessToken(): string {
  const fromStorage = localStorage.getItem('access_token')
  if (fromStorage) return fromStorage
  const params = new URLSearchParams(window.location.search)
  const fromUrl = params.get('token') || ''
  if (fromUrl) {
    localStorage.setItem('access_token', fromUrl)
  }
  return fromUrl
}

axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers['x-token'] = token
  }
  const accessToken = _getAccessToken()
  if (accessToken) {
    if (!config.params) config.params = {}
    config.params.token = accessToken
  }
  return config
})

axios.interceptors.response.use(response => {
  if (response.data && response.data.code === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('session_id')
    window.location.href = '/login'
  }
  return response
})

export function setTargetHttpClientForTest(client: TargetHttpClient) {
  httpClient = client
}

export function resetTargetHttpClientForTest() {
  httpClient = axios as unknown as TargetHttpClient
}

export async function fetchClassifiedAssets(params: {
  keyword: string
  page: number
  size: number
}): Promise<ClassifiedAssetListResponse> {
  const res = await httpClient.post('/api/getClassifiedAssets', params)
  if (res.data.code !== 0) {
    throw new Error(res.data.msg || '获取数据失败')
  }
  return res.data.data
}

export async function triggerFullPipeline(params: { icp_keyword: string; limit: number }): Promise<string> {
  const res = await httpClient.post('/api/triggerFullAssetPipeline', params)
  if (res.data.code !== 0) {
    throw new Error(res.data.msg || '触发失败')
  }
  return res.data.data?.msg || res.data.msg || '任务已下发后台执行，分类结果将自动刷新'
}

export async function updateAssetStatus(assetId: number, isCompleted: boolean): Promise<void> {
  const res = await httpClient.post('/api/updateClassifiedAssetStatus', {
    asset_id: assetId,
    is_completed: isCompleted
  })
  if (res.data.code !== 0) {
    throw new Error(res.data.msg || '状态更新失败')
  }
}

export async function updateAssetRemark(assetId: number, remark: string): Promise<void> {
  const res = await httpClient.post('/api/updateClassifiedAssetRemark', {
    asset_id: assetId,
    remark
  })
  if (res.data.code !== 0) {
    throw new Error(res.data.msg || '备注保存失败')
  }
}
