import type { MaxUser, MaxWebApp, Platform } from './types.ts'

const KNOWN_PLATFORMS = new Set<Platform>(['ios', 'android', 'desktop', 'web'])

function hostApp(): MaxWebApp | undefined {
  return window.WebApp ?? window.Telegram?.WebApp
}

export function initBridge(): void {
  const telegram = window.Telegram?.WebApp
  if (!window.WebApp && telegram) window.WebApp = telegram
  const app = hostApp()
  if (!app) return
  try {
    app.ready?.()
  } catch {
    // Вне клиента MAX ready не обязателен.
  }
  try {
    app.expand?.()
  } catch {
    // В актуальном Bridge метода может не быть.
  }
}

export function getInitData(): string {
  return hostApp()?.initData ?? ''
}

export function getGuestSessionId(): string {
  let id = localStorage.getItem('xray_guest_session_id')
  if (!id) {
    id = 'guest_' + Math.random().toString(36).substring(2) + Date.now().toString(36)
    localStorage.setItem('xray_guest_session_id', id)
  }
  return id
}

export function getMaxUser(): MaxUser | null {
  const unsafe = hostApp()?.initDataUnsafe?.user
  if (unsafe && typeof unsafe.id === 'number') return unsafe
  const raw = window.WebApp?.initData
  if (!raw) return null
  try {
    const encoded = new URLSearchParams(raw).get('user')
    if (!encoded) return null
    const parsed = JSON.parse(encoded) as MaxUser
    if (parsed && typeof parsed.id === 'number') return parsed
  } catch {
    return null
  }
  return null
}

export function isInsideMax(): boolean {
  return Boolean(hostApp()?.initData)
}

export function getPlatform(): Platform {
  const raw = hostApp()?.platform
  const mapped =
    raw === 'tdesktop' || raw === 'macos' ? 'desktop' : raw === 'weba' || raw === 'webk' ? 'web' : raw
  const value = mapped
  if (value && KNOWN_PLATFORMS.has(value as Platform)) return value as Platform
  if (typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 900px)').matches) return 'web'
  return 'ios'
}

export function setClosingConfirmation(enabled: boolean): void {
  const app = hostApp()
  if (!app) return
  try {
    if (enabled) app.enableClosingConfirmation?.()
    else app.disableClosingConfirmation?.()
  } catch {
    // В браузере вне MAX подтверждение закрытия недоступно.
  }
}

export function showBack(visible: boolean): void {
  const button = hostApp()?.BackButton
  if (!button) return
  try {
    if (visible) button.show()
    else button.hide()
  } catch {
    // Кнопки шапки нет вне клиента MAX.
  }
}

export function bindBack(handler: () => void): () => void {
  const button = hostApp()?.BackButton
  if (!button) return () => undefined
  button.onClick(handler)
  return () => button.offClick(handler)
}

export function hapticSuccess(): void {
  const platform = getPlatform()
  if (platform === 'desktop' || platform === 'web') return
  try {
    hostApp()?.HapticFeedback?.notificationOccurred?.('success')
  } catch {
    // Хаптика не должна ронять экран диагноза.
  }
}

export async function downloadByBridge(url: string, fileName: string): Promise<boolean> {
  const download = hostApp()?.downloadFile
  if (!isInsideMax() || !download) return false
  await download(url, fileName)
  return true
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const link = document.createElement('a')
  const href = URL.createObjectURL(blob)
  link.href = href
  link.download = fileName
  link.click()
  URL.revokeObjectURL(href)
}
