import { Button, Typography } from '@maxhub/max-ui'
import { useState, useRef, useEffect } from 'react'
import { marked } from 'marked'
import type { Diagnosis as DiagnosisData } from '../api/types.ts'
import { ToolCallBadge } from './ToolCallBadge.tsx'
import { api } from '../api/client.ts'

// Configure marked for clean inline rendering with breaks
marked.setOptions({
  breaks: true,
  gfm: true,
})

export type ToolCallData = {
  tool_name: string
  arguments: any
  result: any
}

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: ToolCallData[]
}

export function ChatScreen({
  snapshotId,
  diagnosis,
  onBack: _onBack,
}: {
  snapshotId: string
  diagnosis: DiagnosisData | null
  onBack: () => void
}) {
  const storageKey = `xray_chat_history_${snapshotId}`

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Здравствуйте! Я проанализировал ваш бизнес-рентген и готов ответить на любые вопросы по найденным угрозам, зависшим сделкам или рекомендациям.',
    },
  ])

  // Load chat history from backend database (with fallback to localStorage)
  useEffect(() => {
    let ignore = false
    async function loadHistory() {
      try {
        const dbMsgs = await api.getChatHistory(snapshotId)
        if (!ignore && dbMsgs && dbMsgs.length > 0) {
          setMessages(
            dbMsgs.map((m: any) => ({
              role: m.role,
              content: m.content,
              toolCalls: m.tool_calls && m.tool_calls.length > 0 ? m.tool_calls : undefined,
            }))
          )
          return
        }
      } catch {
        // DB load failed, check local storage
      }

      try {
        const saved = localStorage.getItem(storageKey)
        if (!ignore && saved) {
          const parsed = JSON.parse(saved)
          if (Array.isArray(parsed) && parsed.length > 0) setMessages(parsed)
        }
      } catch {
        // ignore
      }
    }

    void loadHistory()
    return () => {
      ignore = true
    }
  }, [snapshotId, storageKey])

  // Also cache in localStorage for fast local re-render
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(messages))
    } catch {
      // ignore
    }
  }, [messages, storageKey])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [currentStreamText, setCurrentStreamText] = useState('')
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCallData[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentStreamText])

  // Build rich system prompt with diagnosis context
  function buildSystemPrompt(): string {
    if (!diagnosis) {
      return (
        'Ты — экспертный бизнес-аналитик сервиса X-Ray. ' +
        'Помогай предпринимателю разобраться в проблемах продаж и оптимизировать бизнес-процессы.'
      )
    }

    const threatsText = diagnosis.findings
      .map(
        (f, idx) =>
          `${idx + 1}. [${f.verdict.toUpperCase()}] ${f.metric_id}: ${f.action} ` +
          `(Деньги под угрозой: ${f.money_impact ? f.money_impact + ' ₽' : 'не применимо'}, ` +
          `порог: ${f.threshold_label})`
      )
      .join('\n')

    return (
      'Ты — персональный бизнес-аналитик и консультант по продажам сервиса X-Ray.\n' +
      'Перед тобой результаты рентгена продаж реального бизнеса пользователя:\n\n' +
      `Главный вывод диагноза: "${diagnosis.headline}"\n\n` +
      `Общая статистика:\n` +
      `- Всего сделок: ${diagnosis.totals.deals}\n` +
      `- Общая сумма: ${diagnosis.totals.amount} ₽\n` +
      `- Период: с ${diagnosis.period.from || 'начала'} по ${diagnosis.period.to || 'конец'}\n\n` +
      `Ключевые найденные угрозы и утечки:\n${threatsText}\n\n` +
      'ВАЖНО О ДОСТУПЕ К ДАННЫМ:\n' +
      'У тебя есть доступ к базе сделок через инструменты (tools): search_deals, get_manager_stats, get_top_clients.\n' +
      'Если пользователь спрашивает о конкретных сделках, клиентах, менеджерах или о том, кто косячит — ОБЯЗАТЕЛЬНО вызывай соответствующий инструмент, получай реальные имена и цифры и отвечай с опорой на них!\n' +
      'Никогда не отвечай "в отчете нет имен менеджеров", так как все имена и сделки доступны через вызовы инструментов.\n\n' +
      'ПРАВИЛА ОБЩЕНИЯ:\n' +
      '1. Опирайся на эти конкретные цифры и факты из отчета. Не придумывай новые финансовые показатели.\n' +
      '2. Отвечай кратко, емко, дружелюбно, языком опытного предпринимателя и трекера.\n' +
      '3. Давай практические советы по шагам: что сделать РОПу, менеджерам или владельцу уже сегодня.'
    )
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || streaming) return

    const newMessages: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setMessages(newMessages)
    setInput('')
    setStreaming(true)
    setCurrentStreamText('')

    // Payload includes system prompt + all past messages
    const payloadMessages = [
      { role: 'system', content: buildSystemPrompt() },
      ...newMessages.map((m) => ({ role: m.role, content: m.content })),
    ]

    const apiUrl = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

    setActiveToolCalls([])
    const currentTools: ToolCallData[] = []

    try {
      const response = await fetch(`${apiUrl}/api/chat/stream/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          snapshot_id: snapshotId,
          messages: payloadMessages,
        }),
      })

      if (!response.ok) {
        throw new Error(`Ошибка сервера: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('ReadableStream не поддерживается')

      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      let accumulated = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data:')) continue

          const payloadStr = trimmed.replace(/^data:\s*/, '')
          if (payloadStr === '[DONE]') break

          try {
            const data = JSON.parse(payloadStr)
            if (data.type === 'tool_call') {
              const tc: ToolCallData = {
                tool_name: data.tool_name,
                arguments: data.arguments,
                result: typeof data.result === 'string' ? JSON.parse(data.result) : data.result,
              }
              currentTools.push(tc)
              setActiveToolCalls([...currentTools])
            } else if (data.choices && data.choices[0] && data.choices[0].delta) {
              const chunk = data.choices[0].delta.content || ''
              accumulated += chunk
              setCurrentStreamText(accumulated)
            } else if (data.error) {
              accumulated += `\n[Ошибка: ${data.error}]`
              setCurrentStreamText(accumulated)
            }
          } catch (e) {
            // partial chunk ignored
          }
        }
      }

      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: accumulated,
          toolCalls: currentTools.length > 0 ? currentTools : undefined,
        },
      ])
    } catch (err: any) {
      setMessages([
        ...newMessages,
        { role: 'assistant', content: `Ошибка соединения с AI-ассистентом: ${err.message}` },
      ])
    } finally {
      setCurrentStreamText('')
      setActiveToolCalls([])
      setStreaming(false)
    }
  }

  return (
    <div className="stack chat-screen">
      <div className="chat-header">
        <Typography.Title variant="medium-strong">AI-консультант X-Ray</Typography.Title>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography.Body variant="small" className="chat-subtitle">
            Контекст: снимок {snapshotId.slice(0, 8)}…
          </Typography.Body>
          {messages.length > 1 && (
            <button
              type="button"
              className="chat-clear-btn"
              onClick={() => {
                const initMsg: ChatMessage[] = [
                  {
                    role: 'assistant',
                    content: 'История очищена. О чем хотите спросить по данному отчету?',
                  },
                ]
                setMessages(initMsg)
                localStorage.removeItem(storageKey)
                void api.clearChatHistory(snapshotId)
              }}
            >
              Очистить историю
            </button>
          )}
        </div>
      </div>

      <div className="chat-messages-container">
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-bubble ${m.role}`}>
            <div className="chat-bubble-author">
              {m.role === 'user' ? 'Вы' : 'AI Аналитик'}
            </div>

            {m.toolCalls && m.toolCalls.length > 0 && (
              <div className="chat-tool-calls-list">
                {m.toolCalls.map((tc, tcIdx) => (
                  <ToolCallBadge key={tcIdx} toolCall={tc} />
                ))}
              </div>
            )}

            {m.role === 'assistant' ? (
              <div
                className="chat-bubble-content markdown-body"
                dangerouslySetInnerHTML={{ __html: marked.parse(m.content) as string }}
              />
            ) : (
              <div className="chat-bubble-content">{m.content}</div>
            )}
          </div>
        ))}

        {streaming && (
          <div className="chat-bubble assistant">
            <div className="chat-bubble-author">AI Аналитик</div>

            {activeToolCalls.length > 0 && (
              <div className="chat-tool-calls-list">
                {activeToolCalls.map((tc, tcIdx) => (
                  <ToolCallBadge key={tcIdx} toolCall={tc} />
                ))}
              </div>
            )}

            <div className="chat-bubble-content markdown-body">
              <span
                dangerouslySetInnerHTML={{
                  __html: marked.parse(currentStreamText) as string,
                }}
              />
              <span className="cursor" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-row">
        <textarea
          className="chat-textarea"
          rows={2}
          placeholder="Спросите о зависших сделках, скидках или что делать первым..."
          value={input}
          disabled={streaming}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void handleSend()
            }
          }}
        />
        <Button
          type="button"
          variant="primary"
          size="medium"
          disabled={!input.trim() || streaming}
          onClick={() => void handleSend()}
        >
          {streaming ? '...' : 'Отправить'}
        </Button>
      </div>
    </div>
  )
}
