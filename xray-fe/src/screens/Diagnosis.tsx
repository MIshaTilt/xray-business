import { Button } from '@maxhub/max-ui'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { Diagnosis as DiagnosisData, MetricId } from '../api/types.ts'
import { hapticSuccess } from '../bridge/index.ts'
import { buildConclusion } from '../domain/conclusion.ts'
import { formatRub, formatWhen } from '../domain/metrics.ts'
import { FindingCard } from '../widgets/FindingCard.tsx'
import { InsetVScroll } from '../widgets/InsetVScroll.tsx'
import { Notice } from '../widgets/Notice.tsx'

export function Diagnosis({
  snapshotId,
  wide,
  onMetric,
  onMissing,
  onOpenChat,
  onLoaded,
}: {
  snapshotId: string
  wide: boolean
  onMetric: (metricId: MetricId) => void
  onMissing: () => void
  onOpenChat: (diagnosis: DiagnosisData) => void
  onLoaded: () => void
}) {
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [fallback, setFallback] = useState('')
  const [moreOpen, setMoreOpen] = useState(false)
  const [moreClosing, setMoreClosing] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const copiedTimer = useRef(0)
  const moreTimer = useRef(0)
  const moreWrapRef = useRef<HTMLDivElement>(null)
  const [moreBox, setMoreBox] = useState<{ top: number; left: number; width: number } | null>(null)
  useEffect(() => {
    let alive = true
    void api
      .diagnosis(snapshotId)
      .then((result) => {
        if (!alive) return
        setDiagnosis(result)
        hapticSuccess()
        onLoaded()
      })
      .catch((reason: unknown) => {
        if (!alive) return
        setError(errorText(reason))
        onLoaded()
      })
    return () => {
      alive = false
      window.clearTimeout(copiedTimer.current)
      window.clearTimeout(moreTimer.current)
    }
  }, [onLoaded, snapshotId])

  async function copy() {
    if (!diagnosis) return
    const text = buildConclusion(diagnosis)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setFallback('')
      window.clearTimeout(copiedTimer.current)
      copiedTimer.current = window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
      setFallback(text)
    }
  }

  function closeMore() {
    if (!moreOpen || moreClosing) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setMoreOpen(false)
      return
    }
    setMoreClosing(true)
    window.clearTimeout(moreTimer.current)
    moreTimer.current = window.setTimeout(() => {
      setMoreOpen(false)
      setMoreClosing(false)
    }, 420)
  }

  useLayoutEffect(() => {
    if (!moreOpen) {
      setMoreBox(null)
      return
    }
    function place() {
      const host = moreWrapRef.current
      if (!host) return
      const trigger = (host.querySelector('button') ?? host) as HTMLElement
      const rect = trigger.getBoundingClientRect()
      setMoreBox({
        top: rect.bottom + window.scrollY + 8,
        left: rect.left + window.scrollX,
        width: rect.width,
      })
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [moreOpen])

  useEffect(() => {
    if (!moreOpen || moreClosing) return
    function onPointer(event: PointerEvent) {
      const target = event.target as Node | null
      if (moreWrapRef.current?.contains(target)) return
      if (target instanceof Element && target.closest('.template-dropdown-menu')) return
      closeMore()
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') closeMore()
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [moreOpen, moreClosing])

  if (error) return <Notice tone="error">{error}</Notice>
  if (!diagnosis) return null

  const counted = diagnosis.coverage.available.length
  const skipped = diagnosis.coverage?.skipped?.length ?? 0
  const periodFrom = diagnosis.period.from ? formatWhen(diagnosis.period.from) : ''
  const periodTo = diagnosis.period.to ? formatWhen(diagnosis.period.to) : ''
  const period = periodFrom && periodTo ? `${periodFrom} — ${periodTo}` : ''
  const findings = diagnosis.findings
  const visible = showAll ? findings : findings.slice(0, 3)
  const hidden = Math.max(0, findings.length - 3)
  const exportBase = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

  return (
    <div className="stack diagnosis">
      <div className="lead">
        <p className="eyebrow">Сводка</p>
        <h1>{diagnosis.headline}</h1>
        <p className="diag-totals">
          {period ? `${period} · ` : ''}
          {diagnosis.totals.deals} сделок · {shortMoney(diagnosis.totals.amount)}
        </p>
      </div>
      <div className={wide ? 'findings wide' : 'findings'}>
        {visible.map((finding) => (
          <FindingCard key={finding.metric_id} finding={finding} onOpen={() => onMetric(finding.metric_id)} />
        ))}
      </div>
      {!showAll && hidden > 0 ? (
        <button type="button" className="action action-quiet findings-more" onClick={() => setShowAll(true)}>
          Ещё {hidden}
        </button>
      ) : null}
      <p className="coverage-line">
        Посчитано {counted} из 7
        {skipped ? ` · не хватило колонок для ${skipped}` : ''}
      </p>
      {fallback ? (
        <label className="stack">
          <span className="home-hint">Буфер недоступен. Выделите текст и скопируйте его сами.</span>
          <textarea className="copy-fallback" readOnly value={fallback} />
        </label>
      ) : null}
      <div className="diagnosis-actions">
        <Button className="action action-accent" type="button" size="large" stretched variant="primary" onClick={() => onOpenChat(diagnosis)}>
          Что делать
        </Button>
        <div className="template-dropdown-wrapper" ref={moreWrapRef}>
          <Button
            className="action action-secondary"
            type="button"
            size="large"
            stretched
            variant="secondary"
            onClick={() => {
              if (moreClosing) return
              if (moreOpen) closeMore()
              else setMoreOpen(true)
            }}
          >
            <span className="template-label">
              Ещё
              <span className={`template-caret${moreOpen && !moreClosing ? ' open' : ''}`} aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M6 9.5 12 15.5 18 9.5" />
                </svg>
              </span>
            </span>
          </Button>
          {moreOpen && moreBox
            ? createPortal(
                <div
                  className={`template-dropdown-menu is-portal${moreClosing ? ' is-closing' : ''}`}
                  style={{
                    top: moreBox.top,
                    left: moreBox.left,
                    width: moreBox.width,
                    right: 'auto',
                  }}
                >
                  <InsetVScroll watch={`${moreOpen}:${skipped}:${copied}`}>
                    <button
                      type="button"
                      className="template-item-btn"
                      onClick={() => {
                        closeMore()
                        void copy()
                      }}
                    >
                      {copied ? 'Скопировано' : 'Скопировать заключение'}
                    </button>
                    <button
                      type="button"
                      className="template-item-btn"
                      onClick={() => {
                        closeMore()
                        window.open(`${exportBase}/api/snapshots/${snapshotId}/export-pdf`, '_blank')
                      }}
                    >
                      Скачать PDF
                    </button>
                    <button
                      type="button"
                      className="template-item-btn"
                      onClick={() => {
                        closeMore()
                        window.open(`${exportBase}/api/snapshots/${snapshotId}/export-excel`, '_blank')
                      }}
                    >
                      Скачать Excel
                    </button>
                    {skipped ? (
                      <button
                        type="button"
                        className="template-item-btn"
                        onClick={() => {
                          closeMore()
                          onMissing()
                        }}
                      >
                        Чего не хватило
                      </button>
                    ) : null}
                  </InsetVScroll>
                </div>,
                document.body,
              )
            : null}
        </div>
      </div>
    </div>
  )
}

function shortMoney(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return value
  if (amount >= 1_000_000) {
    const millions = amount / 1_000_000
    const text = millions >= 10 ? String(Math.round(millions)) : millions.toFixed(1).replace('.', ',')
    return `${text} млн`
  }
  if (amount >= 1000) return `${Math.round(amount / 1000)} тыс.`
  return formatRub(value)
}
