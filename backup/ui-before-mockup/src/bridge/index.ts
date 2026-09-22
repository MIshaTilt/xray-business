import type { Platform } from './types.ts'

const KNOWN_PLATFORMS = new Set<Platform>(['ios', 'android', 'desktop', 'web'])

export function initBridge(): void {
  const app = window.WebApp
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
  return window.WebApp?.initData ?? ''
}

export function isInsideMax(): boolean {
  return Boolean(window.WebApp?.initData)
}

export function getPlatform(): Platform {
  const value = window.WebApp?.platform
  if (value && KNOWN_PLATFORMS.has(value as Platform)) return value as Platform
  if (typeof window.matchMedia === 'function' && window.matchMedia('(min-width: 900px)').matches) return 'web'
  return 'ios'
}

export function setClosingConfirmation(enabled: boolean): void {
  const app = window.WebApp
  if (!app) return
  try {
    if (enabled) app.enableClosingConfirmation?.()
    else app.disableClosingConfirmation?.()
  } catch {
    // В браузере вне MAX подтверждение закрытия недоступно.
  }
}

export function showBack(visible: boolean): void {
  const button = window.WebApp?.BackButton
  if (!button) return
  try {
    if (visible) button.show()
    else button.hide()
  } catch {
    // Кнопки шапки нет вне клиента MAX.
  }
}

export function bindBack(handler: () => void): () => void {
  const button = window.WebApp?.BackButton
  if (!button) return () => undefined
  button.onClick(handler)
  return () => button.offClick(handler)
}

export function hapticSuccess(): void {
  const platform = getPlatform()
  if (platform === 'desktop' || platform === 'web') return
  try {
    window.WebApp?.HapticFeedback?.notificationOccurred?.('success')
  } catch {
    // Хаптика не должна ронять экран диагноза.
  }
}

export async function downloadByBridge(url: string, fileName: string): Promise<boolean> {
  const download = window.WebApp?.downloadFile
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
