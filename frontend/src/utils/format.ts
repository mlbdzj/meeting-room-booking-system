import type { Reservation } from '@/api/types'

export function toDateString(value?: string | null): string {
  if (!value) return ''
  return String(value).slice(0, 10)
}

export function toDateTimeString(value?: string | null): string {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

export function weekdayText(value?: string | null): string {
  const text = toDateString(value)
  if (!text) return ''
  const target = new Date(`${text}T00:00:00`)
  if (Number.isNaN(target.getTime())) return ''
  return `周${'日一二三四五六'[target.getDay()]}`
}

/** 「2026-09-25 至 2026-09-27（2 晚）」 */
export function stayRange(row?: Pick<Reservation, 'start_at' | 'end_at' | 'hours'> | null): string {
  if (!row?.start_at) return ''
  const hours = row.hours ?? ''
  return `${toDateString(row.start_at)} 至 ${toDateString(row.end_at)}${
    hours ? `（${hours} 晚）` : ''
  }`
}

export function money(value?: number | string | null): string {
  const amount = Number(value || 0)
  return `¥${amount.toFixed(0)}`
}
