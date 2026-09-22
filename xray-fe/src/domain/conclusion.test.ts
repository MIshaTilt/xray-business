import { describe, expect, it } from 'vitest'
import type { Finding } from '../api/types.ts'
import { buildConclusion } from './conclusion.ts'

const finding = (action: string): Finding => ({
  metric_id: 'stagnation',
  verdict: 'critical',
  value: 12,
  unit: 'deals',
  money_impact: '4200000',
  action,
  threshold_label: 'дольше 21 дня',
})

describe('buildConclusion', () => {
  it('собирает заголовок, действия и покрытие', () => {
    const text = buildConclusion({
      headline: 'Главная утечка — зависшие сделки.',
      findings: [finding('Разморозьте 12 сделок.'), finding('Запретите скидку выше 10%.')],
      coverage: { available: ['stagnation', 'funnel_dropoff', 'key_account_risk'], skipped: ['speed_to_lead'] },
    })
    expect(text).toBe(
      [
        'Главная утечка — зависшие сделки.',
        '',
        'Разморозьте 12 сделок.',
        'Запретите скидку выше 10%.',
        '',
        'посчитано 3 из 7',
      ].join('\n'),
    )
  })
})
