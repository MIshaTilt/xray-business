import { useState, useRef, useEffect, useLayoutEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { marked } from 'marked'
import type { Diagnosis as DiagnosisData } from '../api/types.ts'
import { ToolCallBadge } from './ToolCallBadge.tsx'
import { ChartCard } from '../widgets/ChartCard.tsx'
import { api, authHeaders } from '../api/client.ts'

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

export type PromptSuggestion = {
  label: string
  query: string
}

export function getSuggestedPrompts(diagnosis: DiagnosisData | null): PromptSuggestion[] {
  const suggestions: PromptSuggestion[] = []
  const availableCols = diagnosis?.available_columns || []
  const normCols = availableCols.map((c) => c.toLowerCase())

  // 1. Unmapped / Custom business columns from user file
  const hasCategory = normCols.some(
    (c) => c.includes('категори') || c.includes('category') || c.includes('группа')
  )
  const hasProduct = normCols.some(
    (c) =>
      c.includes('товар') ||
      c.includes('артикул') ||
      c.includes('номенклатур') ||
      c.includes('продукт')
  )
  const hasCity = normCols.some(
    (c) => c.includes('город') || c.includes('city') || c.includes('регион')
  )
  const hasChannel = normCols.some(
    (c) =>
      c.includes('канал') ||
      c.includes('склад') ||
      c.includes('площадк') ||
      c.includes('точка')
  )
  const hasPayment = normCols.some(
    (c) => c.includes('оплат') || c.includes('payment')
  )
  const hasManager = normCols.some(
    (c) =>
      c.includes('менеджер') ||
      c.includes('manager') ||
      c.includes('кто тащит') ||
      c.includes('ответствен')
  )

  if (hasCategory) {
    suggestions.push({
      label: '📦 Выручка по категориям',
      query: 'Сравни выручку и количество заказов по категориям каталога.',
    })
  }
  if (hasProduct) {
    suggestions.push({
      label: '🏆 Топ-5 товаров',
      query: 'Покажи топ-5 самых продаваемых товаров по сумме выручки.',
    })
  }
  if (hasCity) {
    suggestions.push({
      label: '🌍 Срез по городам',
      query: 'В каких городах самый высокий средний чек? Сравни города по выручке.',
    })
  }
  if (hasChannel) {
    suggestions.push({
      label: '🛒 Продажи по каналам',
      query: 'Сравни продажи, количество заказов и выручку по каналам сбыта (складам/площадкам).',
    })
  }
  if (hasPayment) {
    suggestions.push({
      label: '💳 Способы оплаты',
      query: 'Какими способами оплаты чаще всего пользуются и какая выручка по каждому?',
    })
  }

  // 2. Specific threats from audit diagnosis
  const findings = diagnosis?.findings || []
  const stagnationFinding = findings.find((f) => f.metric_id === 'stagnation')
  const discountFinding = findings.find((f) => f.metric_id === 'discount_leakage')
  const speedFinding = findings.find((f) => f.metric_id === 'speed_to_lead')
  const keyAccountFinding = findings.find((f) => f.metric_id === 'key_account_risk')

  if (stagnationFinding) {
    const amtStr = stagnationFinding.money_impact ? ` (${stagnationFinding.money_impact} ₽)` : ''
    suggestions.push({
      label: `⏳ Зависшие сделки${amtStr}`,
      query: 'Покажи зависшие сделки, где застряли деньги, и предложи план действий для РОПа.',
    })
  }
  if (discountFinding) {
    suggestions.push({
      label: '💸 Сделки с макс. скидками',
      query: 'Найди сделки с самыми большими скидками и оцени потери маржи.',
    })
  }
  if (speedFinding) {
    suggestions.push({
      label: '⚡ Задержки первого ответа',
      query: 'Сколько лидов ждут первого ответа дольше нормы и кто из менеджеров отвечает медленнее всех?',
    })
  }
  if (keyAccountFinding) {
    suggestions.push({
      label: '👑 Топ клиентов по выручке',
      query: 'Выведи топ ключевых клиентов по выручке и оцени риск концентрации.',
    })
  }

  // 3. Essential Charts & Team Analytics
  if (hasManager || normCols.length === 0) {
    suggestions.push({
      label: '👥 Эффективность менеджеров',
      query: 'Кто из менеджеров лучший по выручке и закрытым сделкам? Сравни показатели команды.',
    })
  }
  suggestions.push({
    label: '📈 График выручки по дням',
    query: 'Построй интерактивный график динамики выручки по датам.',
  })
  suggestions.push({
    label: '📉 Воронка по этапам',
    query: 'Построй сводную таблицу воронки продаж по этапам сделок и рассчитай конверсию между стадиями.',
  })
  suggestions.push({
    label: '🔍 Самые крупные сделки',
    query: 'Найди топ-5 самых крупных сделок в отчете.',
  })

  // Deduplicate and return up to 7 prompts
  const seen = new Set<string>()
  const result: PromptSuggestion[] = []
  for (const s of suggestions) {
    if (!seen.has(s.label)) {
      seen.add(s.label)
      result.push(s)
      if (result.length >= 7) break
    }
  }
  return result
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

  const suggestedPrompts = useMemo(() => getSuggestedPrompts(diagnosis), [diagnosis])

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
              toolCalls:
                m.tool_calls && m.tool_calls.length > 0
                  ? m.tool_calls.map((t: any) => ({
                      ...t,
                      result:
                        typeof t.result === 'string'
                          ? (() => {
                              try {
                                return JSON.parse(t.result)
                              } catch {
                                return t.result
                              }
                            })()
                          : t.result,
                    }))
                  : undefined,
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

    const standardFields = new Set([
      'deal_id',
      'client',
      'contact',
      'manager',
      'amount',
      'list_price',
      'discount_pct',
      'status',
      'status_raw',
      'created_at',
      'first_contact_at',
      'status_changed_at',
      'last_activity_at',
      'closed_at',
      'source',
    ])
    const customCols = (diagnosis.available_columns || []).filter(
      (c) => c && !standardFields.has(c)
    )
    const customColsSection =
      customCols.length > 0
        ? '\n  ДОПОЛНИТЕЛЬНЫЕ СТОЛБЦЫ ИЗ ИСХОДНОГО ФАЙЛА ПОЛЬЗОВАТЕЛЯ (также доступны в таблице deals!):\n' +
          customCols.map((c) => `  * "${c}"`).join('\n') +
          '\n  Ты можешь обращаться к ним напрямую в SELECT, WHERE, GROUP BY, ORDER BY, заключая их в двойные кавычки (например: SELECT "' +
          customCols[0] +
          '", COUNT(*), SUM(amount) FROM deals GROUP BY "' +
          customCols[0] +
          '").\n' +
          '  Используй эти столбцы для глубокого анализа товаров, категорий, городов, каналов, способов оплаты и любых специфичных для бизнеса метрик!\n'
        : ''

    return (
      'Ты — персональный бизнес-аналитик и консультант по продажам сервиса X-Ray.\n' +
      'Перед тобой результаты рентгена продаж реального бизнеса пользователя:\n\n' +
      `Главный вывод диагноза: "${diagnosis.headline}"\n\n` +
      `Общая статистика:\n` +
      `- Всего сделок: ${diagnosis.totals.deals}\n` +
      `- Общая сумма: ${diagnosis.totals.amount} руб.\n` +
      `- Период: с ${diagnosis.period.from || 'начала'} по ${diagnosis.period.to || 'конец'}\n\n` +
      `Ключевые найденные угрозы и утечки:\n${threatsText}\n\n` +
      'ВАЖНО ОБ ИНСТРУМЕНТАХ (TOOLS) И SQL-АНАЛИТИКЕ:\n' +
      'У тебя есть доступ к базе сделок текущего отчета через инструмент execute_sql_query и к построению интерактивных графиков через render_chart.\n' +
      '- execute_sql_query: ТВОЙ ГЛАВНЫЙ ИНСТРУМЕНТ для получения любых данных. Используй его ВСЕГДА, когда пользователь спрашивает о:\n' +
      '  1. Менеджерах (кто лучше или хуже работает, кто закрывает больше выручки, у кого зависли сделки, средний чек, статистика команды).\n' +
      '     Пример: SELECT manager, COUNT(*) as deals_cnt, SUM(amount) as total_amt, SUM(CASE WHEN status="won" THEN 1 ELSE 0 END) as won_cnt, SUM(CASE WHEN status="lost" THEN 1 ELSE 0 END) as lost_cnt, ROUND(AVG(amount), 2) as avg_check FROM deals WHERE manager != "" GROUP BY manager ORDER BY total_amt DESC\n' +
      '  2. Клиентах и покупателях (топ клиентов по сумме покупок, средний чек, история сделок конкретного контрагента).\n' +
      '     Пример: SELECT client, COUNT(*) as orders_cnt, SUM(amount) as total_amt, ROUND(AVG(amount), 2) as avg_check FROM deals WHERE client != "" GROUP BY client ORDER BY total_amt DESC LIMIT 10\n' +
      '  3. Поиске конкретных сделок (по фильтрам, статусам, суммам, датам, клиентам или менеджерам).\n' +
      '     Пример: SELECT deal_id, client, manager, amount, status, status_raw, created_at FROM deals WHERE amount > 50000 ORDER BY amount DESC LIMIT 15\n' +
      '  4. Анализе этапов и причин отказов (распределение по status_raw, потерянные заказы, каналы source, скидки discount_pct).\n' +
      '  Схема таблицы deals:\n' +
      '  * deal_id (текст): идентификатор сделки / заказа\n' +
      '  * client (текст): имя клиента или название компании\n' +
      '  * contact (текст): телефон / email\n' +
      '  * manager (текст): имя ответственного менеджера\n' +
      '  * amount (число): сумма сделки / выручка в рублях\n' +
      '  * list_price (число): базовая цена без скидки\n' +
      '  * discount_pct (число): скидка в %\n' +
      '  * status (текст): канонический статус ("new", "in_progress", "proposal", "negotiation", "won", "lost", "other")\n' +
      '  * status_raw (текст): исходный статус из CRM / файла пользователя (например, "Доставлен и оплачен", "В обработке")\n' +
      '  * created_at, closed_at, first_contact_at, status_changed_at, last_activity_at (даты/время)\n' +
      '  * source (текст): канал / источник / маркетплейс\n' +
      customColsSection +
      '  Пиши только одиночные SELECT-запросы. Все данные уже изолированы по текущему снимку.\n' +
      '- render_chart: вызывай для визуализации, когда пользователь просит "построй график", "нарисуй диаграмму", "динамику выручки по времени", "сравни менеджеров визуально", "распределение выручки/сделок" или "сделай чарт".\n' +
      '  * Для графиков выручки по времени/датам: chart_type="line", dimension="date" (или "month").\n' +
      '  * Для менеджеров: chart_type="bar", dimension="manager".\n' +
      '  * Для клиентов: chart_type="bar", dimension="client".\n' +
      '  * Ты также можешь передавать произвольно рассчитанные через SQL данные в массив data для render_chart!\n' +
      'ВАЖНО: Для анализа воронки продаж, этапов сделок и конверсий НЕ пытайся строить график-воронку через render_chart. С этой задачей ты отлично справляешься текстом: запрашивай данные через execute_sql_query (GROUP BY status или status_raw) и формируй наглядную, структурированную Markdown-таблицу стадий воронки с числом заказов, выручкой и конверсией между этапами!\n' +
      'Никогда не говори "в отчете нет данных о менеджерах или клиентах" без предварительного выполнения execute_sql_query к таблице deals.\n' +
      'Когда строишь график через render_chart, в тексте своего ответа обязательно прокомментируй полученные на графике данные, динамику, пики и дай практические советы.\n\n' +
      'ПРАВИЛА ОБЩЕНИЯ:\n' +
      '1. Опирайся на конкретные цифры и факты из отчета и SQL-ответов. Не придумывай финансовые показатели.\n' +
      '2. Отвечай кратко, емко, дружелюбно, языком опытного предпринимателя и трекера.\n' +
      '3. Давай практические советы по шагам: что сделать РОПу, менеджерам или владельцу уже сегодня.'
    )
  }

  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? input).trim()
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

    const apiUrl = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

    setActiveToolCalls([])
    const currentTools: ToolCallData[] = []

    try {
      const response = await fetch(`${apiUrl}/api/chat/stream/`, {
        method: 'POST',
        headers: authHeaders(true),
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
          <p className="home-hint chat-scan-label">Рентген продаж</p>
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
                {m.toolCalls.map((tc, tcIdx) =>
                  tc.tool_name === 'render_chart' && tc.result ? (
                    <ChartCard key={tcIdx} chartData={tc.result} toolCall={tc} />
                  ) : (
                    <ToolCallBadge key={tcIdx} toolCall={tc} />
                  )
                )}
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
                {activeToolCalls.map((tc, tcIdx) =>
                  tc.tool_name === 'render_chart' && tc.result ? (
                    <ChartCard key={tcIdx} chartData={tc.result} toolCall={tc} />
                  ) : (
                    <ToolCallBadge key={tcIdx} toolCall={tc} />
                  )
                )}
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
        {!streaming && suggestedPrompts.length > 0 && (
          <div className="chat-suggestions-bar" aria-label="Быстрые вопросы">
            {suggestedPrompts.map((p, idx) => (
              <button
                key={idx}
                type="button"
                className="chat-suggestion-chip"
                onClick={() => void handleSend(p.query)}
                disabled={streaming}
                title={p.query}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}
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
