import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { CanonicalField, Coverage, Mapping as MappingValue, UploadResponse } from '../api/types.ts'
import { canEnlighten, compactMapping, MAPPING_FIELDS } from '../domain/mapping.ts'
import { setClosingConfirmation } from '../bridge/index.ts'
import { CoverageBar } from '../widgets/CoverageBar.tsx'
import { DataTable } from '../widgets/DataTable.tsx'
import { FlyoutSelect } from '../widgets/FlyoutSelect.tsx'
import { Notice } from '../widgets/Notice.tsx'

export function MappingScreen({
  upload,
  onStart,
  onAnalyze,
  onAnalyzeStop,
}: {
  upload: UploadResponse
  onStart: (snapshotId: string) => void
  onAnalyze: () => void
  onAnalyzeStop: () => void
}) {
  const [mapping, setMapping] = useState<MappingValue>(upload.suggested_mapping)
  const [coverage, setCoverage] = useState<Coverage>(upload.coverage)
  const [autoCols, setAutoCols] = useState<string[]>(upload.auto_computed_columns || [])
  const [warnings, setWarnings] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [openColumn, setOpenColumn] = useState<string | null>(null)
  const [closingColumns, setClosingColumns] = useState<ReadonlySet<string>>(() => new Set())
  const closeTimers = useRef<Record<string, number>>({})
  const fieldsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setClosingConfirmation(dirty)
    return () => setClosingConfirmation(false)
  }, [dirty])

  useEffect(() => {
    if (!dirty) return
    const timer = window.setTimeout(() => {
      void api
        .saveMapping(upload.upload_id, compactMapping(mapping))
        .then((result) => {
          setCoverage(result.coverage)
          setWarnings(result.warnings)
          if (result.auto_computed_columns) {
            setAutoCols(result.auto_computed_columns)
          }
        })
        .catch((reason: unknown) => setError(errorText(reason)))
    }, 400)
    return () => window.clearTimeout(timer)
  }, [dirty, mapping, upload.upload_id])

  function roleOf(column: string): CanonicalField | '' {
    const field = MAPPING_FIELDS.find((item) => mapping[item.id] === column)
    return field?.id ?? ''
  }

  function isAutoComputed(column: string): boolean {
    if (autoCols.includes(column)) return true
    const lower = column.toLowerCase()
    return lower.includes('(авто)') || lower.includes('(расчет)') || lower.includes('(авторасчет)')
  }

  function assignRole(column: string, fieldId: string) {
    setDirty(true)
    setMapping((current) => {
      const next: MappingValue = { ...current }
      for (const field of MAPPING_FIELDS) {
        if (next[field.id] === column) delete next[field.id]
      }
      if (fieldId) next[fieldId as CanonicalField] = column
      return next
    })
    closeFlyout()
  }

  function beginClose(id: string) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    setClosingColumns((current) => {
      if (current.has(id)) return current
      const next = new Set(current)
      next.add(id)
      return next
    })
    window.clearTimeout(closeTimers.current[id])
    closeTimers.current[id] = window.setTimeout(() => {
      setClosingColumns((current) => {
        if (!current.has(id)) return current
        const next = new Set(current)
        next.delete(id)
        return next
      })
      delete closeTimers.current[id]
    }, 420)
  }

  function cancelClose(id: string) {
    window.clearTimeout(closeTimers.current[id])
    delete closeTimers.current[id]
    setClosingColumns((current) => {
      if (!current.has(id)) return current
      const next = new Set(current)
      next.delete(id)
      return next
    })
  }

  function closeFlyout() {
    if (!openColumn) return
    const id = openColumn
    setOpenColumn(null)
    beginClose(id)
  }

  function toggleFlyout(column: string) {
    if (openColumn === column) {
      closeFlyout()
      return
    }
    if (openColumn) beginClose(openColumn)
    cancelClose(column)
    setOpenColumn(column)
  }

  useEffect(
    () => () => {
      Object.values(closeTimers.current).forEach((timer) => window.clearTimeout(timer))
    },
    [],
  )

  useEffect(() => {
    if (!openColumn) return
    function onPointer(event: PointerEvent) {
      const target = event.target as Node | null
      if (fieldsRef.current?.contains(target)) return
      if (target instanceof Element && target.closest('.template-dropdown-menu')) return
      closeFlyout()
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') closeFlyout()
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [openColumn])

  async function enlighten() {
    setBusy(true)
    setError('')
    onAnalyze()
    try {
      const compact = compactMapping(mapping)
      await api.saveMapping(upload.upload_id, compact)
      const created = await api.createSnapshot(upload.upload_id, compact)
      onStart(created.snapshot_id)
    } catch (reason) {
      onAnalyzeStop()
      setError(errorText(reason))
    } finally {
      setBusy(false)
    }
  }

  const ready = canEnlighten(mapping)
  const takenFields = new Set(
    Object.entries(mapping)
      .filter(([, column]) => Boolean(column))
      .map(([field]) => field),
  )

  return (
    <div className="stack mapping-screen">
      <div className="lead">
        <h1>Проверьте колонки</h1>
        <Typography.Body variant="medium">Нажмите заголовок колонки и назначьте роль.</Typography.Body>
      </div>
      <CoverageBar coverage={coverage} compact />
      {error ? <Notice tone="error">{error}</Notice> : null}
      {warnings.map((warning) => (
        <Notice key={warning} tone="ok">{warning}</Notice>
      ))}
      <div ref={fieldsRef}>
        <DataTable>
          <table>
            <thead>
              <tr>
                {upload.columns.map((column) => {
                  const role = roleOf(column)
                  const field = MAPPING_FIELDS.find((item) => item.id === role)
                  const isAuto = isAutoComputed(column)
                  return (
                    <th
                      key={column}
                      className={`${role ? 'is-mapped' : ''} ${isAuto ? 'is-auto-computed' : ''}`.trim() || undefined}
                    >
                      <FlyoutSelect
                        value={role}
                        placeholder="Не назначено"
                        emptyLabel="Назначить"
                        caption={column}
                        minMenuWidth={240}
                        triggerClassName={`map-col flyout-trigger${role ? ' is-set' : ' is-empty'}${isAuto ? ' is-auto-trigger' : ''}`}
                        options={MAPPING_FIELDS.filter((item) => item.id === role || !takenFields.has(item.id)).map(
                          (item) => ({ value: item.id, label: item.label }),
                        )}
                        open={openColumn === column}
                        closing={closingColumns.has(column)}
                        onToggle={() => toggleFlyout(column)}
                        onChange={(fieldId) => assignRole(column, fieldId)}
                      />
                      {isAuto ? (
                        <span className="auto-computed-badge" title="Колонка автоматически рассчитана сервисом X-Ray">
                          <span className="auto-computed-dot" />
                          Авторасчет
                        </span>
                      ) : null}
                      {field ? <span className="map-col-hint">{field.badge}</span> : null}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {upload.sample_rows.map((row, index) => (
                <tr key={index}>
                  {upload.columns.map((column) => {
                    const isAuto = isAutoComputed(column)
                    return (
                      <td key={column} className={isAuto ? 'is-auto-computed' : undefined}>
                        {isAuto ? (
                          <span className="auto-computed-cell-val">{row[column] || '—'}</span>
                        ) : (
                          row[column] || '—'
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </DataTable>
      </div>
      {ready ? null : (
        <Typography.Body variant="medium">Нужны сумма и дата или статус.</Typography.Body>
      )}
      {createPortal(
        <div className="mapping-cta">
          <Button className="action action-primary" type="button" size="large" stretched variant="primary" disabled={!ready} loading={busy} onClick={() => void enlighten()}>
            Сделать снимок
          </Button>
        </div>,
        document.querySelector('.app-shell') ?? document.body,
      )}
    </div>
  )
}
