import { useEffect, useState } from 'react'
import { XRayLogo } from './XRayLogo.tsx'

export type AnalyzePhase = 'mapping' | 'processing' | 'diagnosis'

const TITLES: Record<AnalyzePhase, string> = {
  mapping: 'Разбор таблицы',
  processing: 'Подсчёт показателей',
  diagnosis: 'Формирование заключения',
}

const LINES = [
  'Сверка сумм и сроков',
  'Поиск зависших сделок',
  'Сбор диагноза',
  'Подсчёт сделок по выбранным колонкам',
  'Просмотр сумм, статусов и сроков',
]

export function AnalyzeVeil({ phase, leaving = false }: { phase: AnalyzePhase; leaving?: boolean }) {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = window.setInterval(() => {
      setTick((value) => value + 1)
    }, 1000)
    return () => window.clearInterval(id)
  }, [])

  const line = LINES[tick % LINES.length]
  return (
    <div className={`ai-veil${leaving ? ' is-leaving' : ''}`} role="status" aria-live="polite">
      <span className="ai-veil-scan" aria-hidden="true" />
      <div className="ai-veil-card">
        <span className="ai-logo" aria-hidden="true">
          <XRayLogo scanning />
        </span>
        <p className="ai-veil-title">{TITLES[phase]}</p>
        <p className="ai-veil-line" key={line}>{line}</p>
      </div>
    </div>
  )
}
