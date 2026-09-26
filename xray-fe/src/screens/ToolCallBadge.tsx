import { useRef, useState } from 'react'
import type { ToolCallData } from './ChatScreen.tsx'

export function ToolCallBadge({ toolCall }: { toolCall: ToolCallData }) {
  const [open, setOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const closeTimer = useRef(0)

  const toolLabels: Record<string, string> = {
    execute_sql_query: 'SQL-запрос к базе сделок',
    search_deals: 'Поиск сделок в базе',
    get_manager_stats: 'Анализ работы менеджеров',
    get_top_clients: 'Выборка ключевых клиентов',
    render_chart: 'Построение интерактивного графика',
  }

  const toolIcons: Record<string, string> = {
    execute_sql_query: '🗄️',
    render_chart: '📊',
    get_manager_stats: '👥',
    get_top_clients: '💎',
    search_deals: '🔍',
  }

  const label = toolLabels[toolCall.tool_name] || toolCall.tool_name
  const icon = toolIcons[toolCall.tool_name] || '⚙️'

  const parsedResult =
    typeof toolCall.result === 'string'
      ? (() => {
          try {
            return JSON.parse(toolCall.result)
          } catch {
            return toolCall.result
          }
        })()
      : toolCall.result

  const isSqlQuery = toolCall.tool_name === 'execute_sql_query'
  const sqlQueryText =
    toolCall.arguments?.query ||
    (parsedResult && typeof parsedResult === 'object' ? parsedResult.query : '')

  const hasColumnsAndRows =
    parsedResult &&
    typeof parsedResult === 'object' &&
    Array.isArray(parsedResult.columns) &&
    Array.isArray(parsedResult.rows)

  const sqlError = parsedResult && typeof parsedResult === 'object' ? parsedResult.error : null

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
        <span className="tool-call-icon">{icon}</span>
        <span className="tool-call-title">
          {isSqlQuery ? `SQL: ${sqlQueryText ? (sqlQueryText.length > 45 ? sqlQueryText.slice(0, 45) + '…' : sqlQueryText) : label}` : `Запрос к базе: ${label}`}
        </span>
        <span className={`tool-call-chevron ${open && !closing ? 'rotated' : ''}`}>▼</span>
      </button>

      {open && (
        <div className={`tool-call-body${closing ? ' is-closing' : ''}`}>
          {isSqlQuery ? (
            <>
              {sqlQueryText && (
                <div className="tool-call-section">
                  <span className="tool-call-section-title">SQL-запрос:</span>
                  <pre className="tool-call-code sql-query-code">{sqlQueryText}</pre>
                </div>
              )}

              {sqlError ? (
                <div className="tool-call-section">
                  <span className="tool-call-section-title is-error">Ошибка запроса:</span>
                  <div className="tool-sql-error">{sqlError}</div>
                </div>
              ) : hasColumnsAndRows ? (
                <div className="tool-call-section">
                  <div className="tool-sql-meta-header">
                    <span className="tool-call-section-title">
                      Результат ({parsedResult.rows.length} строк
                      {parsedResult.truncated ? ', показаны первые 50' : ''}):
                    </span>
                  </div>
                  {parsedResult.rows.length === 0 ? (
                    <div className="tool-sql-empty">0 строк найдено</div>
                  ) : (
                    <div className="tool-sql-table-wrap">
                      <table className="tool-sql-table">
                        <thead>
                          <tr>
                            {parsedResult.columns.map((c: string) => (
                              <th key={c}>{c}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {parsedResult.rows.map((row: any, rIdx: number) => (
                            <tr key={rIdx}>
                              {parsedResult.columns.map((col: string) => (
                                <td key={col}>
                                  {row[col] !== null && row[col] !== undefined
                                    ? String(row[col])
                                    : '—'}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : (
                <div className="tool-call-section">
                  <span className="tool-call-section-title">Данные из базы:</span>
                  <pre className="tool-call-code">
                    {JSON.stringify(parsedResult, null, 2)}
                  </pre>
                </div>
              )}
            </>
          ) : (
            <>
              <div className="tool-call-section">
                <span className="tool-call-section-title">Параметры запроса:</span>
                <pre className="tool-call-code">
                  {JSON.stringify(toolCall.arguments, null, 2)}
                </pre>
              </div>

              <div className="tool-call-section">
                <span className="tool-call-section-title">Данные из базы:</span>
                <pre className="tool-call-code">
                  {JSON.stringify(parsedResult, null, 2)}
                </pre>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

