import { Button } from '@maxhub/max-ui'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, usesFixtures } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { SnapshotListItem } from '../api/types.ts'
import { formatWhen, scanCaption } from '../domain/metrics.ts'
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
  const [picking, setPicking] = useState(false)
  const [pickClosing, setPickClosing] = useState(false)
  const [picked, setPicked] = useState<string[]>([])
  const [pickFont, setPickFont] = useState<{ fontFamily: string } | null>(null)
  const emptyTimer = useRef(0)
  const pickTimer = useRef(0)
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
      window.clearTimeout(pickTimer.current)
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
      card_title: 'Тестовая таблица',
      filename: 'test_table.csv',
      topics: ['stagnation'],
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

  function stopPick() {
    if (!picking || pickClosing) return
    setPicking(false)
    setPicked([])
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      window.clearTimeout(pickTimer.current)
      setPickClosing(false)
      return
    }
    setPickClosing(true)
    window.clearTimeout(pickTimer.current)
    pickTimer.current = window.setTimeout(() => setPickClosing(false), 400)
  }

  function startPick() {
    window.clearTimeout(pickTimer.current)
    setPickClosing(false)
    setOpenSwipeId(null)
    setPicked([])
    setPicking(true)
  }

  function togglePicked(id: string) {
    setPicked((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]))
  }

  function removePicked() {
    const ids = picked.filter((id) => !leavingIdsRef.current.includes(id))
    stopPick()
    for (const id of ids) void removeSnapshot(id)
  }

  useLayoutEffect(() => {
    if (!picking && !pickClosing) return
    const shell = document.querySelector('.app-shell')
    if (!(shell instanceof HTMLElement)) return
    setPickFont({ fontFamily: getComputedStyle(shell).fontFamily })
  }, [picking, pickClosing])

  useEffect(() => {
    if (!picking) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') stopPick()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [picking])

  useEffect(() => {
    if (!picking) return
    if (snapshots.every((item) => leavingIds.includes(item.snapshot_id))) stopPick()
  }, [picking, snapshots, leavingIds])

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

  const pickSlot = document.getElementById('diag-more-slot')
  const visible = snapshots.filter((item) => !leavingIds.includes(item.snapshot_id))
  const canPick = scansLoaded && visible.length > 0

  return (
    <div className={`stack scans-screen${picking ? ' is-picking' : ''}`}>
      <div className="lead">
        <h1>Сканы</h1>
      </div>
      {canPick && pickSlot
        ? createPortal(
            <button
              type="button"
              className={`more-dot-btn scans-tool${picking ? ' is-cancel' : ''}`}
              aria-label={picking ? 'Отмена' : 'Выбрать для удаления'}
              onClick={picking ? stopPick : startPick}
            >
              <span className="scans-tool-face scans-tool-trash" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M5 7.5h14" />
                  <path d="M9.5 7.5V6.2A1.2 1.2 0 0 1 10.7 5h2.6A1.2 1.2 0 0 1 14.5 6.2V7.5" />
                  <path d="M8 7.5h8l-.6 11.2A1.6 1.6 0 0 1 13.8 20h-3.6a1.6 1.6 0 0 1-1.6-1.3L8 7.5Z" />
                  <path d="M10.5 11v5M13.5 11v5" />
                </svg>
              </span>
              <span className="scans-tool-face scans-tool-close" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M7 7l10 10M17 7 7 17" />
                </svg>
              </span>
            </button>,
            pickSlot,
          )
        : null}
      {picking || pickClosing
        ? createPortal(
            <div className={`scans-pick-bar${pickClosing ? ' is-closing' : ''}`} style={pickFont ?? undefined}>
              <button
                type="button"
                className="action scans-pick-delete"
                disabled={picked.length === 0}
                onClick={removePicked}
              >
                {picked.length ? `Удалить · ${picked.length}` : 'Удалить'}
              </button>
            </div>,
            document.body,
          )
        : null}
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
                      selecting={picking}
                      selected={picked.includes(item.snapshot_id)}
                      onOpenChange={(next) =>
                        setOpenSwipeId((current) => {
                          if (next) return item.snapshot_id
                          return current === item.snapshot_id ? null : current
                        })
                      }
                      onActivate={() => {
                        if (picking) togglePicked(item.snapshot_id)
                        else void openSnapshot(item)
                      }}
                      onDelete={() => void removeSnapshot(item.snapshot_id)}
                    >
                      <ScanFace item={item} picking={picking} checked={picked.includes(item.snapshot_id)} />
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

function ScanFace({
  item,
  picking = false,
  checked = false,
}: {
  item: SnapshotListItem
  picking?: boolean
  checked?: boolean
}) {
  return (
    <>
      <span className={`scan-check${picking ? ' is-shown' : ''}${checked ? ' is-on' : ''}`} aria-hidden="true">
        <svg viewBox="0 0 24 24">
          <path d="M5 12.6 9.2 16.8 19 7.2" />
        </svg>
      </span>
      <span className="scan-top">
        <span className="scan-meta">
          {shortWhen(item.created_at)}
          {sourceCaption(item.source) ? ` · ${sourceCaption(item.source)}` : ''}
        </span>
        {item.verdict ? (
          <span className={`pill ${item.verdict}`}>
            {verdictName(item.verdict)}
            {item.coverage_label ? ` · ${coverageCaption(item.coverage_label)}` : ''}
          </span>
        ) : (
          <span className={`pill ${item.status}`}>{STATUS[item.status]}</span>
        )}
      </span>
      <span className="scan-title">{cardTitle(item)}</span>
    </>
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

function sourceCaption(source?: string): string {
  if (!source || source === 'miniapp') return ''
  if (source === 'demo') return 'демо'
  return source
}

function coverageCaption(label: string): string {
  return label.replace(/\s*из\s*/u, '/')
}

function tableCaption(filename?: string): string {
  if (!filename) return ''
  return filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
}

function cardTitle(item: SnapshotListItem): string {
  const invented = (item.card_title || '').trim()
  if (invented) return invented
  const table = tableCaption(item.filename)
  if (table) return table
  const topic = scanCaption(item.topics)
  if (topic) return topic
  if (item.verdict === 'ok') return 'В норме'
  if (item.status === 'processing') return 'Считаем'
  if (item.status === 'failed') return 'Не вышло'
  return 'Снимок'
}
