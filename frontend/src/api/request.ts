import { useUserStore } from '@/store/user'
import { feedback } from '@/utils/feedback'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

export interface RequestOptions {
  method?: HttpMethod
  data?: unknown
  params?: Record<string, unknown>
  /** 交给调用方自己提示错误时置 true，请求层不再弹出 message */
  silent?: boolean
}

export class ApiError extends Error {
  status?: number

  payload?: unknown

  constructor(message: string, status?: number, payload?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return ''
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    search.append(key, String(value))
  })
  const queryString = search.toString()
  return queryString ? `?${queryString}` : ''
}

function resolveMessage(payload: unknown, status: number): string {
  const detail = (payload as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    const text = detail
      .map((item) => (item as { msg?: string })?.msg || '')
      .filter(Boolean)
      .join('；')
    return text || '请求参数不合法'
  }
  const fallback = (payload as { message?: string } | null)?.message
  return fallback || `请求失败（${status}）`
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', data, params, silent = false } = options
  const headers: Record<string, string> = {}

  const token = useUserStore.getState().token
  if (token) headers.Authorization = `Bearer ${token}`

  let body: string | undefined
  if (data !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(data)
  }

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}${buildQuery(params)}`, { method, headers, body })
  } catch {
    if (!silent) feedback.error('网络异常，请确认后端服务已启动')
    throw new ApiError('NETWORK_ERROR')
  }

  const text = await response.text()
  let payload: unknown = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    const message = resolveMessage(payload, response.status)
    if (response.status === 401) {
      useUserStore.getState().clear()
      if (!silent) feedback.error(message)
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
      throw new ApiError(message, response.status, payload)
    }
    if (!silent) feedback.error(message)
    throw new ApiError(message, response.status, payload)
  }

  return payload as T
}

export const http = {
  get: <T>(path: string, params?: Record<string, unknown>, options?: RequestOptions) =>
    request<T>(path, { method: 'GET', params, ...options }),
  post: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, { method: 'POST', data, ...options }),
  put: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, { method: 'PUT', data, ...options }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>(path, { method: 'DELETE', ...options }),
}

export default request
