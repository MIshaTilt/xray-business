import { XRayLogo } from './XRayLogo.tsx'

export type AnalyzePhase = 'mapping' | 'processing' | 'diagnosis'

const COPY: Record<AnalyzePhase, { title: string; line: string }> = {
  mapping: {
    title: 'Разбираем таблицу',
    line: 'Считаем сделки по выбранным колонкам',
  },
  processing: {
    title: 'Считаем показатели',
    line: 'Смотрим суммы, статусы и сроки',
  },
  diagnosis: {
    title: 'Собираем заключение',
    line: 'Готовим экран с диагнозом',
  },
}

export function AnalyzeVeil({ phase }: { phase: AnalyzePhase }) {
  const copy = COPY[phase]
  return (
    <div className="ai-veil" role="status" aria-live="polite">
      <span className="ai-veil-scan" aria-hidden="true" />
      <div className="ai-veil-card">
        <span className="ai-logo" aria-hidden="true">
          <XRayLogo scanning />
        </span>
        <p className="ai-veil-title">{copy.title}</p>
        <p className="ai-veil-line" key={phase}>{copy.line}</p>
      </div>
    </div>
  )
}
