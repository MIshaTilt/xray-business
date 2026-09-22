import { Typography } from '@maxhub/max-ui'
import type { EvidenceDeal } from '../api/types.ts'
import { formatRub } from '../domain/metrics.ts'

const STATUS: Record<string, string> = {
  new: 'Новая',
  in_progress: 'В работе',
  proposal: 'КП',
  negotiation: 'Согласование',
  won: 'Выиграна',
  lost: 'Отказ',
  other: 'Другое',
}

function statusLabel(status: string): string {
  return STATUS[status] ?? status
}

export function DealTable({ rows, wide }: { rows: EvidenceDeal[]; wide: boolean }) {
  if (rows.length === 0) {
    return <Typography.Body variant="medium">На этом срезе сделок нет. Откройте другую находку или добавьте колонку.</Typography.Body>
  }
  if (!wide) {
    return (
      <div className="deal-cards">
        {rows.map((deal) => (
          <article key={deal.deal_id} className="deal-card">
            <div className="deal-top">
              <Typography.Body variant="medium-strong">{deal.client || 'Без имени'}</Typography.Body>
              <span className="money">{formatRub(deal.amount)}</span>
            </div>
            <Typography.Label variant="small">
              <span className="status">{statusLabel(deal.status)}</span>
              {deal.days_stale != null ? ` · ${deal.days_stale} дн.` : ''}
              {deal.manager ? ` · ${deal.manager}` : ''}
            </Typography.Label>
          </article>
        ))}
      </div>
    )
  }
  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            <th>Клиент</th>
            <th>Сумма</th>
            <th>Статус</th>
            <th>Дней</th>
            <th>Менеджер</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((deal) => (
            <tr key={deal.deal_id}>
              <td>{deal.client || 'Без имени'}</td>
              <td>{formatRub(deal.amount)}</td>
              <td>{statusLabel(deal.status)}</td>
              <td>{deal.days_stale ?? '—'}</td>
              <td>{deal.manager || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
