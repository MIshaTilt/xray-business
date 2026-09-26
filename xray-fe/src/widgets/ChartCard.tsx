import { useState } from 'react'

export interface ChartItem {
  label: string
  value: number
  amount?: number
  count?: number
  avg_check?: number
  won_count?: number
  formatted_value: string
  color: string
  hint?: string
  percentage: number
  stage_key?: string
}

export interface ChartData {
  chart_type: 'bar' | 'donut' | 'pie' | 'funnel' | 'line'
  title: string
  dimension?: string
  metric?: string
  metric_label?: string
  unit?: string
  total?: number
  formatted_total?: string
  items: ChartItem[]
  summary?: string
}

export function ChartCard({
  chartData,
  toolCall: _toolCall,
}: {
  chartData: ChartData | string
  toolCall?: any
}) {
  const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart')
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
  const [showRaw, setShowRaw] = useState(false)

  // Safely parse data if passed as JSON string
  let parsed: ChartData | null = null
  try {
    if (typeof chartData === 'string') {
      parsed = JSON.parse(chartData)
    } else {
      parsed = chartData
    }
  } catch {
    parsed = null
  }

  if (!parsed || !parsed.items || parsed.items.length === 0) {
    return (
      <div className="chart-card chart-card-empty">
        <div className="chart-card-header">
          <span className="chart-card-icon">📊</span>
          <span className="chart-card-title">{parsed?.title || 'График данных'}</span>
        </div>
        <div className="chart-card-body">
          <p className="chart-empty-text">Нет данных для отображения графика</p>
        </div>
      </div>
    )
  }

  const { title, chart_type, formatted_total, items } = parsed
  const effectiveType = chart_type === 'pie' ? 'donut' : chart_type

  const icon =
    effectiveType === 'donut'
      ? '🍩'
      : effectiveType === 'funnel'
        ? '🔻'
        : effectiveType === 'line'
          ? '📈'
          : '📊'

  const maxVal = Math.max(...items.map((i) => i.value), 1)

  return (
    <div className="chart-card">
      <div className="chart-card-header">
        <div className="chart-header-left">
          <span className="chart-card-icon">{icon}</span>
          <div className="chart-header-titles">
            <h4 className="chart-card-title">{title}</h4>
            {formatted_total ? (
              <span className="chart-card-total">Всего: {formatted_total}</span>
            ) : null}
          </div>
        </div>

        <div className="chart-header-actions">
          <button
            type="button"
            className={`chart-mode-btn ${viewMode === 'chart' ? 'active' : ''}`}
            onClick={() => setViewMode('chart')}
            title="График"
          >
            График
          </button>
          <button
            type="button"
            className={`chart-mode-btn ${viewMode === 'table' ? 'active' : ''}`}
            onClick={() => setViewMode('table')}
            title="Таблица данных"
          >
            Таблица
          </button>
          <button
            type="button"
            className={`chart-raw-btn ${showRaw ? 'active' : ''}`}
            onClick={() => setShowRaw(!showRaw)}
            title="Показать JSON"
          >
            {'{ }'}
          </button>
        </div>
      </div>

      {showRaw ? (
        <pre className="chart-raw-json">{JSON.stringify(parsed, null, 2)}</pre>
      ) : null}

      <div className="chart-card-body">
        {viewMode === 'table' ? (
          <div className="chart-table-wrapper">
            <table className="chart-mini-table">
              <thead>
                <tr>
                  <th>Позиция</th>
                  <th className="align-right">Значение</th>
                  <th className="align-right">Доля</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => (
                  <tr key={idx}>
                    <td className="chart-table-label-cell">
                      <span
                        className="chart-color-bullet"
                        style={{ backgroundColor: item.color }}
                      />
                      <span>{item.label}</span>
                    </td>
                    <td className="align-right font-mono">{item.formatted_value}</td>
                    <td className="align-right font-mono font-bold">{item.percentage}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : effectiveType === 'donut' ? (
          <DonutChartWidget
            items={items}
            totalFormatted={formatted_total}
            hoveredIdx={hoveredIdx}
            setHoveredIdx={setHoveredIdx}
          />
        ) : effectiveType === 'funnel' ? (
          <FunnelChartWidget items={items} />
        ) : effectiveType === 'line' ? (
          <LineChartWidget
            items={items}
            hoveredIdx={hoveredIdx}
            setHoveredIdx={setHoveredIdx}
          />
        ) : (
          <BarChartWidget
            items={items}
            maxVal={maxVal}
            hoveredIdx={hoveredIdx}
            setHoveredIdx={setHoveredIdx}
          />
        )}
      </div>
    </div>
  )
}

function BarChartWidget({
  items,
  maxVal,
  hoveredIdx,
  setHoveredIdx,
}: {
  items: ChartItem[]
  maxVal: number
  hoveredIdx: number | null
  setHoveredIdx: (idx: number | null) => void
}) {
  return (
    <div className="chart-bar-list">
      {items.map((item, idx) => {
        const barWidth = Math.max(Math.min((item.value / maxVal) * 100, 100), 2)
        const isHovered = hoveredIdx === idx

        return (
          <div
            key={idx}
            className={`chart-bar-item ${isHovered ? 'hovered' : ''}`}
            onMouseEnter={() => setHoveredIdx(idx)}
            onMouseLeave={() => setHoveredIdx(null)}
          >
            <div className="chart-bar-meta">
              <span className="chart-bar-label" title={item.label}>
                <span
                  className="chart-color-dot"
                  style={{ backgroundColor: item.color }}
                />
                {item.label}
              </span>
              <div className="chart-bar-numbers">
                <span className="chart-bar-val">{item.formatted_value}</span>
                <span className="chart-bar-pct">{item.percentage}%</span>
              </div>
            </div>

            <div className="chart-bar-track">
              <div
                className="chart-bar-fill"
                style={{
                  width: `${barWidth}%`,
                  backgroundColor: item.color,
                }}
              />
            </div>

            {item.hint ? (
              <span className="chart-bar-hint">{item.hint}</span>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function DonutChartWidget({
  items,
  totalFormatted,
  hoveredIdx,
  setHoveredIdx,
}: {
  items: ChartItem[]
  totalFormatted?: string
  hoveredIdx: number | null
  setHoveredIdx: (idx: number | null) => void
}) {
  const radius = 40
  const circumference = 2 * Math.PI * radius // ~251.327

  let accumulated = 0
  const slices = items.map((item) => {
    const strokeLength = (item.percentage / 100) * circumference
    const offset = accumulated
    accumulated += strokeLength
    return {
      ...item,
      strokeLength,
      offset,
    }
  })

  const activeItem = hoveredIdx !== null ? items[hoveredIdx] : null

  return (
    <div className="chart-donut-layout">
      <div className="chart-donut-visual">
        <svg viewBox="0 0 100 100" className="chart-donut-svg">
          {slices.map((slice, idx) => {
            const isHovered = hoveredIdx === idx
            return (
              <circle
                key={idx}
                cx="50"
                cy="50"
                r={radius}
                fill="none"
                stroke={slice.color}
                strokeWidth={isHovered ? 17 : 14}
                strokeDasharray={`${slice.strokeLength} ${circumference}`}
                strokeDashoffset={-slice.offset}
                transform="rotate(-90 50 50)"
                className="chart-donut-slice"
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
              />
            )
          })}
        </svg>

        <div className="chart-donut-center">
          {activeItem ? (
            <>
              <span className="chart-center-sub" title={activeItem.label}>
                {activeItem.label}
              </span>
              <span className="chart-center-val">{activeItem.formatted_value}</span>
              <span className="chart-center-pct">{activeItem.percentage}%</span>
            </>
          ) : (
            <>
              <span className="chart-center-sub">Всего</span>
              <span className="chart-center-val">{totalFormatted || '100%'}</span>
            </>
          )}
        </div>
      </div>

      <div className="chart-donut-legend">
        {items.map((item, idx) => {
          const isHovered = hoveredIdx === idx
          return (
            <div
              key={idx}
              className={`chart-legend-row ${isHovered ? 'hovered' : ''}`}
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <span
                className="chart-color-dot"
                style={{ backgroundColor: item.color }}
              />
              <span className="chart-legend-label" title={item.label}>
                {item.label}
              </span>
              <span className="chart-legend-val">{item.formatted_value}</span>
              <span className="chart-legend-pct">{item.percentage}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function FunnelChartWidget({ items }: { items: ChartItem[] }) {
  const maxVal = Math.max(...items.map((i) => i.value), 1)

  return (
    <div className="chart-funnel-list">
      {items.map((item, idx) => {
        const prevItem = idx > 0 ? items[idx - 1] : null
        const convPct =
          prevItem && prevItem.value > 0
            ? Math.round((item.value / prevItem.value) * 100)
            : null

        const barWidth = Math.max(Math.min((item.value / maxVal) * 100, 100), 28)

        return (
          <div key={idx} className="chart-funnel-stage">
            {convPct !== null ? (
              <div className="chart-funnel-conv">
                <span className="chart-conv-line" />
                <span className="chart-conv-badge">↓ {convPct}% конверсия</span>
                <span className="chart-conv-line" />
              </div>
            ) : null}

            <div
              className="chart-funnel-bar"
              style={{
                width: `${barWidth}%`,
                borderLeftColor: item.color,
              }}
            >
              <div className="chart-funnel-bar-left">
                <span
                  className="chart-color-dot"
                  style={{ backgroundColor: item.color }}
                />
                <span className="chart-funnel-label">{item.label}</span>
              </div>
              <div className="chart-funnel-bar-right">
                <span className="chart-funnel-val">{item.formatted_value}</span>
                {item.count ? (
                  <span className="chart-funnel-cnt">{item.count} сделок</span>
                ) : null}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function LineChartWidget({
  items,
  hoveredIdx,
  setHoveredIdx,
}: {
  items: ChartItem[]
  hoveredIdx: number | null
  setHoveredIdx: (idx: number | null) => void
}) {
  const maxVal = Math.max(...items.map((i) => i.value), 1)
  const minVal = Math.min(...items.map((i) => i.value), 0)
  const range = maxVal - minVal || 1

  const width = 460
  const height = 150
  const padX = 40
  const padY = 24
  const chartW = width - padX * 2
  const chartH = height - padY * 2

  const pts = items.map((it, idx) => {
    const x = padX + (items.length > 1 ? (idx / (items.length - 1)) * chartW : chartW / 2)
    const y = padY + chartH - ((it.value - minVal) / range) * chartH
    return { x, y, ...it }
  })

  const pathD = pts.reduce(
    (acc, pt, idx) => (idx === 0 ? `M ${pt.x},${pt.y}` : `${acc} L ${pt.x},${pt.y}`),
    ''
  )

  const areaD =
    pts.length > 0
      ? `${pathD} L ${pts[pts.length - 1].x},${padY + chartH} L ${pts[0].x},${padY + chartH} Z`
      : ''

  const activePt = hoveredIdx !== null ? pts[hoveredIdx] : null

  return (
    <div className="chart-line-wrapper">
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-line-svg">
        <defs>
          <linearGradient id="chartLineGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.32" />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        <line
          x1={padX}
          y1={padY}
          x2={width - padX}
          y2={padY}
          className="chart-grid-line"
        />
        <line
          x1={padX}
          y1={padY + chartH / 2}
          x2={width - padX}
          y2={padY + chartH / 2}
          className="chart-grid-line"
        />
        <line
          x1={padX}
          y1={padY + chartH}
          x2={width - padX}
          y2={padY + chartH}
          className="chart-grid-line"
        />

        {/* Fill Area & Line */}
        <path d={areaD} fill="url(#chartLineGrad)" />
        <path
          d={pathD}
          fill="none"
          stroke="#3B82F6"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {pts.map((pt, idx) => {
          const isHovered = hoveredIdx === idx
          return (
            <g
              key={idx}
              className="chart-line-pt-group"
              onMouseEnter={() => setHoveredIdx(idx)}
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <circle
                cx={pt.x}
                cy={pt.y}
                r={isHovered ? 6 : 4}
                fill={pt.color || '#3B82F6'}
                stroke="#fff"
                strokeWidth="2"
                className="chart-line-dot"
              />
            </g>
          )
        })}
      </svg>

      {/* Hover tooltip */}
      {activePt ? (
        <div
          className="chart-line-tooltip"
          style={{
            left: `${(activePt.x / width) * 100}%`,
            top: `${(activePt.y / height) * 100}%`,
          }}
        >
          <span className="tooltip-title">{activePt.label}</span>
          <span className="tooltip-val">{activePt.formatted_value}</span>
        </div>
      ) : null}

      <div className="chart-line-labels">
        {items.map((it, idx) => (
          <span
            key={idx}
            className={`chart-line-lbl ${hoveredIdx === idx ? 'hovered' : ''}`}
            title={it.label}
          >
            {it.label}
          </span>
        ))}
      </div>
    </div>
  )
}
