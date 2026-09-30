import type {
  ComparisonResult,
  Coverage,
  Diagnosis,
  DiagnosisResponse,
  EvidenceDeal,
  Mapping,
  MappingResponse,
  MetricDetail,
  MetricId,
  SnapshotListItem,
  SnapshotPoll,
  UploadResponse,
} from './types.ts'
import { ApiError } from './errors.ts'
import { coverageFromMapping } from '../domain/mapping.ts'
import { DEMO_DEALS, evidenceFor, findingsFor, parseDemoCsv, totalsFor } from './demo-data.ts'

function newId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

const uploadDeals = new Map<string, EvidenceDeal[]>()
const uploadNames = new Map<string, string>()


type StoredSnapshot = {
  id: string
  createdAt: string
  readyAt: number
  failed: boolean
  error: string
  diagnosis: Diagnosis
  deals: EvidenceDeal[]
  source: string
}

const snapshots = new Map<string, StoredSnapshot>()
const uploads: { at: number }[] = []

function diagnosisFor(coverage: Coverage, deals: EvidenceDeal[]): Diagnosis {
  const findings = findingsFor(deals, coverage)
  const headline = findings[0]
    ? 'Продажи идут, но главная утечка уже видна в рублях.'
    : 'По этим колонкам рентген почти пустой. Добавьте сумму и статус или дату.'
  return {
    headline,
    body: findings.map((finding) => finding.action).join(' '),
    findings,
    coverage,
    period: { from: '2026-01-01', to: '2026-03-31' },
    totals: totalsFor(deals),
  }
}

function columnsFor(filename: string): { columns: string[]; mapping: Mapping; rows: Record<string, string>[] } {
  const base = [
    { Клиент: 'Северная верфь', Бюджет: '1 200 000 руб.', Статус: 'КП отправлено', Дата: '14.01.2026', Менеджер: 'Аня' },
    { Клиент: 'Маяк', Бюджет: '860 000 руб.', Статус: 'Пинать в пятницу', Дата: '02.02.2026', Менеджер: 'Илья' },
    { Клиент: 'Контур света', Бюджет: '640 000 руб.', Статус: 'В работе', Дата: '18.02.2026', Менеджер: 'Аня' },
    { Клиент: 'Бюро поле', Бюджет: '510 000 руб.', Статус: 'Оплачено', Дата: '03.03.2026', Менеджер: 'Илья' },
    { Клиент: 'Тихая гавань', Бюджет: '990 000 руб.', Статус: 'Думает', Дата: '11.03.2026', Менеджер: 'Аня' },
  ]
  const dropManager = /nomanager|no-manager|без-менеджера/i.test(filename)
  const rows = base.map((row) => {
    if (!dropManager) return row
    const { Менеджер: _manager, ...rest } = row
    return rest
  })
  const columns = Object.keys(rows[0] ?? {})
  const mapping: Mapping = {
    amount: 'Бюджет',
    client: 'Клиент',
    status: 'Статус',
    created_at: 'Дата',
  }
  if (!dropManager) mapping.manager = 'Менеджер'
  return { columns, mapping, rows }
}

function rememberUpload(): void {
  const hourAgo = Date.now() - 60 * 60 * 1000
  while (uploads.length > 0 && uploads[0]!.at < hourAgo) uploads.shift()
  if (uploads.length >= 20) {
    throw new ApiError(429, 'Слишком много загрузок за час. Выгрузите период покороче и попробуйте позже.')
  }
  uploads.push({ at: Date.now() })
}

function requireSnapshot(id: string): StoredSnapshot {
  const snapshot = snapshots.get(id)
  if (!snapshot) throw new ApiError(404, 'Снимок не найден')
  return snapshot
}

function pollOf(snapshot: StoredSnapshot): SnapshotPoll {
  if (snapshot.failed) {
    return { snapshot_id: snapshot.id, status: 'failed', progress: 100, error: snapshot.error }
  }
  if (Date.now() >= snapshot.readyAt) {
    return { snapshot_id: snapshot.id, status: 'ready', progress: 100, error: '' }
  }
  const started = new Date(snapshot.createdAt).getTime()
  const span = Math.max(snapshot.readyAt - started, 1)
  const progress = Math.min(90, Math.round(((Date.now() - started) / span) * 90))
  return { snapshot_id: snapshot.id, status: 'processing', progress, error: '' }
}

export const fixtures = {
  async upload(file: File): Promise<UploadResponse> {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext !== 'csv') {
      throw new ApiError(400, 'Нужен CSV — выгрузка из 1С, Битрикс24, МойСклад, amoCRM.')
    }
    if (file.size === 0 || /empty/i.test(file.name)) {
      throw new ApiError(400, 'В файле 0 строк с данными.')
    }
    if (file.size > 20 * 1024 * 1024) {
      throw new ApiError(400, 'Слишком большой файл. Выгрузите последние 90 дней.')
    }
    rememberUpload()
    const parsed = columnsFor(file.name)
    const uploadId = newId()
    const fromFile = ext === 'csv' ? parseDemoCsv(await file.text()) : []
    uploadDeals.set(uploadId, fromFile.length > 0 ? fromFile : DEMO_DEALS)
    uploadNames.set(uploadId, file.name)
    return {
      upload_id: uploadId,
      filename: file.name,
      columns: parsed.columns,
      sample_rows: parsed.rows,
      suggested_mapping: parsed.mapping,
      coverage: coverageFromMapping(parsed.mapping),
    }
  },

  async saveMapping(mapping: Mapping): Promise<MappingResponse> {
    const coverage = coverageFromMapping(mapping)
    const warnings: string[] = []
    if (!mapping.created_at) warnings.push('Колонка даты не выбрана. Часть метрик останется закрытой.')
    if (!mapping.manager) warnings.push('Колонки менеджера нет. В списке сделок это поле будет пустым, семь метрик от него не зависят.')
    return { coverage, warnings }
  },

  async createSnapshot(uploadId: string, mapping: Mapping): Promise<{ snapshot_id: string; status: 'processing' }> {
    const coverage = coverageFromMapping(mapping)
    const deals = uploadDeals.get(uploadId) ?? DEMO_DEALS
    const id = newId()
    const createdAt = new Date().toISOString()
    snapshots.set(id, {
      id,
      createdAt,
      readyAt: Date.now() + 2000,
      failed: /fail/i.test(mapping.client ?? ''),
      error: /fail/i.test(mapping.client ?? '') ? 'Не удалось прочитать строки.' : '',
      diagnosis: diagnosisFor(coverage, deals),
      deals,
      source: uploadNames.get(uploadId) ?? 'файл',
    })
    return { snapshot_id: id, status: 'processing' }
  },

  async demo(): Promise<DiagnosisResponse> {
    const mapping: Mapping = {
      amount: 'Бюджет',
      client: 'Клиент',
      status: 'Статус',
      created_at: 'Дата',
      manager: 'Менеджер',
      discount_pct: 'Скидка',
      list_price: 'Прайс',
      first_contact_at: 'Первый контакт',
      closed_at: 'Закрыта',
      last_activity_at: 'Активность',
    }
    const id = newId()
    const diagnosis = diagnosisFor(coverageFromMapping(mapping), DEMO_DEALS)
    snapshots.set(id, {
      id,
      createdAt: new Date().toISOString(),
      readyAt: Date.now(),
      failed: false,
      error: '',
      diagnosis,
      deals: DEMO_DEALS,
      source: 'демо',
    })
    return { snapshot_id: id, ...diagnosis }
  },

  async poll(id: string): Promise<SnapshotPoll> {
    return pollOf(requireSnapshot(id))
  },

  async diagnosis(id: string): Promise<DiagnosisResponse> {
    const snapshot = requireSnapshot(id)
    const poll = pollOf(snapshot)
    if (poll.status === 'failed') throw new ApiError(409, snapshot.error || 'Снимок не посчитался')
    if (poll.status !== 'ready') throw new ApiError(409, 'Снимок ещё считается')
    return { snapshot_id: id, ...snapshot.diagnosis }
  },

  async metric(id: string, metricId: MetricId): Promise<MetricDetail> {
    const snapshot = requireSnapshot(id)
    const poll = pollOf(snapshot)
    if (poll.status !== 'ready') throw new ApiError(409, 'Снимок ещё считается')
    const finding = findingsFor(snapshot.deals, { available: [metricId], skipped: [] })[0]
    const available = snapshot.diagnosis.coverage.available.includes(metricId) && finding != null
    return {
      result: {
        metric_id: metricId,
        available,
        missing_fields: available || !finding ? [] : [finding.threshold_label],
        value: available && finding ? finding.value : null,
        unit: finding?.unit ?? '',
        verdict: available && finding ? finding.verdict : 'skipped',
        money_impact: available && finding ? finding.money_impact : null,
        threshold_label: finding?.threshold_label ?? '',
        action: finding?.action ?? '',
      },
      evidence: available ? evidenceFor(metricId, snapshot.deals) : [],
    }
  },

  async list(): Promise<SnapshotListItem[]> {
    return [...snapshots.values()]
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .slice(0, 20)
      .map((snapshot) => {
        const poll = pollOf(snapshot)
        const first = snapshot.diagnosis.findings[0]
        return {
          snapshot_id: snapshot.id,
          scan_no: [...snapshots.keys()].indexOf(snapshot.id) + 1,
          status: poll.status,
          created_at: snapshot.createdAt,
          headline: poll.status === 'ready' ? first?.action ?? snapshot.diagnosis.headline : undefined,
          card_title: poll.status === 'ready' ? snapshot.source : undefined,
          filename: snapshot.source,
          topics: snapshot.diagnosis.findings
            .filter((finding) => finding.verdict === 'critical' || finding.verdict === 'watch')
            .slice(0, 2)
            .map((finding) => finding.metric_id),
          source: snapshot.source,
          verdict: first && (first.verdict === 'critical' || first.verdict === 'watch' || first.verdict === 'ok') ? first.verdict : undefined,
          coverage_label: `${snapshot.diagnosis.coverage.available.length} из 7`,
        }
      })
  },

  async remove(id: string): Promise<void> {
    if (!snapshots.delete(id)) throw new ApiError(404, 'Снимок не найден')
  },

  async template(): Promise<Blob> {
    const response = await fetch('/xray-template.xlsx')
    if (!response.ok) throw new ApiError(response.status, 'Шаблон не найден')
    return response.blob()
  },

  async compare(baseId: string, targetId: string): Promise<ComparisonResult> {
    const snap1 = snapshots.get(baseId)
    const snap2 = snapshots.get(targetId)

    const baseName = snap1?.source || 'Срез 1'
    const targetName = snap2?.source || 'Срез 2'
    const baseDate = snap1?.createdAt || '2026-07-15'
    const targetDate = snap2?.createdAt || '2026-09-22'

    return {
      base: {
        snapshot_id: baseId,
        filename: baseName,
        created_at: baseDate,
        headline: snap1?.diagnosis.headline || 'Исходный аудит воронки',
        totals: snap1?.diagnosis.totals || { deals: 15, amount: 1890000 },
      },
      target: {
        snapshot_id: targetId,
        filename: targetName,
        created_at: targetDate,
        headline: snap2?.diagnosis.headline || 'Повторный срез после оптимизации',
        totals: snap2?.diagnosis.totals || { deals: 24, amount: 2645000 },
      },
      summary: {
        headline: 'Вы вернули в оборот 581 775 ₽ благодаря разбору зависших сделок и контролю скидок',
        body: `Сравнение среза от ${baseDate} со срезом от ${targetDate}. Выручка выросла на 755 000 ₽ (+40.0%), средний чек скорректировался до 110 208 ₽. Ключевые точки роста: устранение утечки скидок на 56.4% и сокращение зависших сделок на 62.5%.`,
        saved_money: 581775,
        trend: 'improved',
      },
      totals_diff: {
        amount: {
          base: 1890000,
          target: 2645000,
          delta_abs: 755000,
          delta_pct: 39.9,
          status: 'positive',
          unit: 'rub',
        },
        deals: {
          base: 15,
          target: 24,
          delta_abs: 9,
          delta_pct: 60.0,
          status: 'positive',
          unit: 'count',
        },
        avg_check: {
          base: 126000,
          target: 110208,
          delta_abs: -15792,
          delta_pct: -12.5,
          status: 'negative',
          unit: 'rub',
        },
      },
      metrics_diff: [
        {
          metric_id: 'stagnation',
          name: 'Зависшие сделки',
          base_value: 24,
          target_value: 9,
          base_impact: 840000,
          target_impact: 315000,
          delta_value: -15,
          delta_pct: -62.5,
          delta_impact: -525000,
          unit: 'days',
          status: 'positive',
          base_verdict: 'critical',
          target_verdict: 'ok',
        },
        {
          metric_id: 'discount_leakage',
          name: 'Утечка скидок',
          base_value: 18.5,
          target_value: 8.1,
          base_impact: 142000,
          target_impact: 85225,
          delta_value: -10.4,
          delta_pct: -56.2,
          delta_impact: -56775,
          unit: 'pct',
          status: 'positive',
          base_verdict: 'watch',
          target_verdict: 'ok',
        },
        {
          metric_id: 'speed_to_lead',
          name: 'Скорость первого ответа',
          base_value: 3.2,
          target_value: 1.1,
          base_impact: 0,
          target_impact: 0,
          delta_value: -2.1,
          delta_pct: -65.6,
          delta_impact: 0,
          unit: 'hours',
          status: 'positive',
          base_verdict: 'watch',
          target_verdict: 'ok',
        },
        {
          metric_id: 'sales_cycle',
          name: 'Цикл сделки',
          base_value: 38,
          target_value: 26,
          base_impact: 0,
          target_impact: 0,
          delta_value: -12,
          delta_pct: -31.6,
          delta_impact: 0,
          unit: 'days',
          status: 'positive',
          base_verdict: 'ok',
          target_verdict: 'ok',
        },
      ],
      managers_diff: [
        {
          manager: 'Алексей Смирнов',
          base_amount: 850000,
          target_amount: 1420000,
          delta_amount: 570000,
          delta_pct: 67.1,
          base_deals: 6,
          target_deals: 11,
          base_won: 520000,
          target_won: 980000,
          status: 'positive',
        },
        {
          manager: 'Елена Кузнецова',
          base_amount: 640000,
          target_amount: 825000,
          delta_amount: 185000,
          delta_pct: 28.9,
          base_deals: 5,
          target_deals: 8,
          base_won: 410000,
          target_won: 590000,
          status: 'positive',
        },
        {
          manager: 'Михаил Орлов',
          base_amount: 400000,
          target_amount: 400000,
          delta_amount: 0,
          delta_pct: 0.0,
          base_deals: 4,
          target_deals: 5,
          base_won: 210000,
          target_won: 240000,
          status: 'positive',
        },
      ],
      total_saved_money: 581775,
    }
  },
}
