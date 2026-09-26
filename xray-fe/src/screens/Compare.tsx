import { useEffect, useState } from 'react'
import { Button } from '@maxhub/max-ui'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { ComparisonResult, MetricDiffItem } from '../api/types.ts'
import { formatRub, formatWhen } from '../domain/metrics.ts'
import { Notice } from '../widgets/Notice.tsx'

export function Compare({
  baseId,
  targetId,
  onOpenSnapshot,
  onOpenChat,
  onLoaded,
}: {
  baseId: string
  targetId: string
  onOpenSnapshot?: (snapshotId: string) => void
  onOpenChat?: (comparisonId?: string) => void
  onLoaded?: () => void
}) {
  const [data, setData] = useState<ComparisonResult | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    setError('')

    api
      .compare(baseId, targetId)
      .then((result) => {
        if (!alive) return
        setData(result)
        onLoaded?.()
      })
      .catch((err) => {
        if (!alive) return
        setError(errorText(err))
        onLoaded?.()
      })

    return () => {
      alive = false
    }
  }, [baseId, targetId, onLoaded])

  if (error) {
    return (
      <div className="stack compare-screen">
        <div className="lead">
          <p className="eyebrow">Сравнение</p>
          <h1>Ошибка анализа</h1>
        </div>
        <Notice tone="error">{error}</Notice>
      </div>
    )
  }

  if (!data) return null


  const baseLabel = data.base.filename || shortDate(data.base.created_at)
  const targetLabel = data.target.filename || shortDate(data.target.created_at)

  return (
    <div className="stack compare-screen">
      <div className="lead">
        <p className="eyebrow">Динамика бизнеса</p>
        <h1>Сравнение срезов</h1>

        <div className="compare-range-bar">
          <button
            type="button"
            className="compare-chip"
            onClick={() => onOpenSnapshot?.(data.base.snapshot_id)}
            title="Открыть базовый снимок"
          >
            <span className="compare-chip-role">База</span>
            <span className="compare-chip-title">{baseLabel}</span>
            <span className="compare-chip-date">{shortDate(data.base.created_at)}</span>
          </button>
          <span className="compare-arrow" aria-hidden="true">➔</span>
          <button
            type="button"
            className="compare-chip is-target"
            onClick={() => onOpenSnapshot?.(data.target.snapshot_id)}
            title="Открыть текущий снимок"
          >
            <span className="compare-chip-role">Текущий</span>
            <span className="compare-chip-title">{targetLabel}</span>
            <span className="compare-chip-date">{shortDate(data.target.created_at)}</span>
          </button>
        </div>
      </div>
          {/* Hero Executive AI Narrative Card */}
          <section className={`compare-hero-card ${data.summary.trend}`}>
            <div className="compare-hero-top">
              {data.total_saved_money > 0 ? (
                <span className="compare-saved-badge">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 2 3 7v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5Z" />
                    <path d="m9 12 2 2 4-4" />
                  </svg>
                  <span>+{formatRub(data.total_saved_money)} спасено</span>
                </span>
              ) : (
                <span className={`pill ${data.summary.trend === 'improved' ? 'ok' : 'watch'}`}>
                  {data.summary.trend === 'improved' ? 'Позитивная динамика' : 'Внимание к рискам'}
                </span>
              )}
            </div>
            <h2 className="compare-hero-headline">{data.summary.headline}</h2>
            <p className="compare-hero-body">{data.summary.body}</p>
          </section>

          {/* Totals Delta Grid */}
          <section className="compare-totals-grid">
            <div className="compare-total-card">
              <span className="compare-total-label">Выручка</span>
              <strong className="compare-total-val">{shortMoney(data.totals_diff.amount.target)}</strong>
              <div className="compare-total-sub">
                <span className="compare-prev-val">было {shortMoney(data.totals_diff.amount.base)}</span>
                <span className={`compare-delta-pill ${data.totals_diff.amount.status}`}>
                  {formatDeltaPct(data.totals_diff.amount.delta_pct)}
                </span>
              </div>
            </div>

            <div className="compare-total-card">
              <span className="compare-total-label">Сделок</span>
              <strong className="compare-total-val">{data.totals_diff.deals.target}</strong>
              <div className="compare-total-sub">
                <span className="compare-prev-val">было {data.totals_diff.deals.base}</span>
                <span className={`compare-delta-pill ${data.totals_diff.deals.status}`}>
                  {formatDeltaPct(data.totals_diff.deals.delta_pct)}
                </span>
              </div>
            </div>

            <div className="compare-total-card">
              <span className="compare-total-label">Средний чек</span>
              <strong className="compare-total-val">{shortMoney(data.totals_diff.avg_check.target)}</strong>
              <div className="compare-total-sub">
                <span className="compare-prev-val">было {shortMoney(data.totals_diff.avg_check.base)}</span>
                <span className={`compare-delta-pill ${data.totals_diff.avg_check.status}`}>
                  {formatDeltaPct(data.totals_diff.avg_check.delta_pct)}
                </span>
              </div>
            </div>
          </section>

          {/* Metrics Dynamics */}
          <section className="compare-metrics-section">
            <div className="compare-section-header">
              <h2>Показатели воронки</h2>
              <span className="compare-section-meta">До ➔ После</span>
            </div>

            <div className="compare-metrics-list">
              {data.metrics_diff.map((item) => (
                <MetricDiffCard key={item.metric_id} item={item} />
              ))}
            </div>
          </section>

          {/* Sales Managers Dynamics */}
          {data.managers_diff && data.managers_diff.length > 0 ? (
            <section className="compare-managers-section">
              <div className="compare-section-header">
                <h2>Динамика менеджеров</h2>
                <span className="compare-section-meta">{data.managers_diff.length} сотр.</span>
              </div>

              <div className="compare-managers-list">
                {data.managers_diff.map((m) => (
                  <div key={m.manager} className="compare-manager-card">
                    <div className="compare-mgr-main">
                      <span className="compare-mgr-name">{m.manager}</span>
                      <span className={`compare-delta-pill ${m.status}`}>
                        {formatDeltaPct(m.delta_pct)}
                      </span>
                    </div>

                    <div className="compare-mgr-stats">
                      <div className="compare-mgr-stat-col">
                        <span className="compare-mgr-stat-label">Текущая выручка</span>
                        <strong className="compare-mgr-stat-val">{formatRub(m.target_amount)}</strong>
                        <span className="compare-mgr-stat-sub">{m.target_deals} сделок</span>
                      </div>
                      <div className="compare-mgr-stat-col align-right">
                        <span className="compare-mgr-stat-label">Базовая выручка</span>
                        <span className="compare-mgr-stat-val-prev">{formatRub(m.base_amount)}</span>
                        <span className="compare-mgr-stat-sub">
                          {m.delta_amount >= 0 ? `+${formatRub(m.delta_amount)}` : formatRub(m.delta_amount)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <div className="compare-actions-bar">
            <Button
              className="action action-accent"
              type="button"
              size="large"
              stretched
              variant="primary"
              onClick={() => onOpenChat?.(data.comparison_id)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true" style={{ width: 18, height: 18, marginRight: 8, fill: 'currentColor' }}>
                <path d="M5 6.5h14v9.5H9.2L5 19.2V6.5Z" />
                <path d="M8.5 10h7M8.5 13h4.5" />
              </svg>
              Разобрать динамику с AI-агентом
            </Button>
          </div>
    </div>
  )
}

function MetricDiffCard({ item }: { item: MetricDiffItem }) {
  const isImproved = item.status === 'positive'
  const isDeclined = item.status === 'negative'

  return (
    <article className={`compare-metric-card ${item.status}`}>
      <div className="compare-metric-head">
        <span className="compare-metric-name">{item.name}</span>
        <span className={`compare-delta-pill ${item.status}`}>
          {formatDeltaPct(item.delta_pct)}
        </span>
      </div>

      <div className="compare-metric-body">
        <div className="compare-metric-flow">
          <span className="compare-metric-val-base">
            {formatMetricVal(item.base_value, item.unit)}
          </span>
          <span className="compare-metric-arrow">➔</span>
          <strong className="compare-metric-val-target">
            {formatMetricVal(item.target_value, item.unit)}
          </strong>
        </div>

        {item.base_impact > 0 || item.target_impact > 0 ? (
          <div className="compare-metric-leakage">
            <span className="compare-leakage-label">Утечка:</span>
            <span className="compare-leakage-vals">
              {formatRub(item.base_impact)} ➔ {formatRub(item.target_impact)}
            </span>
            {item.delta_impact !== 0 ? (
              <span className={`compare-impact-delta ${isImproved ? 'is-good' : isDeclined ? 'is-bad' : ''}`}>
                ({item.delta_impact > 0 ? `+${formatRub(item.delta_impact)}` : formatRub(item.delta_impact)})
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  )
}

function shortMoney(val: number | string): string {
  const num = typeof val === 'number' ? val : Number(val)
  if (!Number.isFinite(num)) return String(val)
  if (num >= 1_000_000) {
    const m = num / 1_000_000
    const str = m >= 10 ? String(Math.round(m)) : m.toFixed(1).replace('.', ',')
    return `${str} млн ₽`
  }
  if (num >= 1000) {
    return `${Math.round(num / 1000)} тыс. ₽`
  }
  return `${Math.round(num)} ₽`
}

function shortDate(iso: string): string {
  if (!iso) return ''
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  const date = match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : new Date(iso)
  if (Number.isNaN(date.getTime())) return formatWhen(iso)
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(date).replace('.', '')
}

function formatDeltaPct(delta: number): string {
  if (delta === 0) return '0%'
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta.toFixed(1)}%`
}

function formatMetricVal(val: number, unit: string): string {
  if (unit === 'pct') return `${val}%`
  if (unit === 'days') return `${val} дн.`
  if (unit === 'hours') return `${val} ч`
  if (unit === 'rub') return formatRub(val)
  if (unit === 'deals') return `${val} сдел.`
  return `${val} ${unit}`.trim()
}
