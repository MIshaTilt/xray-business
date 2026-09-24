import type { MetricId, Verdict } from '../api/types.ts'

export const METRIC_ORDER: MetricId[] = [
  'speed_to_lead',
  'stagnation',
  'discount_leakage',
  'sales_cycle',
  'key_account_risk',
  'dormant',
  'funnel_dropoff',
]

export type MetricCopy = {
  id: MetricId
  title: string
  needs: string
  hint: string
  what: string
  how: string
}

export const METRICS: Record<MetricId, MetricCopy> = {
  speed_to_lead: {
    id: 'speed_to_lead',
    title: 'Скорость первого ответа',
    needs: 'дата создания и дата первого контакта',
    hint: 'Чтобы найти утечку на входе, добавьте дату первого звонка.',
    what: 'Сколько времени проходит от заявки до первого звонка или письма.',
    how: 'Берём медиану по сделкам, где есть обе даты. Дольше 30 минут — уже внимание, дольше 2 часов — критично.',
  },
  stagnation: {
    id: 'stagnation',
    title: 'Зависшие сделки',
    needs: 'статус и дата',
    hint: 'Без статуса и даты не видно, какие сделки стоят дольше обычного цикла.',
    what: 'Открытые сделки, которые стоят на этапе дольше обычного цикла продажи.',
    how: 'Сначала считаем медиану цикла выигранных сделок. Открытая зависла, если она на статусе дольше 1,5 этой медианы. В рублях показываем сумму таких сделок.',
  },
  discount_leakage: {
    id: 'discount_leakage',
    title: 'Утечка скидок',
    needs: 'сумма и скидка или прайс',
    hint: 'Без колонки скидки не видно, где менеджеры продают скидкой.',
    what: 'Выигранные сделки, которые закрылись со скидкой больше обычной.',
    how: 'Смотрим долю выигранных со скидкой выше 10%. Если в файле есть прайс, рядом считаем недополученную разницу между прайсом и суммой.',
  },
  sales_cycle: {
    id: 'sales_cycle',
    title: 'Цикл сделки',
    needs: 'дата создания и дата закрытия',
    hint: 'Чтобы увидеть, растёт ли цикл, добавьте дату оплаты.',
    what: 'Сколько дней проходит от заявки до оплаты и не стал ли путь длиннее.',
    how: 'Медиана по выигранным сделкам. Период делим пополам и сравниваем: рост больше 30% — критично.',
  },
  key_account_risk: {
    id: 'key_account_risk',
    title: 'Зависимость от крупных клиентов',
    needs: 'клиент и статус',
    hint: 'Без имени клиента не видно зависимость от двух крупных заказчиков.',
    what: 'Какая часть выигранной выручки сидит на двух самых крупных клиентах.',
    how: 'Складываем суммы выигранных сделок, берём двух крупнейших клиентов и считаем их долю. Больше 50% — внимание, больше 65% — критично.',
  },
  dormant: {
    id: 'dormant',
    title: 'Забытые клиенты',
    needs: 'клиент и дата',
    hint: 'Без клиента и даты не видно, кому не звонили больше 45 дней.',
    what: 'Клиенты без выигранной сделки, с которыми давно не было контакта.',
    how: 'Тишина больше 45 дней от последней активности. Если такой даты нет, считаем от даты создания.',
  },
  funnel_dropoff: {
    id: 'funnel_dropoff',
    title: 'Провал воронки',
    needs: 'статус и сумма',
    hint: 'Без статуса и суммы не видно, на каком этапе отваливаются деньги.',
    what: 'Этап, на котором теряется больше всего денег.',
    how: 'Сравниваем сумму сделок, дошедших до этапа, с суммой следующего. Берём этап с самой большой потерей. Больше 40% суммы — внимание, больше 55% — критично.',
  },
}

const UNIT_LABEL: Record<string, string> = {
  hours: 'ч',
  days: 'дн.',
  pct: '%',
  rub: 'руб.',
  deals: 'сделок',
}

export function verdictLabel(verdict: Verdict): string {
  switch (verdict) {
    case 'critical':
      return 'Критично'
    case 'watch':
      return 'Стоит смотреть'
    case 'ok':
      return 'В норме'
    case 'skipped':
      return 'Не посчитано'
  }
}

export function formatRub(value: string | number | null | undefined): string {
  if (value == null || value === '') return '—'
  const amount = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(amount)) return String(value)
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(amount)} руб.`
}

export function formatImpact(finding: { money_impact: string | null; value: number | null; unit: string }): string {
  if (finding.money_impact) return formatRub(finding.money_impact)
  if (finding.value == null) return '—'
  const unit = UNIT_LABEL[finding.unit] ?? finding.unit
  return `${new Intl.NumberFormat('ru-RU').format(finding.value)} ${unit}`
}

export function formatWhen(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(date)
}
