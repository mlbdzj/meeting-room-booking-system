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

/** 「2026-11-06 10:00 至 12:00（2 小时）」 */
export function reservationRange(
  row?: Pick<Reservation, 'start_at' | 'end_at' | 'hours'> | null,
): string {
  if (!row?.start_at) return ''
  const duration = row.hours ? `（${row.hours} 小时）` : ''
  return `${toDateTimeString(row.start_at)} 至 ${toDateTimeString(row.end_at)}${duration}`
}

export function money(value?: number | string | null): string {
  const amount = Number(value || 0)
  return `¥${amount.toFixed(0)}`
}
