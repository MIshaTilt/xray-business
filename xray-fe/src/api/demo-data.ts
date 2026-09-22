import type { Coverage, EvidenceDeal, Finding, MetricId } from './types.ts'

const CLIENTS = [
  'Офис на Садовой', 'Студия «Лампа»', 'Школа №12', 'Барбершоп «Нож»',
  'Аптека у метро', 'Йога-зал «Мята»', 'Типография «Лист»', 'Салон «Волна»',
  'Коворкинг «Этаж»', 'Детский центр «Бим»', 'Мастерская «Глина»', 'Клиника «Шаг»',
]

const MANAGERS = ['Аня', 'Илья', 'Марина']

const STATUS_BAG = [
  'won', 'won', 'won', 'won',
  'lost',
  'proposal', 'proposal', 'proposal',
  'negotiation', 'negotiation',
  'in_progress', 'in_progress',
  'new',
] as const

const STATUS_LABEL: Record<string, string> = {
  new: 'Новая',
  in_progress: 'В работе',
  proposal: 'КП отправлено',
  negotiation: 'Согласование',
  won: 'Оплачено',
  lost: 'Отказ',
}

function mulberry32(seed: number): () => number {
  let state = seed
  return () => {
    state = (state + 0x6d2b79f5) | 0
    let next = Math.imul(state ^ (state >>> 15), 1 | state)
    next = (next + Math.imul(next ^ (next >>> 7), 61 | next)) ^ next
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296
  }
}

function sum(deals: EvidenceDeal[]): number {
  return deals.reduce((total, deal) => total + Number(deal.amount), 0)
}

function moneyPhrase(value: number): string {
  if (value >= 1_000_000) {
    const millions = value / 1_000_000
    const text = millions >= 10 ? String(Math.round(millions)) : millions.toFixed(1).replace('.', ',')
    return `${text} млн`
  }
  return `${Math.round(value / 1000)} тыс.`
}

function buildDeals(): EvidenceDeal[] {
  const random = mulberry32(20260321)
  const deals: EvidenceDeal[] = []
  for (let index = 0; index < 36; index += 1) {
    const status = STATUS_BAG[Math.floor(random() * STATUS_BAG.length)] ?? 'in_progress'
    const closed = status === 'won' || status === 'lost'
    const days = closed ? 2 + Math.floor(random() * 18) : 5 + Math.floor(random() * 40)
    const client = random() < 0.4 ? CLIENTS[Math.floor(random() * 2)] ?? CLIENTS[0] : CLIENTS[index % CLIENTS.length]
    const banquet = random() < 0.2
    const amount = banquet ? (35 + Math.floor(random() * 45)) * 1000 : (6 + Math.floor(random() * 16)) * 1000
    deals.push({
      deal_id: `d-${String(index + 1).padStart(3, '0')}`,
      client: client ?? 'Клиент',
      amount: String(amount),
      status,
      days_stale: days,
      manager: MANAGERS[index % MANAGERS.length] ?? 'Аня',
      contact: '',
    })
  }
  return deals
}

export const DEMO_DEALS = buildDeals()

function byDays(deals: EvidenceDeal[]): EvidenceDeal[] {
  return [...deals].sort((left, right) => (right.days_stale ?? 0) - (left.days_stale ?? 0))
}

function byAmount(deals: EvidenceDeal[]): EvidenceDeal[] {
  return [...deals].sort((left, right) => Number(right.amount) - Number(left.amount))
}

const OPEN = new Set(['new', 'in_progress', 'proposal', 'negotiation'])

export function evidenceFor(metricId: MetricId, deals: EvidenceDeal[]): EvidenceDeal[] {
  if (metricId === 'stagnation') return byDays(deals.filter((deal) => OPEN.has(deal.status) && (deal.days_stale ?? 0) >= 21)).slice(0, 12)
  if (metricId === 'dormant') return byDays(deals.filter((deal) => deal.status !== 'won' && (deal.days_stale ?? 0) >= 45)).slice(0, 12)
  if (metricId === 'funnel_dropoff') return byAmount(deals.filter((deal) => deal.status === 'proposal')).slice(0, 12)
  if (metricId === 'discount_leakage' || metricId === 'key_account_risk' || metricId === 'sales_cycle') {
    return byAmount(deals.filter((deal) => deal.status === 'won')).slice(0, 12)
  }
  return byDays(deals.filter((deal) => OPEN.has(deal.status))).slice(0, 12)
}

const PRIORITY: MetricId[] = [
  'stagnation',
  'discount_leakage',
  'funnel_dropoff',
  'speed_to_lead',
  'key_account_risk',
  'dormant',
  'sales_cycle',
]

export function findingsFor(deals: EvidenceDeal[], coverage: Coverage): Finding[] {
  const stale = evidenceFor('stagnation', deals)
  const won = deals.filter((deal) => deal.status === 'won')
  const proposal = evidenceFor('funnel_dropoff', deals)
  const dormant = evidenceFor('dormant', deals)
  const wonMoney = sum(won)
  const topTwo = new Set(byAmount(won).slice(0, 2).map((deal) => deal.client))
  const topMoney = sum(won.filter((deal) => topTwo.has(deal.client)))
  const topShare = wonMoney === 0 ? 0 : Math.round((topMoney / wonMoney) * 100)
  const bank: Record<MetricId, Finding> = {
    stagnation: {
      metric_id: 'stagnation',
      verdict: 'critical',
      value: stale.length,
      unit: 'deals',
      money_impact: String(sum(stale)),
      action: `Разморозьте ${stale.length} сделок старше 21 дня на ${moneyPhrase(sum(stale))}.`,
      threshold_label: 'Зависшей считаем сделку, которая стоит на этапе дольше 21 дня.',
    },
    discount_leakage: {
      metric_id: 'discount_leakage',
      verdict: 'critical',
      value: 19,
      unit: 'pct',
      money_impact: String(Math.round(wonMoney * 0.07)),
      action: `Запретите скидку выше 10% без согласования: так ушло ${moneyPhrase(Math.round(wonMoney * 0.07))}.`,
      threshold_label: 'Смотрим долю выигранных сделок со скидкой больше 10%.',
    },
    funnel_dropoff: {
      metric_id: 'funnel_dropoff',
      verdict: 'critical',
      value: 38,
      unit: 'pct',
      money_impact: String(sum(proposal)),
      action: `На этапе «КП отправлено» зависло ${moneyPhrase(sum(proposal))}. Позвоните, пока КП не ушло без разговора.`,
      threshold_label: 'Плохо, когда один этап забирает больше 40% суммы.',
    },
    speed_to_lead: {
      metric_id: 'speed_to_lead',
      verdict: 'critical',
      value: 11,
      unit: 'hours',
      money_impact: null,
      action: 'Отвечайте на новую заявку до 30 минут: сейчас медиана первого контакта 11 часов.',
      threshold_label: 'Дольше 30 минут — уже зона внимания, дольше 2 часов — критично.',
    },
    key_account_risk: {
      metric_id: 'key_account_risk',
      verdict: topShare > 65 ? 'critical' : 'watch',
      value: topShare,
      unit: 'pct',
      money_impact: null,
      action: `Два клиента дают ${topShare}% выручки. Заведите ещё один источник сделок на этой неделе.`,
      threshold_label: 'Тревога, когда два клиента дают больше половины выигранной выручки.',
    },
    dormant: {
      metric_id: 'dormant',
      verdict: 'watch',
      value: dormant.length,
      unit: 'deals',
      money_impact: String(sum(dormant)),
      action: `Верните в работу ${dormant.length} клиентов, с которыми тишина дольше 45 дней.`,
      threshold_label: 'Забытым считаем клиента без выигранной сделки и без касания 45 дней.',
    },
    sales_cycle: {
      metric_id: 'sales_cycle',
      verdict: 'watch',
      value: 34,
      unit: 'days',
      money_impact: null,
      action: 'Цикл вырос на второй половине периода. Разберите сделки, которые идут дольше месяца.',
      threshold_label: 'Смотрим медиану дней от заявки до оплаты по выигранным.',
    },
  }
  return PRIORITY.filter((id) => coverage.available.includes(id)).slice(0, 3).map((id) => bank[id])
}

export function totalsFor(deals: EvidenceDeal[]): { deals: number; amount: string; accepted: number; rejected: number } {
  return {
    deals: deals.length,
    amount: String(sum(deals)),
    accepted: deals.length,
    rejected: deals.filter((deal) => deal.status === 'lost').length,
  }
}

function dateFor(index: number): string {
  const day = (index % 27) + 1
  const month = (index % 3) + 1
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}.2026`
}

export function demoCsv(): string {
  const header = 'Клиент;Бюджет;Статус;Дней на этапе;Менеджер;Дата'
  const lines = DEMO_DEALS.map((deal, index) =>
    [
      deal.client,
      deal.amount,
      STATUS_LABEL[deal.status] ?? deal.status,
      String(deal.days_stale ?? 0),
      deal.manager ?? '',
      dateFor(index),
    ].join(';'),
  )
  return `${header}\n${lines.join('\n')}\n`
}

export function parseDemoCsv(text: string): EvidenceDeal[] {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  if (lines.length < 2) return []
  const delimiter = lines[0]?.includes(';') ? ';' : ','
  const header = lines[0]?.split(delimiter).map((cell) => cell.trim().toLowerCase()) ?? []
  const column = (...names: string[]) => header.findIndex((cell) => names.includes(cell))
  const clientAt = column('клиент')
  const amountAt = column('бюджет', 'сумма')
  const statusAt = column('статус')
  const daysAt = column('дней на этапе', 'дней')
  const managerAt = column('менеджер')
  if (clientAt < 0 || amountAt < 0) return []
  const reverse: Record<string, string> = {}
  for (const [code, label] of Object.entries(STATUS_LABEL)) reverse[label.toLowerCase()] = code
  return lines.slice(1).map((line, index) => {
    const cells = line.split(delimiter).map((cell) => cell.trim())
    const raw = (statusAt >= 0 ? cells[statusAt] : '') ?? ''
    return {
      deal_id: `d-${String(index + 1).padStart(3, '0')}`,
      client: cells[clientAt] ?? '',
      amount: String((cells[amountAt] ?? '0').replace(/[^\d]/g, '')),
      status: reverse[raw.toLowerCase()] ?? 'other',
      days_stale: Number(daysAt >= 0 ? cells[daysAt] : 0) || 0,
      manager: managerAt >= 0 ? cells[managerAt] : '',
      contact: '',
    }
  })
}
