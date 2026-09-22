import { describe, expect, it } from 'vitest'
import { canEnlighten, coverageFromMapping } from './mapping.ts'

describe('canEnlighten', () => {
  it('требует сумму и статус или дату', () => {
    expect(canEnlighten({})).toBe(false)
    expect(canEnlighten({ amount: 'Бюджет' })).toBe(false)
    expect(canEnlighten({ amount: 'Бюджет', status: 'Статус' })).toBe(true)
    expect(canEnlighten({ amount: 'Бюджет', created_at: 'Дата' })).toBe(true)
    expect(canEnlighten({ amount: '', status: 'Статус' })).toBe(false)
  })
})

describe('coverageFromMapping', () => {
  it('считает покрытие по колонкам, а не по желанию', () => {
    const coverage = coverageFromMapping({
      amount: 'Бюджет',
      client: 'Клиент',
      status: 'Статус',
      created_at: 'Дата',
    })
    expect(coverage.available).toEqual(['stagnation', 'key_account_risk', 'dormant', 'funnel_dropoff'])
    expect(coverage.skipped).toContain('speed_to_lead')
    expect(coverage.skipped).toContain('discount_leakage')
    expect(coverage.available.length + coverage.skipped.length).toBe(7)
  })

  it('без колонок пропускает все семь', () => {
    const coverage = coverageFromMapping({})
    expect(coverage.available).toEqual([])
    expect(coverage.skipped).toHaveLength(7)
  })
})
