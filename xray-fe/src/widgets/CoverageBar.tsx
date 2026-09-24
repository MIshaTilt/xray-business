import { Typography } from '@maxhub/max-ui'
import type { Coverage, MetricId } from '../api/types.ts'
import { METRIC_ORDER, METRICS } from '../domain/metrics.ts'

export function CoverageBar({ coverage }: { coverage: Coverage }) {
  const counted = coverage.available.length
  const available = METRIC_ORDER.filter((id) => coverage.available.includes(id))
  const skipped = METRIC_ORDER.filter((id) => coverage.skipped.includes(id))
  return (
    <div className="coverage">
      <Typography.Headline variant="small">Показателей: {counted} из 7</Typography.Headline>
      <div className="segments" aria-hidden="true">
        {METRIC_ORDER.map((id, index) => (
          <span
            key={id}
            className={coverage.available.includes(id) ? 'on' : 'off'}
            style={{ animationDelay: `${index * 70}ms` }}
            title={METRICS[id].title}
          />
        ))}
      </div>
      <div className="coverage-lists">
        {available.length > 0 ? (
          <CoverageGroup title="Будет посчитано" ids={available} ready />
        ) : null}
        {skipped.length > 0 ? (
          <CoverageGroup title="Невозможно посчитать" ids={skipped} ready={false} extraTop />
        ) : null}
      </div>
    </div>
  )
}

function CoverageGroup({
  title,
  ids,
  ready,
  extraTop,
}: {
  title: string
  ids: MetricId[]
  ready: boolean
  extraTop?: boolean
}) {
  return (
    <div className={`coverage-group${extraTop ? ' is-spaced' : ''}`}>
      <p className="coverage-group-title">{title}</p>
      <ul>
        {ids.map((id) => (
          <li key={id} className={ready ? 'is-on' : 'is-off'}>
            <span className="coverage-name">{METRICS[id].title}</span>
            {ready ? null : <span className="coverage-need">Нужны: {METRICS[id].needs}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
