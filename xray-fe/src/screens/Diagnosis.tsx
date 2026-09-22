import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { Diagnosis as DiagnosisData, MetricId } from '../api/types.ts'
import { hapticSuccess } from '../bridge/index.ts'
import { buildConclusion } from '../domain/conclusion.ts'
import { formatRub, formatWhen } from '../domain/metrics.ts'
import { FindingCard } from '../widgets/FindingCard.tsx'
import { Notice } from '../widgets/Notice.tsx'

export function Diagnosis({
  snapshotId,
  wide,
  onMetric,
  onMissing,
  onNew,
  onOpenChat,
}: {
  snapshotId: string
  wide: boolean
  onMetric: (metricId: MetricId) => void
  onMissing: () => void
  onNew: () => void
  onOpenChat: (diagnosis: DiagnosisData) => void
}) {
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [fallback, setFallback] = useState('')

  useEffect(() => {
    let alive = true
    void api
      .diagnosis(snapshotId)
      .then((result) => {
        if (!alive) return
        setDiagnosis(result)
        hapticSuccess()
      })
      .catch((reason: unknown) => {
        if (alive) setError(errorText(reason))
      })
    return () => {
      alive = false
    }
  }, [snapshotId])

  async function copy() {
    if (!diagnosis) return
    const text = buildConclusion(diagnosis)
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setFallback('')
    } catch {
      setCopied(false)
      setFallback(text)
    }
  }

  if (error) return <Notice tone="error">{error}</Notice>
  if (!diagnosis) return <Typography.Body variant="medium">Собираем заключение…</Typography.Body>

  const period = diagnosis.period.from && diagnosis.period.to
    ? `${formatWhen(diagnosis.period.from)} — ${formatWhen(diagnosis.period.to)}`
    : 'Период по датам в файле'
  const counted = diagnosis.coverage.available.length

  return (
    <div className="stack diagnosis">
      <div className="stat-row">
        <article>
          <strong>{period}</strong>
          <span>период</span>
        </article>
        <article>
          <strong>{diagnosis.totals.deals} · {shortMoney(diagnosis.totals.amount)}</strong>
          <span>сделки</span>
        </article>
      </div>
      <div className="banner">{diagnosis.headline}</div>
      <div className={wide ? 'findings wide' : 'findings'}>
        {diagnosis.findings.slice(0, 4).map((finding) => (
          <FindingCard key={finding.metric_id} finding={finding} onOpen={() => onMetric(finding.metric_id)} />
        ))}
      </div>
      <p className="coverage-line">Посчитано {counted} из 7</p>
      {copied ? <Notice tone="ok">Заключение в буфере. Его можно переслать самому.</Notice> : null}
      {fallback ? (
        <label className="stack">
          <span className="home-hint">Буфер недоступен. Выделите текст и скопируйте его сами.</span>
          <textarea className="copy-fallback" readOnly value={fallback} />
        </label>
      ) : null}
      <div className="diagnosis-actions">
        <Button
          className="action action-accent"
          type="button"
          size="large"
          stretched
          variant="primary"
          onClick={() => diagnosis && onOpenChat(diagnosis)}
        >
          💬 Задать вопрос AI по отчету
        </Button>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', width: '100%' }}>
          <Button
            className="action action-secondary"
            type="button"
            size="large"
            stretched
            variant="secondary"
            onClick={() => {
              const base = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
              window.open(`${base}/api/snapshots/${snapshotId}/export-pdf`, '_blank')
            }}
          >
            📄 Скачать PDF
          </Button>
          <Button
            className="action action-secondary"
            type="button"
            size="large"
            stretched
            variant="secondary"
            onClick={() => {
              const base = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')
              window.open(`${base}/api/snapshots/${snapshotId}/export-excel`, '_blank')
            }}
          >
            📊 Скачать Excel
          </Button>
        </div>
        <Button className="action action-secondary" type="button" size="large" stretched variant="secondary" onClick={() => void copy()}>
          {copied ? 'Скопировано' : 'Скопировать заключение'}
        </Button>
        <Button className="action action-quiet" type="button" size="large" stretched variant="ghost" onClick={onMissing}>
          Чтобы увидеть больше
        </Button>
        <Button className="action action-primary" type="button" size="large" stretched variant="ghost" onClick={onNew}>
          Новый снимок
        </Button>
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
