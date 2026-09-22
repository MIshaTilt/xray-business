import { describe, expect, it } from 'vitest'
import { dealsAsTable } from './platform.ts'

describe('dealsAsTable', () => {
  it('на телефоне показывает карточки, на широком экране таблицу', () => {
    expect(dealsAsTable('ios')).toBe(false)
    expect(dealsAsTable('android')).toBe(false)
    expect(dealsAsTable('desktop')).toBe(true)
    expect(dealsAsTable('web')).toBe(true)
  })
})
