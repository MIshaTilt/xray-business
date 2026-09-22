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
}: {
  snapshotId: string
  wide: boolean
  onMetric: (metricId: MetricId) => void
  onMissing: () => void
  onNew: () => void
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
    <div className="stack">
      <div className="lead">
        <Typography.Label variant="small">{period}</Typography.Label>
        <Typography.Title variant="medium-strong">
          {diagnosis.totals.deals} сделок · {formatRub(diagnosis.totals.amount)}
        </Typography.Title>
        <Typography.Body variant="medium">Покрытие {counted}/7. Принято {diagnosis.totals.accepted}, отброшено {diagnosis.totals.rejected}.</Typography.Body>
      </div>
      <div className="lead verdict-line">
        <Typography.Headline variant="medium">{diagnosis.headline}</Typography.Headline>
      </div>
      <div className={wide ? 'findings wide' : 'findings'}>
        {diagnosis.findings.slice(0, 3).map((finding) => (
          <FindingCard key={finding.metric_id} finding={finding} onOpen={() => onMetric(finding.metric_id)} />
        ))}
      </div>
      <Typography.Body variant="medium">
        Посчитано: {diagnosis.coverage.available.length}. Пропущено: {diagnosis.coverage.skipped.length}.
      </Typography.Body>
      {copied ? <Notice tone="ok">Заключение в буфере. Его можно переслать самому.</Notice> : null}
      {fallback ? (
        <label className="stack">
          <Typography.Label variant="small">Буфер недоступен. Выделите текст и скопируйте его сами.</Typography.Label>
          <textarea className="copy-fallback" readOnly value={fallback} />
        </label>
      ) : null}
      <Button className="action action-primary" type="button" size="large" stretched variant="primary" onClick={() => void copy()}>
        {copied ? 'Скопировано' : 'Скопировать заключение'}
      </Button>
      <Button className="action action-secondary" type="button" size="large" stretched variant="secondary" onClick={onMissing}>
        Чтобы увидеть больше
      </Button>
      <Button className="action action-quiet" type="button" size="large" stretched variant="ghost" onClick={onNew}>
        Новый снимок
      </Button>
    </div>
  )
}
