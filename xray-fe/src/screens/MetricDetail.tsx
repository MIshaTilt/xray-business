import { Typography } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { MetricDetail as MetricPayload, MetricId } from '../api/types.ts'
import { formatImpact, METRICS, verdictLabel } from '../domain/metrics.ts'
import { DealTable } from '../widgets/DealTable.tsx'
import { Notice } from '../widgets/Notice.tsx'

export function MetricDetail({
  snapshotId,
  metricId,
  wide,
}: {
  snapshotId: string
  metricId: MetricId
  wide: boolean
}) {
  const [detail, setDetail] = useState<MetricPayload | null>(null)
  const [error, setError] = useState('')
  const copy = METRICS[metricId]

  useEffect(() => {
    let alive = true
    void api
      .metric(snapshotId, metricId)
      .then((result) => {
        if (alive) setDetail(result)
      })
      .catch((reason: unknown) => {
        if (alive) setError(errorText(reason))
      })
    return () => {
      alive = false
    }
  }, [metricId, snapshotId])

  if (error) return <Notice tone="error">{error}</Notice>
  if (!detail) return <Typography.Body variant="medium">Открываем сделки…</Typography.Body>

  return (
    <div className="stack">
      <div className="lead">
        <p className="section-title">{verdictLabel(detail.result.verdict)}</p>
        <Typography.Title variant="medium-strong">{copy.title}</Typography.Title>
        <Typography.Headline variant="medium">
          {detail.result.available ? formatImpact(detail.result) : 'Не посчитано'}
        </Typography.Headline>
      </div>
      <section className="explain">
        <h2 className="section-title">Что это</h2>
        <p className="section-body">{copy.what}</p>
        <h2 className="section-title">Как считаем</h2>
        <p className="section-body">{detail.result.available ? copy.how : copy.hint}</p>
        {detail.result.threshold_label ? <p className="section-body">{detail.result.threshold_label}</p> : null}
      </section>
      {detail.result.available ? <p className="section-body">{detail.result.action}</p> : null}
      <h2 className="section-title">Сделки, из которых сложилась цифра</h2>
      <DealTable rows={detail.evidence} wide={wide} />
    </div>
  )
}
