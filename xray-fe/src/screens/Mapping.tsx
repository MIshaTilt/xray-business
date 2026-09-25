import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { CanonicalField, Coverage, Mapping as MappingValue, UploadResponse } from '../api/types.ts'
import { canEnlighten, compactMapping, exampleValue, MAPPING_FIELDS } from '../domain/mapping.ts'
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
  const [warnings, setWarnings] = useState<string[]>([])
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [openField, setOpenField] = useState<CanonicalField | null>(null)
  const [closingFields, setClosingFields] = useState<ReadonlySet<CanonicalField>>(() => new Set())
  const closeTimers = useRef<Partial<Record<CanonicalField, number>>>({})
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
        })
        .catch((reason: unknown) => setError(errorText(reason)))
    }, 400)
    return () => window.clearTimeout(timer)
  }, [dirty, mapping, upload.upload_id])

  function change(field: keyof MappingValue, column: string) {
    setDirty(true)
    setMapping((current) => ({ ...current, [field]: column || undefined }))
    closeFlyout()
  }

  function beginClose(id: CanonicalField) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    setClosingFields((current) => {
      if (current.has(id)) return current
      const next = new Set(current)
      next.add(id)
      return next
    })
    window.clearTimeout(closeTimers.current[id])
    closeTimers.current[id] = window.setTimeout(() => {
      setClosingFields((current) => {
        if (!current.has(id)) return current
        const next = new Set(current)
        next.delete(id)
        return next
      })
      delete closeTimers.current[id]
    }, 420)
  }

  function cancelClose(id: CanonicalField) {
    window.clearTimeout(closeTimers.current[id])
    delete closeTimers.current[id]
    setClosingFields((current) => {
      if (!current.has(id)) return current
      const next = new Set(current)
      next.delete(id)
      return next
    })
  }

  function closeFlyout() {
    if (!openField) return
    const id = openField
    setOpenField(null)
    beginClose(id)
  }

  function toggleFlyout(field: CanonicalField) {
    if (openField === field) {
      closeFlyout()
      return
    }
    if (openField) beginClose(openField)
    cancelClose(field)
    setOpenField(field)
  }

  useEffect(
    () => () => {
      Object.values(closeTimers.current).forEach((timer) => window.clearTimeout(timer))
    },
    [],
  )

  useEffect(() => {
    if (!openField) return
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
  }, [openField])

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
  const taken = new Set(
    Object.values(mapping).filter((column): column is string => Boolean(column)),
  )

  return (
    <div className="stack">
      <div className="lead">
        <h1>Проверьте колонки</h1>
        <Typography.Body variant="medium">Если поле назначено неверно — выберите другую колонку.</Typography.Body>
      </div>
      <CoverageBar coverage={coverage} />
      {error ? <Notice tone="error">{error}</Notice> : null}
      {warnings.map((warning) => (
        <Notice key={warning} tone="ok">{warning}</Notice>
      ))}
      <DataTable>
        <table>
          <thead>
            <tr>
              {upload.columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {upload.sample_rows.map((row, index) => (
              <tr key={index}>
                {upload.columns.map((column) => (
                  <td key={column}>{row[column] || '—'}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </DataTable>
      <div className="fields" ref={fieldsRef}>
        {MAPPING_FIELDS.map((field) => (
          <div key={field.id} className="field">
            <span className="field-head">
              <Typography.Body variant="medium-strong">{field.label}</Typography.Body>
              <span className="badge">{field.badge}</span>
            </span>
            <FlyoutSelect
              value={mapping[field.id] ?? ''}
              options={upload.columns
                .filter((column) => mapping[field.id] === column || !taken.has(column))
                .map((column) => ({ value: column, label: column }))}
              open={openField === field.id}
              closing={closingFields.has(field.id)}
              onToggle={() => toggleFlyout(field.id)}
              onChange={(column) => change(field.id, column)}
            />
            <Typography.Label variant="small">Пример: {exampleValue(upload.sample_rows, mapping[field.id])}</Typography.Label>
          </div>
        ))}
      </div>
      {ready ? null : (
        <Typography.Body variant="medium">Подтвердите сумму и дату или статус.</Typography.Body>
      )}
      <Button className="action action-primary" type="button" size="large" stretched variant="primary" disabled={!ready} loading={busy} onClick={() => void enlighten()}>
        Сделать снимок
      </Button>
    </div>
  )
}
