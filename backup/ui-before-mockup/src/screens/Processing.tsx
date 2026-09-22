import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import { Notice } from '../widgets/Notice.tsx'

export function Processing({
  snapshotId,
  onReady,
  onBack,
}: {
  snapshotId: string
  onReady: () => void
  onBack: () => void
}) {
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const onReadyRef = useRef(onReady)
  const finished = useRef(false)
  onReadyRef.current = onReady

  useEffect(() => {
    let stopped = false
    async function tick() {
      try {
        const poll = await api.poll(snapshotId)
        if (stopped || finished.current) return
        setProgress(poll.progress)
        if (poll.status === 'ready') {
          finished.current = true
          onReadyRef.current()
        }
        if (poll.status === 'failed') setError(poll.error || 'Снимок не посчитался')
      } catch (reason) {
        if (!stopped) setError(errorText(reason))
      }
    }
    void tick()
    const timer = window.setInterval(() => void tick(), 1000)
    return () => {
      stopped = true
      window.clearInterval(timer)
    }
  }, [snapshotId])

  return (
    <div className="stack">
      <Typography.Title variant="medium-strong">Просвечиваем сделки</Typography.Title>
      {error ? (
        <>
          <Notice tone="error">{error}</Notice>
          <Button className="action action-secondary" type="button" size="large" stretched variant="secondary" onClick={onBack}>
            Вернуться к колонкам
          </Button>
        </>
      ) : (
        <>
          <div className="scan" aria-hidden="true">
            <span className="scan-ring" />
            <span className="scan-line" />
          </div>
          <Typography.Body variant="medium">Сверяем суммы, статусы и даты. Это займёт несколько секунд.</Typography.Body>
          <div className="progress-track" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} role="progressbar">
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
          <Typography.Label variant="small">{progress}%</Typography.Label>
        </>
      )}
    </div>
  )
}
