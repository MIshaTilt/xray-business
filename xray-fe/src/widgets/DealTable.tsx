import { Typography } from '@maxhub/max-ui'
import type { EvidenceDeal } from '../api/types.ts'
import { formatRub } from '../domain/metrics.ts'
import { DataTable } from './DataTable.tsx'

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
    <DataTable>
      <table>
        <thead>
          <tr>
            <th>Клиент</th>
            <th>Сумма</th>
            <th>Статус</th>
            <th className="is-auto-calc-th">
              Дней <span className="auto-calc-tag" title="Автоматический расчет">авто</span>
            </th>
            <th>Менеджер</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((deal) => (
            <tr key={deal.deal_id}>
              <td>{deal.client || 'Без имени'}</td>
              <td>{formatRub(deal.amount)}</td>
              <td>{statusLabel(deal.status)}</td>
              <td className="is-auto-calc-td">
                {deal.days_stale != null ? <span className="auto-calc-val">{deal.days_stale} дн.</span> : '—'}
              </td>
              <td>{deal.manager || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </DataTable>
  )
}
