import { downloadBlob, downloadByBridge, getGuestSessionId, getInitData } from '../bridge/index.ts'
import type { ChatListItem, ComparisonResult, Mapping, MetricId, SnapshotListItem, UploadResponse } from './types.ts'
import { ApiError } from './errors.ts'
import { fixtures } from './fixtures.ts'

const TEMPLATE_NAME = 'xray-template.xlsx'

export function usesFixtures(): boolean {
  return import.meta.env.VITE_USE_FIXTURES === 'true'
}

function apiUrl(path: string): string {
  const base = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
  return `${base}${path}`
}

export function authHeaders(json: boolean): Headers {
  const headers = new Headers()
  const initData = getInitData()
  if (initData) {
    headers.set('X-Max-Init-Data', initData)
  } else {
    headers.set('X-Guest-Session', getGuestSessionId())
  }
  if (json) headers.set('Content-Type', 'application/json')
  return headers
}

const REMOVED_SCANS_KEY = 'xray-removed-scans'

export function removedScanIds(): Set<string> {
  try {
    const raw: unknown = JSON.parse(sessionStorage.getItem(REMOVED_SCANS_KEY) || '[]')
    return new Set(Array.isArray(raw) ? raw.map((item) => String(item)) : [])
  } catch {
    return new Set()
  }
}

export function rememberRemovedScan(id: string) {
  const ids = removedScanIds()
  ids.add(id)
  sessionStorage.setItem(REMOVED_SCANS_KEY, JSON.stringify([...ids]))
}

async function detailOf(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object') {
      const payload = body as { detail?: unknown; message?: unknown }
      const detail = payload.message ?? payload.detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) {
        return detail
          .map((item) => {
            if (item && typeof item === 'object' && 'msg' in item) return String((item as { msg: unknown }).msg)
            return String(item)
          })
          .join('; ')
      }
    }
  } catch {
    // Тело не JSON: ниже будет статус.
  }
  if (response.status === 401) return 'Сессия MAX не подтвердилась. Откройте приложение из бота ещё раз.'
  if (response.status === 404) return 'Снимок не найден'
  if (response.status === 409) return 'Снимок ещё считается'
  if (response.status === 429) return 'Слишком много загрузок за час. Попробуйте позже.'
  if (response.status === 502 || response.status === 503 || response.status === 504) {
    return 'Сервер перезагружается или временно недоступен. Пожалуйста, обновите страницу через несколько секунд.'
  }
  if (response.status >= 500) {
    return 'Внутренняя ошибка сервера. Попробуйте повторить запрос позже.'
  }
  return 'Запрос не прошёл'
}

async function request<T>(path: string, init: RequestInit, jsonBody: boolean): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), { ...init, cache: 'no-store', headers: authHeaders(jsonBody) })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером')
  }
  if (!response.ok) throw new ApiError(response.status, await detailOf(response))
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  amoSessions() {
    return request<{
      connected: boolean
      sessions: {
        id: number
        account: string
        last_sync_at: string | null
        last_error: string
        last_snapshot_id: string
      }[]
    }>('/api/amo', { method: 'GET' }, false)
  },

  bitrixSessions() {
    return request<{
      connected: boolean
      sessions: {
        id: number
        account: string
        last_sync_at: string | null
        last_error: string
        last_snapshot_id: string
      }[]
    }>('/api/bitrix', { method: 'GET' }, false)
  },

  moyskladSessions() {
    return request<{
      connected: boolean
      sessions: {
        id: number
        account: string
        last_sync_at: string | null
        last_error: string
        last_snapshot_id: string
      }[]
    }>('/api/moysklad', { method: 'GET' }, false)
  },

  connectAmo(account: string, token: string) {
    return request<{
      connected: boolean
      id: number
      account: string
      message?: string
      snapshot_id?: string
      last_sync_at: string | null
    }>('/api/amo/connect', { method: 'POST', body: JSON.stringify({ account, token }) }, true)
  },

  syncAmo(id: number) {
    return request<{ snapshot_id: string; status: string }>(
      '/api/amo/sync',
      { method: 'POST', body: JSON.stringify({ id }) },
      true,
    )
  },

  syncBitrix(id: number) {
    return request<{ snapshot_id: string; status: string }>(
      '/api/bitrix/sync',
      { method: 'POST', body: JSON.stringify({ id }) },
      true,
    )
  },

  syncMoySklad(id: number) {
    return request<{ snapshot_id: string; status: string }>(
      '/api/moysklad/sync',
      { method: 'POST', body: JSON.stringify({ id }) },
      true,
    )
  },

  deleteAmo(id: number) {
    return request<void>(`/api/amo/${id}`, { method: 'DELETE' }, false)
  },

  deleteBitrix(id: number) {
    return request<void>(`/api/bitrix/${id}`, { method: 'DELETE' }, false)
  },

  deleteMoySklad(id: number) {
    return request<void>(`/api/moysklad/${id}`, { method: 'DELETE' }, false)
  },

  connectBitrix(webhookUrl: string) {
    return request<{
      connected: boolean
      id: number
      account: string
      snapshot_id?: string
      message?: string
      last_sync_at: string | null
    }>('/api/bitrix/connect', { method: 'POST', body: JSON.stringify({ webhook_url: webhookUrl }) }, true)
  },

  connectMoySklad(token: string) {
    return request<{
      connected: boolean
      id: number
      account: string
      snapshot_id?: string
      message?: string
      last_sync_at: string | null
    }>('/api/moysklad/connect', { method: 'POST', body: JSON.stringify({ token }) }, true)
  },

  upload(file: File) {
    if (usesFixtures()) return fixtures.upload(file)
    const body = new FormData()
    body.set('file', file)
    return request<Awaited<ReturnType<typeof fixtures.upload>>>('/api/uploads', { method: 'POST', body }, false)
  },

  saveMapping(uploadId: string, mapping: Mapping) {
    if (usesFixtures()) return fixtures.saveMapping(mapping)
    return request<Awaited<ReturnType<typeof fixtures.saveMapping>>>(
      `/api/uploads/${uploadId}/mapping`,
      { method: 'PUT', body: JSON.stringify({ mapping }) },
      true,
    )
  },

  createSnapshot(uploadId: string, mapping: Mapping) {
    if (usesFixtures()) return fixtures.createSnapshot(uploadId, mapping)
    return request<Awaited<ReturnType<typeof fixtures.createSnapshot>>>(
      '/api/snapshots',
      { method: 'POST', body: JSON.stringify({ upload_id: uploadId }) },
      true,
    )
  },

  demo() {
    if (usesFixtures()) return fixtures.demo()
    return request<Awaited<ReturnType<typeof fixtures.demo>>>('/api/demo', { method: 'GET' }, false)
  },

  poll(snapshotId: string) {
    if (usesFixtures()) return fixtures.poll(snapshotId)
    return request<Awaited<ReturnType<typeof fixtures.poll>>>(`/api/snapshots/${snapshotId}`, { method: 'GET' }, false)
  },

  diagnosis(snapshotId: string) {
    if (usesFixtures()) return fixtures.diagnosis(snapshotId)
    return request<Awaited<ReturnType<typeof fixtures.diagnosis>>>(`/api/snapshots/${snapshotId}/diagnosis`, { method: 'GET' }, false)
  },

  metric(snapshotId: string, metricId: MetricId) {
    if (usesFixtures()) return fixtures.metric(snapshotId, metricId)
    return request<Awaited<ReturnType<typeof fixtures.metric>>>(
      `/api/snapshots/${snapshotId}/metrics/${metricId}`,
      { method: 'GET' },
      false,
    )
  },

  async listTemplates(): Promise<{ id: string; name: string; label: string; size_bytes: number }[]> {
    const res = await request<{ items: { id: string; name: string; label: string; size_bytes: number }[] }>(
      '/api/templates',
      { method: 'GET' },
      false,
    )
    return res?.items || []
  },

  async loadTemplate(templateId: string): Promise<UploadResponse> {
    return request<UploadResponse>(
      `/api/templates/${templateId}/load`,
      { method: 'POST' },
      false,
    )
  },

  async listChats(): Promise<ChatListItem[]> {
    if (usesFixtures()) {
      const items = await fixtures.list()
      return items
        .filter((item) => item.status === 'ready')
        .map((item) => ({
          snapshot_id: item.snapshot_id,
          title: item.card_title || item.headline || item.filename || 'Снимок',
          filename: item.filename || '',
          created_at: item.created_at,
          message_count: 0,
          last_message: '',
          last_at: null,
        }))
    }
    const res = await request<{ items: ChatListItem[] }>('/api/chats', { method: 'GET' }, false)
    return res?.items || []
  },

  async getChatHistory(snapshotId: string): Promise<any[]> {
    const res = await request<{ messages: any[] }>(
      `/api/snapshots/${snapshotId}/chat`,
      { method: 'GET' },
      false,
    )
    return res?.messages || []
  },

  async clearChatHistory(snapshotId: string): Promise<void> {
    return request<void>(
      `/api/snapshots/${snapshotId}/chat`,
      { method: 'DELETE' },
      false,
    )
  },

  async list(): Promise<SnapshotListItem[]> {
    if (usesFixtures()) return fixtures.list()
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 12000)
    const res = await request<{ items: SnapshotListItem[]; next_cursor: string | null }>(
      '/api/snapshots',
      { method: 'GET', signal: controller.signal },
      false,
    ).finally(() => window.clearTimeout(timer))
    return (res?.items || []).map((item) => ({
      ...item,
      coverage_label: item.coverage_label || `${(item as any).coverage_ready ?? 0} из ${(item as any).coverage_total ?? 7}`,
    }))
  },

  remove(snapshotId: string) {
    if (usesFixtures()) return fixtures.remove(snapshotId)
    return request<void>(`/api/snapshots/${snapshotId}`, { method: 'DELETE' }, false)
  },

  compare(baseId: string, targetId: string): Promise<ComparisonResult> {
    if (usesFixtures()) return fixtures.compare(baseId, targetId)
    return request<ComparisonResult>(
      `/api/snapshots/compare?base_id=${encodeURIComponent(baseId)}&target_id=${encodeURIComponent(targetId)}`,
      { method: 'GET' },
      false,
    )
  },

  exportToBot(snapshotId: string, format: 'pdf' | 'excel'): Promise<{ status: string; message: string; filename: string }> {
    return request<{ status: string; message: string; filename: string }>(
      `/api/snapshots/${snapshotId}/export-bot`,
      {
        method: 'POST',
        body: JSON.stringify({ format }),
      },
      true,
    )
  },

  async downloadReport(snapshotId: string, format: 'pdf' | 'excel'): Promise<void> {
    const ext = format === 'pdf' ? 'pdf' : 'xlsx'
    const fileName = `xray_audit_${snapshotId.slice(0, 8)}.${ext}`
    const url = apiUrl(`/api/snapshots/${snapshotId}/export-${format}`)
    if (await downloadByBridge(url, fileName)) return
    let response: Response
    try {
      response = await fetch(url, { headers: authHeaders(false) })
    } catch {
      throw new ApiError(0, 'Нет связи с сервером')
    }
    if (!response.ok) throw new ApiError(response.status, await detailOf(response))
    downloadBlob(await response.blob(), fileName)
  },
}

export async function downloadTemplate(): Promise<void> {
  if (usesFixtures()) {
    downloadBlob(await fixtures.template(), TEMPLATE_NAME)
    return
  }
  const url = apiUrl('/api/template')
  if (await downloadByBridge(url, TEMPLATE_NAME)) return
  let response: Response
  try {
    response = await fetch(url, { headers: authHeaders(false) })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером')
  }
  if (!response.ok) throw new ApiError(response.status, await detailOf(response))
  downloadBlob(await response.blob(), TEMPLATE_NAME)
}
