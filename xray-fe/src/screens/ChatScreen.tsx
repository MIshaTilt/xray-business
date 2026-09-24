import { useState, useRef, useEffect, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
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
  const [clearing, setClearing] = useState(false)
  const [sweeping, setSweeping] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const areaRef = useRef<HTMLTextAreaElement>(null)
  const clearTimer = useRef(0)
  const sweepTimer = useRef(0)
  const [navSlot, setNavSlot] = useState<HTMLElement | null>(null)

  useLayoutEffect(() => {
    setNavSlot(document.getElementById('chat-nav-actions'))
  }, [])

  const syncListOverflow = () => {
    const box = listRef.current
    if (!box) return
    const canScroll = box.scrollHeight > box.clientHeight + 1
    box.classList.toggle('is-scrollable', canScroll)
    if (canScroll) box.scrollTop = box.scrollHeight
  }

  useLayoutEffect(() => {
    window.scrollTo(0, 0)
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
    syncListOverflow()
  }, [messages, currentStreamText, clearing])

  useEffect(() => {
    const box = listRef.current
    const ro = box ? new ResizeObserver(syncListOverflow) : null
    if (box && ro) ro.observe(box)

    const allowInnerScroll = (target: EventTarget | null, node: HTMLElement | null) => {
      if (!node || !target || !(target instanceof Node) || !node.contains(target)) return false
      return node.scrollHeight > node.clientHeight + 1
    }

    const blockPageScroll = (event: Event) => {
      if (allowInnerScroll(event.target, listRef.current)) return
      if (allowInnerScroll(event.target, areaRef.current)) return
      event.preventDefault()
    }

    document.addEventListener('touchmove', blockPageScroll, { passive: false })
    document.addEventListener('wheel', blockPageScroll, { passive: false })
    return () => {
      ro?.disconnect()
      document.removeEventListener('touchmove', blockPageScroll)
      document.removeEventListener('wheel', blockPageScroll)
    }
  }, [])

  useLayoutEffect(() => {
    const node = areaRef.current
    if (!node) return
    node.style.height = 'auto'
    const cap = window.matchMedia('(min-width: 960px)').matches ? 160 : 200
    const next = Math.min(node.scrollHeight, cap)
    node.style.height = `${next}px`
    node.style.overflowY = node.scrollHeight > cap ? 'auto' : 'hidden'
  }, [input])

  useEffect(
    () => () => {
      window.clearTimeout(clearTimer.current)
      window.clearTimeout(sweepTimer.current)
    },
    [],
  )

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
          `(Деньги под угрозой: ${f.money_impact ? f.money_impact + ' руб.' : 'не применимо'}, ` +
          `порог: ${f.threshold_label})`
      )
      .join('\n')

    return (
      'Ты — персональный бизнес-аналитик и консультант по продажам сервиса X-Ray.\n' +
      'Перед тобой результаты рентгена продаж реального бизнеса пользователя:\n\n' +
      `Главный вывод диагноза: "${diagnosis.headline}"\n\n` +
      `Общая статистика:\n` +
      `- Всего сделок: ${diagnosis.totals.deals}\n` +
      `- Общая сумма: ${diagnosis.totals.amount} руб.\n` +
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

  const canClear = messages.length > 1 && !clearing
  const showClear = canClear || sweeping

  function handleClear() {
    if (!canClear) return
    const reset = () => {
      setMessages([])
      setClearing(false)
      localStorage.removeItem(storageKey)
      void api.clearChatHistory(snapshotId)
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      reset()
      return
    }
    setSweeping(true)
    setClearing(true)
    window.clearTimeout(clearTimer.current)
    window.clearTimeout(sweepTimer.current)
    clearTimer.current = window.setTimeout(reset, 420)
    sweepTimer.current = window.setTimeout(() => setSweeping(false), 780)
  }

  const clearIcon = (
    <button
      type="button"
      className={`chat-clear-nav${showClear ? ' is-on' : ''}${sweeping ? ' is-sweeping' : ''}`}
      aria-label="Очистить историю"
      tabIndex={canClear ? 0 : -1}
      onClick={handleClear}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <g transform="rotate(-20 12 14)">
          <path d="M12 3.4v9.8" />
          <path d="M5.2 13.2h13.6v3.4H5.2z" />
          <path d="M6.4 16.6v4.2" />
          <path d="M9.2 16.6v4.2" />
          <path d="M12 16.6v4.2" />
          <path d="M14.8 16.6v4.2" />
          <path d="M17.6 16.6v4.2" />
        </g>
      </svg>
    </button>
  )

  return (
    <div className="stack chat-screen">
      {navSlot ? createPortal(clearIcon, navSlot) : null}
      {streaming ? <span className="chat-scan" aria-hidden="true" /> : null}
      <div className="chat-header">
        <div className="lead">
          <h1>Консультант</h1>
          <p className="home-hint chat-scan-label">
            {diagnosis?.scan_no
              ? `Снимок №${diagnosis.scan_no}`
              : 'Снимок'}
          </p>
        </div>
        <div className="chat-clear-slot">
          <button
            type="button"
            className={`chat-clear-btn${canClear ? ' is-on' : ''}`}
            tabIndex={canClear ? 0 : -1}
            onClick={handleClear}
          >
            Очистить историю
          </button>
        </div>
      </div>

      <div ref={listRef} className={`chat-messages-container${clearing ? ' is-clearing' : ''}`}>
        {messages.length === 0 && !streaming && !clearing ? (
          <div className="chat-empty">
            <span className="chat-empty-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2z" />
                <path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1" />
              </svg>
            </span>
            <p className="chat-empty-title">История очищена</p>
            <p className="chat-empty-hint">Напишите сообщение, чтобы начать консультацию</p>
          </div>
        ) : null}
        {messages.map((m, idx) => (
          <div key={`${m.role}-${idx}-${m.content.slice(0, 24)}`} className={`chat-bubble ${m.role}`}>
            {m.role === 'assistant' ? (
              <div className="chat-bubble-author">Консультант</div>
            ) : null}

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
          <div className="chat-bubble assistant chat-bubble-live">
            <div className="chat-bubble-author">Консультант</div>

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
      </div>

      <div className={`chat-input-row${input.trim() ? ' has-text' : ''}`}>
        <div className="chat-composer">
          <textarea
            ref={areaRef}
            className="chat-textarea"
            rows={1}
            placeholder="Напишите вопрос"
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
          <button
            type="button"
            className="chat-send"
            aria-label="Отправить"
            disabled={!input.trim() || streaming}
            onClick={() => void handleSend()}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M22 2 11 13" />
              <path d="M22 2 15 22 11 13 2 9 22 2Z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
