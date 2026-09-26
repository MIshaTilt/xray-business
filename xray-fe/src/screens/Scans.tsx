import { Button } from '@maxhub/max-ui'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api, usesFixtures } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { SnapshotListItem } from '../api/types.ts'
import { formatWhen } from '../domain/metrics.ts'
import { Notice } from '../widgets/Notice.tsx'
import { SwipeScan } from '../widgets/SwipeScan.tsx'
import { XRayLogo } from '../widgets/XRayLogo.tsx'

const STATUS: Record<SnapshotListItem['status'], string> = {
  processing: 'Считаем',
  ready: 'Готово',
  failed: 'Не вышло',
}

export function Scans({
  onDiagnosis,
  onProcessing,
}: {
  onDiagnosis: (snapshotId: string) => void
  onProcessing: (snapshotId: string) => void
}) {
  const [busy, setBusy] = useState<'seed' | null>(null)
  const [error, setError] = useState('')
  const [snapshots, setSnapshots] = useState<SnapshotListItem[]>([])
  const [scansLoaded, setScansLoaded] = useState(false)
  const [openSwipeId, setOpenSwipeId] = useState<string | null>(null)
  const [leavingIds, setLeavingIds] = useState<string[]>([])
  const [emptyLeaving, setEmptyLeaving] = useState(false)
  const [enteringIds, setEnteringIds] = useState<string[]>([])
  const emptyTimer = useRef(0)
  const leavingIdsRef = useRef<string[]>([])
  const enterTimerRef = useRef<Record<string, number>>({})

  async function refresh() {
    try {
      setSnapshots(await api.list())
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setScansLoaded(true)
    }
  }

  useEffect(() => {
    void refresh()
    return () => {
      window.clearTimeout(emptyTimer.current)
      Object.values(enterTimerRef.current).forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  useLayoutEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    for (const id of enteringIds) {
      const row = document.querySelector<HTMLElement>(`[data-scan-id="${id}"]`)
      if (!row || row.dataset.enterLock) continue
      row.dataset.enterLock = '1'
      const across = getComputedStyle(row.parentElement!).flexDirection === 'row'
      const size = across ? row.getBoundingClientRect().width : row.getBoundingClientRect().height
      const prop = across ? 'width' : 'height'
      row.style.transition = 'none'
      row.style[prop] = '0px'
      row.style.margin = '0px'
      row.getBoundingClientRect()
      window.requestAnimationFrame(() => {
        row.style.removeProperty('transition')
        row.style[prop] = `${size}px`
        row.style.margin = across ? '0 8px 0 0' : '0 0 8px'
      })
    }
  }, [enteringIds])

  function seedScan() {
    const id = `stub-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
    const item: SnapshotListItem = {
      snapshot_id: id,
      status: 'ready',
      created_at: new Date().toISOString(),
      scan_no: Math.max(0, ...snapshots.map((item) => item.scan_no ?? 0)) + 1,
      headline: 'Пустая заглушка для проверки списка',
      source: 'тест',
      verdict: 'watch',
      coverage_label: '0 из 7',
    }
    if (snapshots.length === 0) {
      setEmptyLeaving(true)
      window.clearTimeout(emptyTimer.current)
      emptyTimer.current = window.setTimeout(() => setEmptyLeaving(false), 420)
    }
    setSnapshots((current) => [item, ...current])
    setEnteringIds((ids) => [...ids, id])
    window.clearTimeout(enterTimerRef.current[id])
    enterTimerRef.current[id] = window.setTimeout(() => {
      setEnteringIds((ids) => ids.filter((item) => item !== id))
      const row = document.querySelector<HTMLElement>(`[data-scan-id="${id}"]`)
      if (row) {
        row.style.height = ''
        row.style.width = ''
        row.style.margin = ''
        delete row.dataset.enterLock
      }
      delete enterTimerRef.current[id]
    }, 520)
    setBusy(null)
  }

  async function openSnapshot(item: SnapshotListItem) {
    setError('')
    if (item.snapshot_id.startsWith('stub-')) return
    if (item.status === 'ready') {
      onDiagnosis(item.snapshot_id)
      return
    }
    if (item.status === 'processing') {
      onProcessing(item.snapshot_id)
      return
    }
    try {
      const poll = await api.poll(item.snapshot_id)
      setError(poll.error || 'Этот снимок не посчитался. Загрузите таблицу ещё раз.')
    } catch (reason) {
      setError(errorText(reason))
    }
  }

  async function removeSnapshot(id: string) {
    if (leavingIdsRef.current.includes(id)) return
    setError('')
    const row = document.querySelector<HTMLElement>(`[data-scan-id="${id}"]`)
    if (row) {
      const across = getComputedStyle(row.parentElement!).flexDirection === 'row'
      const size = across ? row.getBoundingClientRect().width : row.getBoundingClientRect().height
      if (across) row.style.width = `${size}px`
      else row.style.height = `${size}px`
      row.getBoundingClientRect()
      row.classList.add('is-leaving')
      if (across) row.style.width = '0px'
      else row.style.height = '0px'
      row.style.margin = '0px'
    }
    leavingIdsRef.current = [...leavingIdsRef.current, id]
    setLeavingIds(leavingIdsRef.current)
    window.setTimeout(() => {
      setSnapshots((current) => current.filter((item) => item.snapshot_id !== id))
      leavingIdsRef.current = leavingIdsRef.current.filter((item) => item !== id)
      setLeavingIds(leavingIdsRef.current)
      setOpenSwipeId((current) => (current === id ? null : current))
    }, 500)
    if (id.startsWith('stub-')) return
    try {
      await api.remove(id)
    } catch (reason) {
      leavingIdsRef.current = leavingIdsRef.current.filter((item) => item !== id)
      setLeavingIds(leavingIdsRef.current)
      setError(errorText(reason))
      void refresh()
    }
  }

  return (
    <div className="stack scans-screen">
      <div className="lead">
        <h1>Сканы</h1>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {usesFixtures() ? (
        <Button
          className="action action-quiet"
          type="button"
          size="large"
          stretched
          variant="ghost"
          loading={busy === 'seed'}
          onClick={() => seedScan()}
        >
          Случайный скан
        </Button>
      ) : null}
      {!scansLoaded ? (
        <div className="scans-empty" aria-hidden="true">
          <span className="scans-empty-icon">
            <XRayLogo scanning />
          </span>
        </div>
      ) : (
        <section className="history">
          <div className="history-stage">
            {snapshots.length === 0 || emptyLeaving ? (
              <div className={`scans-empty${emptyLeaving ? ' is-leaving' : ''}`}>
                <span className="scans-empty-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M8 3.5h5.2L19 9.2V20a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 7 20V5A1.5 1.5 0 0 1 8.5 3.5H8z" />
                    <path d="M13 3.8V9h5" />
                  </svg>
                </span>
                <p className="scans-empty-title">Сканов пока нет</p>
                <p className="scans-empty-hint">Загрузите таблицу на главной</p>
              </div>
            ) : null}
            {snapshots.length > 0 ? (
              <ul className="scans">
                {snapshots.map((item) => (
                  <li
                    key={item.snapshot_id}
                    data-scan-id={item.snapshot_id}
                    className={
                      leavingIds.includes(item.snapshot_id)
                        ? 'is-leaving'
                        : enteringIds.includes(item.snapshot_id)
                          ? 'is-entering'
                          : undefined
                    }
                  >
                    <SwipeScan
                      open={openSwipeId === item.snapshot_id}
                      onOpenChange={(next) =>
                        setOpenSwipeId((current) => {
                          if (next) return item.snapshot_id
                          return current === item.snapshot_id ? null : current
                        })
                      }
                      onActivate={() => void openSnapshot(item)}
                      onDelete={() => void removeSnapshot(item.snapshot_id)}
                    >
                      <span className="scan-top">
                        <span className="scan-meta">
                          {item.scan_no ? `№${item.scan_no} · ` : ''}
                          {shortWhen(item.created_at)} · {item.source || STATUS[item.status]}
                        </span>
                        {item.verdict ? (
                          <span className={`pill ${item.verdict}`}>
                            {verdictName(item.verdict)} · {item.coverage_label}
                          </span>
                        ) : (
                          <span className={`pill ${item.status}`}>{STATUS[item.status]}</span>
                        )}
                      </span>
                      <span className="scan-title">{item.headline || 'Снимок без заключения'}</span>
                    </SwipeScan>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </section>
      )}
    </div>
  )
}

function shortWhen(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  const date = match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : new Date(iso)
  if (Number.isNaN(date.getTime())) return formatWhen(iso)
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(date).replace('.', '')
}

function verdictName(verdict: 'critical' | 'watch' | 'ok'): string {
  if (verdict === 'critical') return 'критично'
  if (verdict === 'watch') return 'следить'
  return 'норма'
}
