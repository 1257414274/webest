export type PriorityTagType = 'danger' | 'warning' | 'success' | 'info'

export interface PriorityRenderResult {
  text: string
  type: PriorityTagType
  className: string
  style: Record<string, string>
}

export function normalizePriority(value: unknown): PriorityRenderResult {
  if (value === null || value === undefined || String(value).trim() === '') {
    return {
      text: '-',
      type: 'info',
      className: 'priority-empty',
      style: {
        backgroundColor: '#f3f4f6',
        borderColor: '#d1d5db',
        color: '#6b7280'
      }
    }
  }
  const raw = String(value).trim()
  const v = raw.toLowerCase()

  if (v.includes('p0') || v.includes('p1') || v.includes('高') || v.includes('high') || v.includes('critical')) {
    return {
      text: raw,
      type: 'danger',
      className: 'priority-p1',
      style: {
        backgroundColor: '#fee2e2',
        borderColor: '#fca5a5',
        color: '#b91c1c'
      }
    }
  }
  if (v.includes('p2') || v.includes('中') || v.includes('medium')) {
    return {
      text: raw,
      type: 'warning',
      className: 'priority-p2',
      style: {
        backgroundColor: '#ffedd5',
        borderColor: '#fdba74',
        color: '#c2410c'
      }
    }
  }
  if (v.includes('p3') || v.includes('p4') || v.includes('低') || v.includes('low')) {
    return {
      text: raw,
      type: 'success',
      className: 'priority-p3',
      style: {
        backgroundColor: '#dcfce7',
        borderColor: '#86efac',
        color: '#166534'
      }
    }
  }
  return {
    text: raw,
    type: 'info',
    className: 'priority-other',
    style: {
      backgroundColor: '#e0f2fe',
      borderColor: '#7dd3fc',
      color: '#075985'
    }
  }
}

export function normalizeAction(value: unknown): string {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'string') {
    const v = value.trim()
    return v || '-'
  }
  try {
    const text = JSON.stringify(value)
    return text || '-'
  } catch (_e) {
    return String(value)
  }
}
