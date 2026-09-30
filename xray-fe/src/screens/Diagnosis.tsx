import { Button } from '@maxhub/max-ui'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, rememberRemovedScan } from '../api/client.ts'
import { ApiError, errorText } from '../api/errors.ts'
import type { Diagnosis as DiagnosisData, MetricId } from '../api/types.ts'
import { hapticSuccess, isInsideMax } from '../bridge/index.ts'
import { buildConclusion } from '../domain/conclusion.ts'
import { formatRub, formatWhen } from '../domain/metrics.ts'
import { FindingCard } from '../widgets/FindingCard.tsx'
import { Notice } from '../widgets/Notice.tsx'

export function Diagnosis({
  snapshotId,
  onMetric,
  onMissing,
  onOpenChat,
  onLoaded,
}: {
  snapshotId: string
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
  const [sheetFont, setSheetFont] = useState<{ fontFamily: string; fontSize: string } | null>(null)
  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null)
  const [exportSuccess, setExportSuccess] = useState('')
  const [exportError, setExportError] = useState('')
  const insideMax = isInsideMax()

  async function handleExport(format: 'pdf' | 'excel') {
    if (exporting) return
    setExportError('')
    setExportSuccess('')
    setExporting(format)

    try {
      if (insideMax) {
        const res = await api.exportToBot(snapshotId, format)
        hapticSuccess()
        setExportSuccess(res.message || 'Отчёт отправлен в диалог с ботом!')
        window.setTimeout(() => {
          closeMore()
          setExportSuccess('')
          setExporting(null)
        }, 1800)
      } else {
        await api.downloadReport(snapshotId, format)
        closeMore()
        setExporting(null)
      }
    } catch (err: unknown) {
      setExportError(errorText(err))
      setExporting(null)
    }
  }
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
        if (reason instanceof ApiError && reason.status === 404) rememberRemovedScan(snapshotId)
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
    if (!diagnosis || copied) return
    const text = buildConclusion(diagnosis)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setFallback('')
      window.clearTimeout(copiedTimer.current)
      const hold = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1100
      copiedTimer.current = window.setTimeout(() => {
        closeMore()
        copiedTimer.current = window.setTimeout(() => setCopied(false), 420)
      }, hold)
    } catch {
      setCopied(false)
      setFallback(text)
      closeMore()
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
    if (!moreOpen) return
    const shell = document.querySelector('.app-shell')
    if (!(shell instanceof HTMLElement)) return
    const style = window.getComputedStyle(shell)
    setSheetFont({ fontFamily: style.fontFamily, fontSize: style.fontSize })
  }, [moreOpen])

  useEffect(() => {
    if (!moreOpen || moreClosing) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') closeMore()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
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
      <div className="findings">
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
      {createPortal(
        <div className="template-dropdown-wrapper" ref={moreWrapRef}>
          <button
            type="button"
            className={`more-dot-btn${moreOpen && !moreClosing ? ' is-away' : ''}`}
            aria-label="Поделиться"
            aria-expanded={moreOpen && !moreClosing}
            onClick={() => {
              if (moreClosing) return
              if (moreOpen) closeMore()
              else setMoreOpen(true)
            }}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3.5v11" />
              <path d="M8 7 12 3.5 16 7" />
              <path d="M6.5 11.5v7.5h11v-7.5" />
            </svg>
          </button>
        </div>,
        document.getElementById('diag-more-slot') ?? document.body,
      )}
      {moreOpen
        ? createPortal(
            <div className={`download-sheet${moreClosing ? ' is-closing' : ''}`}>
              <button type="button" className="download-sheet-backdrop" aria-label="Закрыть" onClick={closeMore} />
              <div
                className="download-sheet-panel"
                role="dialog"
                aria-label="Сохранить снимок"
                style={sheetFont ?? undefined}
              >
                <p className="download-sheet-title">{insideMax ? 'Экспорт отчёта' : 'Сохранить снимок'}</p>

                {exportSuccess ? (
                  <div style={{ color: '#10b981', fontSize: '14px', fontWeight: 600, textAlign: 'center', margin: '4px 0 10px' }}>
                    ✅ {exportSuccess}
                  </div>
                ) : null}

                {exportError ? (
                  <div style={{ color: '#ef4444', fontSize: '13px', textAlign: 'center', margin: '4px 0 10px' }}>
                    ⚠️ {exportError}
                  </div>
                ) : null}

                <button
                  type="button"
                  className={`template-item-btn copy-action${copied ? ' is-copied' : ''}`}
                  onClick={() => void copy()}
                >
                  <span className="copy-action-status">
                    <svg className="copy-action-check" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M5 12.6 9.2 16.8 19 7.2" />
                    </svg>
                    <span className="copy-action-words">
                      <span className="is-idle" aria-hidden={copied}>
                        Скопировать заключение
                      </span>
                      <span className="is-done" aria-hidden={!copied}>
                        Скопировано в буфер обмена
                      </span>
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="template-item-btn"
                  disabled={Boolean(exporting)}
                  onClick={() => void handleExport('pdf')}
                >
                  {exporting === 'pdf'
                    ? 'Отправка PDF в чат...'
                    : insideMax
                    ? '✉️ Отправить PDF в диалог бота'
                    : 'Скачать PDF'}
                </button>
                <button
                  type="button"
                  className="template-item-btn"
                  disabled={Boolean(exporting)}
                  onClick={() => void handleExport('excel')}
                >
                  {exporting === 'excel'
                    ? 'Отправка Excel в чат...'
                    : insideMax
                    ? '✉️ Отправить Excel в диалог бота'
                    : 'Скачать Excel'}
                </button>
              </div>
            </div>,
            document.body,
          )
        : null}
      <div className="diagnosis-actions">
        <Button className="action action-accent" type="button" size="large" stretched variant="primary" onClick={() => onOpenChat(diagnosis)}>
          Что делать
        </Button>
        {skipped ? (
          <Button className="action action-missing" type="button" size="large" stretched variant="secondary" onClick={onMissing}>
            Чего не хватило
          </Button>
        ) : null}
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
