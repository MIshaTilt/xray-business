import { Button, Typography } from '@maxhub/max-ui'
import { useState, useRef, useEffect } from 'react'
import type { Diagnosis as DiagnosisData } from '../api/types.ts'

export type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
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
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        'Здравствуйте! Я проанализировал ваш бизнес-рентген и готов ответить на любые вопросы по найденным угрозам, зависшим сделкам или рекомендациям.',
    },
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [currentStreamText, setCurrentStreamText] = useState('')
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

    try {
      const response = await fetch(`${apiUrl}/api/chat/stream/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages: payloadMessages }),
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
            if (data.choices && data.choices[0] && data.choices[0].delta) {
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

      setMessages([...newMessages, { role: 'assistant', content: accumulated }])
    } catch (err: any) {
      setMessages([
        ...newMessages,
        { role: 'assistant', content: `Ошибка соединения с AI-ассистентом: ${err.message}` },
      ])
    } finally {
      setCurrentStreamText('')
      setStreaming(false)
    }
  }

  return (
    <div className="stack chat-screen">
      <div className="chat-header">
        <Typography.Title variant="medium-strong">AI-консультант X-Ray</Typography.Title>
        <Typography.Body variant="small" className="chat-subtitle">
          Контекст: снимок {snapshotId.slice(0, 8)}…
        </Typography.Body>
      </div>

      <div className="chat-messages-container">
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-bubble ${m.role}`}>
            <div className="chat-bubble-author">
              {m.role === 'user' ? 'Вы' : 'AI Аналитик'}
            </div>
            <div className="chat-bubble-content">{m.content}</div>
          </div>
        ))}

        {streaming && (
          <div className="chat-bubble assistant">
            <div className="chat-bubble-author">AI Аналитик</div>
            <div className="chat-bubble-content">
              {currentStreamText}
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
