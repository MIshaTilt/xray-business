import { Button } from '@maxhub/max-ui'
import { useEffect, useRef, useState } from 'react'
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
  onAmoReady,
}: {
  onUploaded: (upload: UploadResponse) => void
  onTemplates: () => void
  onAmoReady: (snapshotId: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [soon, setSoon] = useState('')
  const [amoOpen, setAmoOpen] = useState(false)
  const [amoAccount, setAmoAccount] = useState('')
  const [amoToken, setAmoToken] = useState('')
  const [amoAccountName, setAmoAccountName] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (usesFixtures()) return
    api.amoStatus().then((status) => {
      if (status.connected && status.account) setAmoAccountName(status.account)
    }).catch(() => undefined)
  }, [])

  async function connectAmo() {
    setBusy(true)
    setError('')
    try {
      const result = await api.connectAmo(amoAccount.trim(), amoToken.trim())
      setAmoAccountName(result.account)
      setAmoToken('')
      setAmoOpen(false)
      if (result.snapshot_id) onAmoReady(result.snapshot_id)
      else setSoon(result.message || 'Кабинет подключен. В сделках пока нет бюджета.')
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(false)
    }
  }

  async function refreshAmo() {
    setBusy(true)
    setError('')
    try {
      const result = await api.syncAmo()
      onAmoReady(result.snapshot_id)
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusy(false)
    }
  }

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
        <Button
          className="action action-secondary"
          type="button"
          size="large"
          stretched
          variant="secondary"
          onClick={() => setAmoOpen((open) => !open)}
        >
          Подключить amoCRM
        </Button>
        {amoOpen ? (
          <form
            className="amo-form"
            onSubmit={(event) => {
              event.preventDefault()
              void connectAmo()
            }}
          >
            <input
              className="amo-input"
              placeholder="Поддомен, например demo"
              value={amoAccount}
              onChange={(event) => setAmoAccount(event.target.value)}
              autoComplete="off"
            />
            <input
              className="amo-input"
              placeholder="Долгосрочный токен"
              value={amoToken}
              onChange={(event) => setAmoToken(event.target.value)}
              autoComplete="off"
              type="password"
            />
            <Button className="action action-primary" type="submit" size="large" stretched variant="primary" disabled={busy}>
              {busy ? 'Читаем сделки…' : 'Забрать сделки из amoCRM'}
            </Button>
          </form>
        ) : null}
        {amoAccountName ? (
          <Button className="action action-secondary" type="button" size="large" stretched variant="secondary" disabled={busy} onClick={() => void refreshAmo()}>
            Обновить {amoAccountName}
          </Button>
        ) : null}
        <FileDrop
          file={file}
          busy={busy}
          hideButton
          inputRef={fileInputRef}
          onPick={setFile}
          onClear={() => setFile(null)}
          onSend={() => void sendFile()}
        />
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
