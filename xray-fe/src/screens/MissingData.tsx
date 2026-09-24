import { useEffect, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { MetricId } from '../api/types.ts'
import { METRICS } from '../domain/metrics.ts'
import { Notice } from '../widgets/Notice.tsx'

export function MissingData({ snapshotId }: { snapshotId: string }) {
  const [skipped, setSkipped] = useState<MetricId[]>([])
  const [scanNo, setScanNo] = useState<number | undefined>()
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    void api
      .diagnosis(snapshotId)
      .then((result) => {
        if (!alive) return
        setSkipped(result.coverage.skipped)
        setScanNo(result.scan_no)
      })
      .catch((reason: unknown) => {
        if (alive) setError(errorText(reason))
      })
    return () => {
      alive = false
    }
  }, [snapshotId])

  return (
    <div className="stack">
      <div className="lead">
        <h1>
          {scanNo ? `Чего не хватило по снимку №${scanNo}` : 'Чего не хватило'}
        </h1>
        <p className="home-hint">Показатели, которые не посчитались: в таблице нет нужных колонок.</p>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {skipped.length === 0 ? (
        <p className="home-hint">Все семь показателей посчитаны.</p>
      ) : (
        <div className="findings missing-list">
          {skipped.map((id) => (
            <article key={id} className="finding skipped">
              <div className="finding-open">
                <span className="pill skipped">не посчитано</span>
                <strong className="finding-fact">{METRICS[id].title}</strong>
                <p className="finding-text">{METRICS[id].hint}</p>
                <span className="finding-title">Нужно: {METRICS[id].needs}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
