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
}: {
  snapshotId: string
  metricId: MetricId
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

  const verdict = detail.result.verdict
  return (
    <div className="stack metric-detail">
      <div className="lead">
        <p className={`metric-verdict is-${verdict}`}>{verdictLabel(verdict)}</p>
        <h1>{copy.title}</h1>
        <p className={`metric-value is-${verdict}`}>
          {detail.result.available ? formatImpact(detail.result) : 'Не посчитано'}
        </p>
      </div>
      <section className="explain">
        <div>
          <h2 className="section-title">Что это</h2>
          <p className="section-body">{copy.what}</p>
        </div>
        <div>
          <h2 className="section-title">Как считаем</h2>
          <p className="section-body">{detail.result.available ? copy.how : copy.hint}</p>
          {detail.result.threshold_label ? (
            <p className="metric-note">{detail.result.threshold_label}</p>
          ) : null}
        </div>
      </section>
      {detail.result.available && detail.result.action ? (
        <h2 className={`metric-action is-${verdict}`}>{detail.result.action}</h2>
      ) : null}
      <h2 className="section-title">Сделки, из которых сложилась цифра</h2>
      <DealTable rows={detail.evidence} wide />
    </div>
  )
}
