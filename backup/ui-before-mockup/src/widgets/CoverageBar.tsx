import { Typography } from '@maxhub/max-ui'
import type { Coverage } from '../api/types.ts'
import { METRIC_ORDER, METRICS } from '../domain/metrics.ts'

export function CoverageBar({ coverage }: { coverage: Coverage }) {
  const counted = coverage.available.length
  return (
    <div className="coverage">
      <Typography.Headline variant="small">Можем посчитать {counted} из 7</Typography.Headline>
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
    </div>
  )
}
