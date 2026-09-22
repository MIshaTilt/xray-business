import { Button } from '@maxhub/max-ui'
import { useEffect, useState } from 'react'
import { api, usesFixtures } from '../api/client.ts'
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
  const [busy, setBusy] = useState<'upload' | 'template' | null>(null)
  const [error, setError] = useState('')
  const [notice] = useState('')
  const [snapshots, setSnapshots] = useState<SnapshotListItem[]>([])

  // Template dropdown state
  const [templates, setTemplates] = useState<{ id: string; name: string; label: string; size_bytes: number }[]>([])
  const [showTemplatesDropdown, setShowTemplatesDropdown] = useState(false)

  async function refresh() {
    try {
      setSnapshots(await api.list())
    } catch (reason) {
      setError(errorText(reason))
    }
  }

  async function loadTemplatesList() {
    try {
      const items = await api.listTemplates()
      setTemplates(items)
    } catch {
      // fallback
    }
  }

  useEffect(() => {
    void refresh()
    void loadTemplatesList()
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

  async function selectTemplate(templateId: string) {
    setShowTemplatesDropdown(false)
    setBusy('template')
    setError('')
    try {
      const uploadResp = await api.loadTemplate(templateId)
      onUploaded(uploadResp)
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
    <div className="stack home">
      <header className="home-head">
        <h1>X-Ray</h1>
        <p className="home-sub">Где теряются деньги</p>
        <p className="home-hint">Таблица сделок за 30–90 дней</p>
      </header>
      {usesFixtures() ? <p className="home-hint">Сейчас ответы локальные: сервер для проверки экранов не нужен.</p> : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="ok">{notice}</Notice> : null}
      <div className="home-actions">
        <FileDrop file={file} busy={busy === 'upload'} onPick={setFile} onSend={() => void sendFile()} />
        <div className="template-dropdown-wrapper">
          <Button
            className="action action-secondary"
            type="button"
            size="large"
            stretched
            variant="secondary"
            loading={busy === 'template'}
            onClick={() => setShowTemplatesDropdown((val) => !val)}
          >
            Шаблон ▼
          </Button>

          {showTemplatesDropdown && (
            <div className="template-dropdown-menu">
              <div className="template-dropdown-header">Выберите готовый CSV:</div>
              {templates.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="template-item-btn"
                  onClick={() => void selectTemplate(t.id)}
                >
                  <span className="template-item-label">{t.label}</span>
                  <span className="template-item-filename">{t.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      {snapshots.length > 0 ? (
        <section className="history">
          <p className="eyebrow">История сканов</p>
          <ul className="scans">
            {snapshots.map((item) => (
              <li key={item.snapshot_id}>
                <button type="button" className="scan-card" onClick={() => void openSnapshot(item)}>
                  <span className="scan-top">
                    <span className="scan-meta">{shortWhen(item.created_at)} · {item.source || STATUS[item.status]}</span>
                    {item.verdict ? (
                      <span className={`pill ${item.verdict}`}>{verdictName(item.verdict)} · {item.coverage_label}</span>
                    ) : (
                      <span className={`pill ${item.status}`}>{STATUS[item.status]}</span>
                    )}
                  </span>
                  <span className="scan-title">{item.headline || 'Снимок без заключения'}</span>
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

function shortWhen(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  const date = match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : new Date(iso)
  if (Number.isNaN(date.getTime())) return formatWhen(iso)
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' }).format(date).replace('.', '')
}

function verdictName(verdict: 'critical' | 'watch' | 'ok'): string {
  if (verdict === 'critical') return 'критично'
  if (verdict === 'watch') return 'следить'
  return 'норма'
}
