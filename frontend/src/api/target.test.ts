import { afterEach, describe, expect, it } from 'vitest'
import {
  fetchClassifiedAssets,
  resetTargetHttpClientForTest,
  setTargetHttpClientForTest
} from './target'

describe('target api', () => {
  afterEach(() => {
    resetTargetHttpClientForTest()
  })

  it('字段为空时应返回可安全渲染的数据结构', async () => {
    setTargetHttpClientForTest({
      post: async () => ({
        data: {
          code: 0,
          data: {
            list: [{ id: 1, deepseek_priority: '', deepseek_action: null }],
            total: 1,
            page: 1,
            size: 50
          }
        }
      })
    })

    const data = await fetchClassifiedAssets({ keyword: '', page: 1, size: 50 })
    expect(data.list.length).toBe(1)
  })

  it('网络延迟场景应能正常返回', async () => {
    setTargetHttpClientForTest({
      post: async () => {
        await new Promise(resolve => setTimeout(resolve, 60))
        return {
          data: {
            code: 0,
            data: { list: [], total: 0, page: 1, size: 50 }
          }
        }
      }
    })

    const t0 = Date.now()
    const data = await fetchClassifiedAssets({ keyword: 'x', page: 1, size: 50 })
    expect(Date.now() - t0).toBeGreaterThanOrEqual(50)
    expect(data.total).toBe(0)
  })

  it('异常返回码应抛出错误', async () => {
    setTargetHttpClientForTest({
      post: async () => ({ data: { code: 500, msg: 'fail' } })
    })
    await expect(fetchClassifiedAssets({ keyword: '', page: 1, size: 20 })).rejects.toThrow('fail')
  })
})
