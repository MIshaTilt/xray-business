import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react'

function kindOf(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'csv') return 'CSV'
  return 'Файл'
}

const ALLOWED = /\.csv$/i

function sizeOf(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

export function FileDrop({
  file,
  busy,
  onPick,
  onSend,
  onClear,
  extra,
  hideButton = false,
  inputRef,
}: {
  file: File | null
  busy: boolean
  onPick: (file: File) => void
  onSend: () => void
  onClear: () => void
  extra?: ReactNode
  hideButton?: boolean
  inputRef?: RefObject<HTMLInputElement | null>
}) {
  const localInput = useRef<HTMLInputElement>(null)
  const input = inputRef ?? localInput
  const slot = useRef<HTMLDivElement>(null)
  const hideTimer = useRef(0)
  const [leaving, setLeaving] = useState(false)
  const visible = Boolean(file) || leaving

  useEffect(() => () => window.clearTimeout(hideTimer.current), [])

  useLayoutEffect(() => {
    const node = slot.current
    if (!node || !file || leaving) return
    node.style.height = '0px'
    node.style.opacity = '0'
    const height = node.scrollHeight
    requestAnimationFrame(() => {
      node.style.height = `${height}px`
      node.style.opacity = '1'
    })
    const done = (event: TransitionEvent) => {
      if (event.propertyName !== 'height' || !slot.current) return
      slot.current.style.height = 'auto'
      slot.current.removeEventListener('transitionend', done)
    }
    node.addEventListener('transitionend', done)
    return () => {
      node.removeEventListener('transitionend', done)
    }
  }, [file])

  function remove() {
    if (busy || leaving) return
    const node = slot.current
    if (!node) {
      onClear()
      return
    }
    const height = node.getBoundingClientRect().height
    node.style.height = `${height}px`
    node.style.opacity = '1'
    setLeaving(true)
    requestAnimationFrame(() => {
      node.style.height = '0px'
      node.style.opacity = '0'
    })
    window.clearTimeout(hideTimer.current)
    hideTimer.current = window.setTimeout(() => {
      setLeaving(false)
      onClear()
    }, 480)
  }

  return (
    <div className="file-drop">
      <input
        ref={input}
        className="file-input"
        type="file"
        accept=".csv,text/csv"
        onChange={(event) => {
          const next = event.target.files?.[0]
          event.target.value = ''
          if (next && ALLOWED.test(next.name)) onPick(next)
        }}
      />
      {hideButton ? null : (
        <Button className="action action-primary" type="button" size="large" stretched variant="primary" onClick={() => input.current?.click()}>
          Загрузить файл
        </Button>
      )}
      {visible ? (
        <div ref={slot} className={`file-card-slot${leaving ? ' is-leaving' : ''}`}>
          <div className="file-card-pad">
          <div className="file-card">
            <div className="file-card-meta">
              <div className="file-card-meta-text">
                <Typography.Body variant="medium-strong">{file?.name}</Typography.Body>
                <Typography.Label variant="small">
                  {file ? `${sizeOf(file.size)} · ${kindOf(file.name)}` : ''}
                </Typography.Label>
              </div>
              <button
                type="button"
                className="file-card-remove"
                aria-label="Убрать файл"
                disabled={busy}
                onClick={remove}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </div>
            <Button className="action action-secondary" type="button" size="medium" stretched variant="secondary" loading={busy} onClick={onSend}>
              Отправить таблицу
            </Button>
          </div>
          </div>
        </div>
      ) : null}
      {extra}
    </div>
  )
}
