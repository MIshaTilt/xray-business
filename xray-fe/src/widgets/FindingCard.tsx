import { useState } from 'react'
import type { Finding, Verdict } from '../api/types.ts'
import { formatImpact, METRICS, verdictLabel } from '../domain/metrics.ts'

function verdictName(verdict: Verdict): string {
  if (verdict === 'critical') return 'критично'
  if (verdict === 'watch') return 'следить'
  if (verdict === 'ok') return 'норма'
  return 'не посчитано'
}

function shortRub(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return value
  if (amount >= 1_000_000) {
    const millions = amount / 1_000_000
    const text = millions >= 10 ? String(Math.round(millions)) : millions.toFixed(1).replace('.', ',')
    return `${text} млн`
  }
  if (amount >= 1000) return `${Math.round(amount / 1000)} тыс.`
  return `${Math.round(amount)} ₽`
}

function factLine(finding: Finding): string {
  if (finding.money_impact && finding.unit === 'deals') return `${finding.value} сделок на ${shortRub(finding.money_impact)}`
  if (finding.unit === 'pct') return `${finding.value}%`
  return formatImpact(finding)
}

export function FindingCard({ finding, onOpen }: { finding: Finding; onOpen: () => void }) {
  const [open, setOpen] = useState(false)
  const copy = METRICS[finding.metric_id]

  return (
    <article className={`finding ${finding.verdict}`} onClick={onOpen}>
      <div className="finding-open">
        <span className={`pill ${finding.verdict}`}>{verdictName(finding.verdict)}</span>
        <strong className="finding-fact">{factLine(finding)}</strong>
        <p className={open ? 'finding-text' : 'finding-text clamp'}>{finding.action}</p>
        <span className="finding-title">{copy.title}</span>
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
