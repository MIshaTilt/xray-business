export type Platform = 'ios' | 'android' | 'desktop' | 'web'

export type MaxUser = {
  id: number
  first_name: string
  last_name?: string
  username?: string
  photo_url?: string
}

export type MaxWebApp = {
  initData?: string
  initDataUnsafe?: { user?: MaxUser }
  platform?: string
  ready?: () => void
  expand?: () => void
  enableClosingConfirmation?: () => void
  disableClosingConfirmation?: () => void
  BackButton?: {
    show: () => void
    hide: () => void
    onClick: (callback: () => void) => void
    offClick: (callback: () => void) => void
  }
  downloadFile?: (url: string, fileName: string) => Promise<unknown>
  HapticFeedback?: {
    notificationOccurred?: (type: 'error' | 'success' | 'warning', disableVibrationFallback?: boolean) => void
  }
}

declare global {
  interface Window {
    WebApp?: MaxWebApp
    Telegram?: { WebApp?: MaxWebApp }
  }
}
