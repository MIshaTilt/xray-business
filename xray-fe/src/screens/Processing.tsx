import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import { Notice } from '../widgets/Notice.tsx'

export function Processing({
  snapshotId,
  onReady,
  onBack,
  onFailed,
}: {
  snapshotId: string
  onReady: () => void
  onBack: () => void
  onFailed: () => void
}) {
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
        if (poll.status === 'ready') {
          finished.current = true
          onReadyRef.current()
        }
        if (poll.status === 'failed') {
          if (!finished.current) onFailed()
          finished.current = true
          setError(poll.error || 'Снимок не посчитался')
        }
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

  if (!error) return null

  return (
    <div className="stack">
      <Typography.Title variant="medium-strong">Снимок не собрался</Typography.Title>
      <Notice tone="error">{error}</Notice>
      <Button className="action action-secondary" type="button" size="large" stretched variant="secondary" onClick={onBack}>
        Вернуться к колонкам
      </Button>
    </div>
  )
}
