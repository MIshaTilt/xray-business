import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, downloadTemplate } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { MetricId } from '../api/types.ts'
import { METRICS } from '../domain/metrics.ts'
import { Notice } from '../widgets/Notice.tsx'

export function MissingData({ snapshotId }: { snapshotId: string }) {
  const [skipped, setSkipped] = useState<MetricId[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let alive = true
    void api
      .diagnosis(snapshotId)
      .then((result) => {
        if (alive) setSkipped(result.coverage.skipped)
      })
      .catch((reason: unknown) => {
        if (alive) setError(errorText(reason))
      })
    return () => {
      alive = false
    }
  }, [snapshotId])

  async function saveTemplate() {
    setBusy(true)
    setError('')
    try {
      await downloadTemplate()
      setSaved(true)
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <div className="lead">
        <Typography.Title variant="medium-strong">Чего не хватило</Typography.Title>
        <Typography.Body variant="medium">Диагноз уже построен по тем колонкам, что есть. Ниже — что откроет остальные метрики.</Typography.Body>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {saved ? <Notice tone="ok">Шаблон сохранён как xray-template.xlsx</Notice> : null}
      {skipped.length === 0 ? (
        <Typography.Body variant="medium">Все семь метрик посчитаны. Добавлять колонки не нужно.</Typography.Body>
      ) : (
        <div className="fields">
          {skipped.map((id) => (
            <article key={id} className="field">
              <Typography.Body variant="medium-strong">{METRICS[id].title}</Typography.Body>
              <Typography.Label variant="small">Нужно: {METRICS[id].needs}</Typography.Label>
              <Typography.Body variant="medium">{METRICS[id].hint}</Typography.Body>
            </article>
          ))}
        </div>
      )}
      <Button className="action action-primary" type="button" size="large" stretched variant="primary" loading={busy} onClick={() => void saveTemplate()}>
        Скачать шаблон
      </Button>
    </div>
  )
}
