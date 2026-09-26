import { Button } from '@maxhub/max-ui'
import { useRef, useState } from 'react'
import { api, usesFixtures } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { UploadResponse } from '../api/types.ts'
import { FileDrop } from '../widgets/FileDrop.tsx'
import { Notice } from '../widgets/Notice.tsx'
import { Logo1C, LogoBitrix24, LogoMoySklad } from '../widgets/SourceLogos.tsx'
import { XRayLogo } from '../widgets/XRayLogo.tsx'

export function Home({
  onUploaded,
  onTemplates,
}: {
  onUploaded: (upload: UploadResponse) => void
  onTemplates: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [soon, setSoon] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  async function sendFile() {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      onUploaded(await api.upload(file))
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack home">
      <header className="home-head">
        <div className="home-brand">
          <XRayLogo />
          <h1>X-Ray</h1>
        </div>
        <p className="home-sub">Где теряются деньги</p>
        <p className="home-hint">Таблица сделок за 30–90 дней</p>
      </header>
      {usesFixtures() ? <p className="home-hint">Сейчас ответы локальные: сервер для проверки экранов не нужен.</p> : null}
      {error ? <Notice tone="error">{error}</Notice> : null}
      {soon ? <Notice tone="ok">{soon}</Notice> : null}
      <div className="home-actions">
        <p className="home-lead-in">Можно подключить базу данных</p>
        <div className="source-grid">
          <button type="button" className="source-tile source-1c" onClick={() => setSoon('Подключение 1С скоро появится')}>
            <span className="source-tile-icon" aria-hidden="true">
              <Logo1C />
            </span>
            <span className="source-tile-label">1С</span>
          </button>
          <button type="button" className="source-tile source-bitrix" onClick={() => setSoon('Подключение Битрикс24 скоро появится')}>
            <span className="source-tile-icon" aria-hidden="true">
              <LogoBitrix24 />
            </span>
            <span className="source-tile-label">Битрикс24</span>
          </button>
          <button type="button" className="source-tile source-moysklad" onClick={() => setSoon('Подключение МойСклад скоро появится')}>
            <span className="source-tile-icon" aria-hidden="true">
              <LogoMoySklad />
            </span>
            <span className="source-tile-label">МойСклад</span>
          </button>
        </div>
        {file ? null : <p className="home-or">или</p>}
        {file ? null : (
          <Button
            className="action action-primary"
            type="button"
            size="large"
            stretched
            variant="primary"
            onClick={() => fileInputRef.current?.click()}
          >
            Загрузить файл CSV
          </Button>
        )}
        <FileDrop
          file={file}
          busy={busy}
          hideButton
          inputRef={fileInputRef}
          onPick={setFile}
          onClear={() => setFile(null)}
          onSend={() => void sendFile()}
        />
        <Button
          className="action action-secondary"
          type="button"
          size="large"
          stretched
          variant="secondary"
          onClick={onTemplates}
        >
          Шаблоны
        </Button>
      </div>
    </div>
  )
}
