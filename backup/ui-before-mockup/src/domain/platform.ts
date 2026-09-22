import type { Platform } from '../bridge/types.ts'

export function dealsAsTable(platform: Platform): boolean {
  return platform === 'desktop' || platform === 'web'
}
