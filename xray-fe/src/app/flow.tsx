import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { UploadResponse } from '../api/types.ts'

const UPLOAD_KEY = 'xray-upload'
const SCAN_KEY = 'xray-last-scan'

type FlowValue = {
  upload: UploadResponse | null
  setUpload: (upload: UploadResponse | null) => void
  lastScanId: string | null
  setLastScanId: (id: string | null) => void
  veil: boolean
  veilLeaving: boolean
  beginVeil: () => void
  stopVeil: () => void
  finishVeil: () => void
  dark: boolean
  toggleTheme: () => void
}

const FlowContext = createContext<FlowValue | null>(null)

function readUpload(): UploadResponse | null {
  try {
    const raw = sessionStorage.getItem(UPLOAD_KEY)
    return raw ? (JSON.parse(raw) as UploadResponse) : null
  } catch {
    return null
  }
}

export function FlowProvider({ children }: { children: ReactNode }) {
  const [upload, setUploadState] = useState<UploadResponse | null>(readUpload)
  const [lastScanId, setLastScanState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(SCAN_KEY) || sessionStorage.getItem(SCAN_KEY)
    } catch {
      return null
    }
  })
  const [veil, setVeil] = useState(false)
  const [veilLeaving, setVeilLeaving] = useState(false)
  const [dark, setDark] = useState(() => window.localStorage.getItem('xray-theme') === 'dark')
  const veilRef = useRef(false)

  useEffect(() => {
    veilRef.current = veil
  }, [veil])

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    window.localStorage.setItem('xray-theme', dark ? 'dark' : 'light')
  }, [dark])

  const setUpload = useCallback((next: UploadResponse | null) => {
    setUploadState(next)
    if (next) sessionStorage.setItem(UPLOAD_KEY, JSON.stringify(next))
    else sessionStorage.removeItem(UPLOAD_KEY)
  }, [])

  const setLastScanId = useCallback((id: string | null) => {
    setLastScanState(id)
    try {
      if (id) {
        localStorage.setItem(SCAN_KEY, id)
        sessionStorage.setItem(SCAN_KEY, id)
      } else {
        localStorage.removeItem(SCAN_KEY)
        sessionStorage.removeItem(SCAN_KEY)
      }
    } catch {
      // ignore
    }
  }, [])

  const beginVeil = useCallback(() => {
    setVeilLeaving(false)
    setVeil(true)
  }, [])

  const hideVeil = useCallback(() => {
    setVeil(false)
    setVeilLeaving(false)
  }, [])

  const stopVeil = useCallback(() => {
    setVeilLeaving(true)
  }, [])

  const finishVeil = useCallback(() => {
    if (!veilRef.current) return
    window.setTimeout(() => {
      if (veilRef.current) setVeilLeaving(true)
    }, 480)
  }, [])

  useEffect(() => {
    if (!veilLeaving) return
    const id = window.setTimeout(hideVeil, 520)
    return () => window.clearTimeout(id)
  }, [hideVeil, veilLeaving])

  useEffect(() => {
    if (!veil) return
    const block = (event: Event) => event.preventDefault()
    document.documentElement.classList.add('veil-lock')
    document.addEventListener('touchmove', block, { passive: false })
    document.addEventListener('wheel', block, { passive: false })
    return () => {
      document.documentElement.classList.remove('veil-lock')
      document.removeEventListener('touchmove', block)
      document.removeEventListener('wheel', block)
    }
  }, [veil])

  const toggleTheme = useCallback(() => {
    setDark((value) => !value)
  }, [])

  const value = useMemo(
    () => ({
      upload,
      setUpload,
      lastScanId,
      setLastScanId,
      veil,
      veilLeaving,
      beginVeil,
      stopVeil,
      finishVeil,
      dark,
      toggleTheme,
    }),
    [
      upload,
      setUpload,
      lastScanId,
      setLastScanId,
      veil,
      veilLeaving,
      beginVeil,
      stopVeil,
      finishVeil,
      dark,
      toggleTheme,
    ],
  )

  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>
}

export function useFlow() {
  const value = useContext(FlowContext)
  if (!value) throw new Error('useFlow')
  return value
}
