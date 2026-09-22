import { Typography } from '@maxhub/max-ui'
import { useState } from 'react'
import type { Finding } from '../api/types.ts'
import { formatImpact, METRICS, verdictLabel } from '../domain/metrics.ts'

export function FindingCard({ finding, onOpen }: { finding: Finding; onOpen: () => void }) {
  const [open, setOpen] = useState(false)
  const copy = METRICS[finding.metric_id]

  return (
    <article className={`finding ${finding.verdict}`} onClick={onOpen}>
      <div className="finding-open">
        <Typography.Label variant="small-strong">{copy.title}</Typography.Label>
        <Typography.Title variant="medium-strong">{formatImpact(finding)}</Typography.Title>
        <p className={open ? 'finding-text' : 'finding-text clamp'}>{finding.action}</p>
      </div>
      <div className={open ? 'finding-extra open' : 'finding-extra'}>
        <div>
          <p className="finding-note">{verdictLabel(finding.verdict)}. {finding.threshold_label}</p>
          <p className="finding-note">{copy.what}</p>
        </div>
      </div>
      <button
        type="button"
        className="finding-more"
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation()
          setOpen((value) => !value)
        }}
      >
        {open ? 'Свернуть' : 'Ещё'}
      </button>
    </article>
  )
}
