import type { CanonicalField, Coverage, Mapping, MetricId } from '../api/types.ts'
import { METRIC_ORDER } from './metrics.ts'

export type FieldSpec = {
  id: CanonicalField
  label: string
  badge: string
}

export const MAPPING_FIELDS: FieldSpec[] = [
  { id: 'amount', label: 'Сумма сделки', badge: 'нужно, чтобы просветить' },
  { id: 'status', label: 'Статус', badge: 'нужно для воронки и зависших' },
  { id: 'created_at', label: 'Дата создания', badge: 'нужно для цикла и скорости' },
  { id: 'client', label: 'Клиент', badge: 'нужно для крупных и забытых' },
  { id: 'manager', label: 'Менеджер', badge: 'видно в списке сделок' },
  { id: 'contact', label: 'Контакт', badge: 'телефон или почта' },
  { id: 'discount_pct', label: 'Скидка, %', badge: 'нужно для утечки скидок' },
  { id: 'list_price', label: 'Прайс до скидки', badge: 'нужно для утечки скидок' },
  { id: 'first_contact_at', label: 'Первый контакт', badge: 'нужно для скорости ответа' },
  { id: 'closed_at', label: 'Дата закрытия', badge: 'нужно для цикла сделки' },
  { id: 'status_changed_at', label: 'Дата смены статуса', badge: 'точнее считает зависшие' },
  { id: 'last_activity_at', label: 'Последняя активность', badge: 'нужно для забытых' },
  { id: 'source', label: 'Источник', badge: 'канал лида' },
  { id: 'deal_id', label: 'Номер сделки', badge: 'если есть свой id' },
]

const NONE = ''

export function hasField(mapping: Mapping, field: CanonicalField): boolean {
  return Boolean(mapping[field] && mapping[field] !== NONE)
}

export function canEnlighten(mapping: Mapping): boolean {
  return hasField(mapping, 'amount') && (hasField(mapping, 'status') || hasField(mapping, 'created_at'))
}

export function coverageFromMapping(mapping: Mapping): Coverage {
  const ready: Record<MetricId, boolean> = {
    speed_to_lead: hasField(mapping, 'created_at') && hasField(mapping, 'first_contact_at'),
    stagnation: hasField(mapping, 'status') && (hasField(mapping, 'status_changed_at') || hasField(mapping, 'created_at')),
    discount_leakage: hasField(mapping, 'amount') && (hasField(mapping, 'discount_pct') || hasField(mapping, 'list_price')),
    sales_cycle: hasField(mapping, 'created_at') && hasField(mapping, 'closed_at'),
    key_account_risk: hasField(mapping, 'client') && hasField(mapping, 'status'),
    dormant: hasField(mapping, 'client') && (hasField(mapping, 'last_activity_at') || hasField(mapping, 'created_at')),
    funnel_dropoff: hasField(mapping, 'status') && hasField(mapping, 'amount'),
  }
  const available = METRIC_ORDER.filter((id) => ready[id])
  const skipped = METRIC_ORDER.filter((id) => !ready[id])
  return { available, skipped }
}

export function exampleValue(rows: Record<string, string>[], column: string | undefined): string {
  if (!column) return 'нет колонки'
  const cell = rows.find((row) => row[column])?.[column]
  return cell && cell.trim() ? cell : 'пусто'
}

export function compactMapping(mapping: Mapping): Mapping {
  const next: Mapping = {}
  for (const field of MAPPING_FIELDS) {
    const column = mapping[field.id]
    if (column) next[field.id] = column
  }
  return next
}
