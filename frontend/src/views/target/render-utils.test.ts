import { describe, expect, it } from 'vitest'
import { normalizeAction, normalizePriority } from './render-utils'

describe('render-utils', () => {
  it('空优先级字段应返回安全默认值', () => {
    expect(normalizePriority('')).toEqual({ text: '-', type: 'info' })
    expect(normalizePriority(null)).toEqual({ text: '-', type: 'info' })
  })

  it('异常优先级字段应降级为 info 标签', () => {
    expect(normalizePriority('unknown')).toEqual({ text: 'unknown', type: 'info' })
    expect(normalizePriority(999)).toEqual({ text: '999', type: 'info' })
  })

  it('中英优先级字段应正确映射颜色', () => {
    expect(normalizePriority('P1-高危')).toEqual({ text: 'P1-高危', type: 'danger' })
    expect(normalizePriority('medium')).toEqual({ text: 'medium', type: 'warning' })
    expect(normalizePriority('LOW')).toEqual({ text: 'LOW', type: 'success' })
  })

  it('建议操作字段为空与对象时应安全渲染', () => {
    expect(normalizeAction(undefined)).toBe('-')
    expect(normalizeAction('   ')).toBe('-')
    expect(normalizeAction({ k: 'v' })).toBe('{"k":"v"}')
  })
})
