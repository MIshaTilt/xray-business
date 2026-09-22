import { Button, Typography } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, downloadTemplate, usesFixtures } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { SnapshotListItem, UploadResponse } from '../api/types.ts'
import { formatWhen } from '../domain/metrics.ts'
import { FileDrop } from '../widgets/FileDrop.tsx'
import { Notice } from '../widgets/Notice.tsx'

const STATUS: Record<SnapshotListItem['status'], string> = {
  processing: 'Считаем',
  ready: 'Готово',
  failed: 'Не вышло',
}

export function Home({
  onUploaded,
  onDiagnosis,
  onProcessing,
}: {
  onUploaded: (upload: UploadResponse) => void
  onDiagnosis: (snapshotId: string) => void
  onProcessing: (snapshotId: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState<'upload' | 'demo' | 'template' | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [snapshots, setSnapshots] = useState<SnapshotListItem[]>([])

  async function refresh() {
    try {
      setSnapshots(await api.list())
    } catch (reason) {
      setError(errorText(reason))
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function sendFile() {
    if (!file) return
    setBusy('upload')
    setError('')
    try {
      onUploaded(await api.upload(file))
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(null)
    }
  }

  async function openDemo() {
    setBusy('demo')
    setError('')
    try {
      const diagnosis = await api.demo()
      onDiagnosis(diagnosis.snapshot_id)
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(null)
    }
  }

  async function saveTemplate() {
    setBusy('template')
    setError('')
    try {
      await downloadTemplate()
      setNotice('Шаблон сохранён как xray-template.xlsx')
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(null)
    }
  }

  async function openSnapshot(item: SnapshotListItem) {
    setError('')
    if (item.status === 'ready') {
      onDiagnosis(item.snapshot_id)
      return
    }
    if (item.status === 'processing') {
      onProcessing(item.snapshot_id)
      return
    }
    try {
      const poll = await api.poll(item.snapshot_id)
      setError(poll.error || 'Этот снимок не посчитался. Загрузите таблицу ещё раз.')
    } catch (reason) {
      setError(errorText(reason))
    }
  }

  async function removeSnapshot(id: string) {
    setError('')
    try {
      await api.remove(id)
      setSnapshots((current) => current.filter((item) => item.snapshot_id !== id))
    } catch (reason) {
      setError(errorText(reason))
    }
  }

  return (
    <div className="stack">
      <div className="hero">
        <div className="mark" aria-hidden="true">
          <span className="mark-line" />
        </div>
        <div className="lead">
          <Typography.Label variant="small-strong">Рентген продаж</Typography.Label>
          <Typography.Display>X-Ray</Typography.Display>
          <Typography.Body variant="medium">
            Загрузите таблицу сделок — покажем, где теряются деньги.
          </Typography.Body>
        </div>
      </div>
      {usesFixtures() ? (
        <Typography.Label variant="small">Сейчас ответы локальные: сервер для проверки экранов не нужен.</Typography.Label>
      ) : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="ok">{notice}</Notice> : null}
      <FileDrop file={file} busy={busy === 'upload'} onPick={setFile} onSend={() => void sendFile()} />
      <Button className="action action-secondary" type="button" size="large" stretched variant="secondary" loading={busy === 'demo'} onClick={() => void openDemo()}>
        Открыть демо
      </Button>
      <Button className="action action-quiet" type="button" size="large" stretched variant="ghost" loading={busy === 'template'} onClick={() => void saveTemplate()}>
        Скачать шаблон
      </Button>
      {snapshots.length > 0 ? (
        <section className="history">
          <Typography.Label variant="medium-strong">Прошлые снимки</Typography.Label>
          <ul>
            {snapshots.map((item) => (
              <li key={item.snapshot_id}>
                <button type="button" className="history-main" onClick={() => void openSnapshot(item)}>
                  <span className={`pill ${item.status}`}>{STATUS[item.status]}</span>
                  <span className="history-title">{item.headline || 'Снимок без заключения'}</span>
                  <span className="history-meta">{formatWhen(item.created_at)}</span>
                </button>
                <button type="button" className="history-delete" onClick={() => void removeSnapshot(item.snapshot_id)}>
                  Удалить
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
