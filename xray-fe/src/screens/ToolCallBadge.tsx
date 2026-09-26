import { useRef, useState } from 'react'
import type { ToolCallData } from './ChatScreen.tsx'

export function ToolCallBadge({ toolCall }: { toolCall: ToolCallData }) {
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const closeTimer = useRef(0)

  const toolLabels: Record<string, string> = {
    search_deals: 'Поиск сделок в базе',
    get_manager_stats: 'Анализ работы менеджеров',
    get_top_clients: 'Выборка ключевых клиентов',
    render_chart: 'Построение интерактивного графика',
  }

  const label = toolLabels[toolCall.tool_name] || toolCall.tool_name

  return (
    <div className="tool-call-container">
      <button
        type="button"
        className={`tool-call-header ${open && !closing ? 'open' : ''}`}
        onClick={() => {
          if (closing) return
          if (!open) {
            setOpen(true)
            return
          }
          if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            setOpen(false)
            return
          }
          setClosing(true)
          window.clearTimeout(closeTimer.current)
          closeTimer.current = window.setTimeout(() => {
            setOpen(false)
            setClosing(false)
          }, 360)
        }}
      >
        <span className="tool-call-icon">⚙️</span>
        <span className="tool-call-title">Запрос к базе: {label}</span>
        <span className={`tool-call-chevron ${open && !closing ? 'rotated' : ''}`}>▼</span>
      </button>

      {open && (
        <div className={`tool-call-body${closing ? ' is-closing' : ''}`}>
          <div className="tool-call-section">
            <span className="tool-call-section-title">Параметры запроса:</span>
            <pre className="tool-call-code">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          <div className="tool-call-section">
            <span className="tool-call-section-title">Данные из базы:</span>
            <pre className="tool-call-code">
              {JSON.stringify(toolCall.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
