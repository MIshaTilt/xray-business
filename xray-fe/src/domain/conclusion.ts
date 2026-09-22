import type { Diagnosis } from '../api/types.ts'

export function buildConclusion(diagnosis: Pick<Diagnosis, 'headline' | 'findings' | 'coverage'>): string {
  const actions = diagnosis.findings.map((finding) => finding.action).filter((action) => action.trim().length > 0)
  const counted = diagnosis.coverage.available.length
  return [diagnosis.headline, '', ...actions, '', `посчитано ${counted} из 7`].join('\n')
}
