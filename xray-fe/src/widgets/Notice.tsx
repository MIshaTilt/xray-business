import type { ReactNode } from 'react'

export function Notice({ tone, children }: { tone: 'error' | 'ok'; children: ReactNode }) {
  return (
    <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}
