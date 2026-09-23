import { XRayLogo } from './XRayLogo.tsx'

export function AnalyzeVeil({ step }: { step: number }) {
  const lines = ['Сверяем суммы и сроки', 'Ищем зависшие сделки', 'Собираем диагноз']
  return (
    <div className="ai-veil" role="status" aria-live="polite">
      <div className="ai-veil-card">
        <span className="ai-logo" aria-hidden="true">
          <XRayLogo scanning />
        </span>
        <p className="ai-veil-kicker">X-Ray</p>
        <p className="ai-veil-title">ИИ анализирует базу данных</p>
        <p className="ai-veil-line" key={step}>{lines[step % lines.length]}</p>
      </div>
    </div>
  )
}
