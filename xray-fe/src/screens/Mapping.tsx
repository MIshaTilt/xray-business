import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { Coverage, Mapping as MappingValue, UploadResponse } from '../api/types.ts'
import { canEnlighten, compactMapping, exampleValue, MAPPING_FIELDS } from '../domain/mapping.ts'
import { setClosingConfirmation } from '../bridge/index.ts'
import { CoverageBar } from '../widgets/CoverageBar.tsx'
import { DataTable } from '../widgets/DataTable.tsx'
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
  }

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
      <div className="fields">
        {MAPPING_FIELDS.map((field) => (
          <label key={field.id} className="field">
            <span className="field-head">
              <Typography.Body variant="medium-strong">{field.label}</Typography.Body>
              <span className="badge">{field.badge}</span>
            </span>
            <select
              value={mapping[field.id] ?? ''}
              onChange={(event) => change(field.id, event.target.value)}
            >
              <option value="">Не выбрано</option>
              {upload.columns.map((column) => (
                <option key={column} value={column}>
                  {column}
                </option>
              ))}
            </select>
            <Typography.Label variant="small">Пример: {exampleValue(upload.sample_rows, mapping[field.id])}</Typography.Label>
          </label>
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
