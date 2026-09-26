import { useEffect, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { UploadResponse } from '../api/types.ts'
import { Notice } from '../widgets/Notice.tsx'

export function Templates({ onPicked }: { onPicked: (upload: UploadResponse) => void }) {
  const [items, setItems] = useState<{ id: string; name: string; label: string }[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    void api.listTemplates().then(setItems).catch((reason) => setError(errorText(reason)))
  }, [])

  async function pick(id: string) {
    if (busy) return
    setBusy(id)
    setError('')
    try {
      onPicked(await api.loadTemplate(id))
    } catch (reason) {
      setError(errorText(reason))
      setBusy(null)
    }
  }

  return (
    <div className="stack templates-screen">
      <div className="lead">
        <h1>Шаблоны</h1>
        <p className="home-hint">Готовый CSV, чтобы сразу проверить колонки</p>
      </div>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <ul className="template-page-list">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className="settings-card template-page-item"
              disabled={Boolean(busy)}
              onClick={() => void pick(item.id)}
            >
              <span className="settings-copy">
                <strong>{item.label}</strong>
                <span>{item.name}</span>
              </span>
              {busy === item.id ? <span className="connector-status">Открываю…</span> : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
