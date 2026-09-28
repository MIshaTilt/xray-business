import { Button } from '@maxhub/max-ui'
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { api, usesFixtures } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import type { UploadResponse } from '../api/types.ts'
import { FileDrop } from '../widgets/FileDrop.tsx'
import { Notice } from '../widgets/Notice.tsx'
import { LogoAmo, LogoBitrix24, LogoMoySklad } from '../widgets/SourceLogos.tsx'
import { XRayLogo } from '../widgets/XRayLogo.tsx'

type SourceKind = 'amo' | 'bitrix' | 'moysklad'

export function Home({
  onUploaded,
  onTemplates,
  onCrmReady,
}: {
  onUploaded: (upload: UploadResponse) => void
  onTemplates: () => void
  onCrmReady: (snapshotId: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sheetError, setSheetError] = useState('')
  const [soon, setSoon] = useState('')
  const [amoOpen, setAmoOpen] = useState(false)
  const [amoClosing, setAmoClosing] = useState(false)
  const [source, setSource] = useState<SourceKind>('amo')
  const [amoAccount, setAmoAccount] = useState('')
  const [amoToken, setAmoToken] = useState('')
  const [bitrixUrl, setBitrixUrl] = useState('')
  const [msToken, setMsToken] = useState('')
  const [sheetFont, setSheetFont] = useState<CSSProperties>()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const amoTimer = useRef(0)
  const amoErrorText = useRef('')

  function closeAmo() {
    if (!amoOpen || amoClosing) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setAmoOpen(false)
      return
    }
    setAmoClosing(true)
    window.clearTimeout(amoTimer.current)
    amoTimer.current = window.setTimeout(() => {
      setAmoOpen(false)
      setAmoClosing(false)
    }, 420)
  }

  useEffect(() => {
    if (!amoOpen || amoClosing) return
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') closeAmo()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [amoOpen, amoClosing])

  useLayoutEffect(() => {
    if (!amoOpen) return
    const shell = document.querySelector('.app-shell')
    if (!(shell instanceof HTMLElement)) return
    const style = window.getComputedStyle(shell)
    setSheetFont({ fontFamily: style.fontFamily, fontSize: style.fontSize })
  }, [amoOpen])

  function openSource(kind: SourceKind) {
    if (amoClosing) return
    if (amoOpen && source === kind) {
      closeAmo()
      return
    }
    setSource(kind)
    setSheetError('')
    setAmoOpen(true)
    setAmoClosing(false)
  }

  async function connectSource() {
    setBusy(true)
    setSheetError('')
    try {
      const result =
        source === 'bitrix'
          ? await api.connectBitrix(bitrixUrl.trim())
          : source === 'moysklad'
            ? await api.connectMoySklad(msToken.trim())
            : await api.connectAmo(amoAccount.trim(), amoToken.trim())
      setAmoToken('')
      setMsToken('')
      setSheetError('')
      setAmoOpen(false)
      setAmoClosing(false)
      if (result.snapshot_id) onCrmReady(result.snapshot_id)
      else if (result.message) setSoon(result.message)
    } catch (reason) {
      const message = errorText(reason)
      amoErrorText.current = message
      setSheetError(message)
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
      <div className="home-actions">
        <p className="home-lead-in">Можно подключить базу данных</p>
        <div className="source-grid">
          <button
            type="button"
            className={`source-tile source-amo${amoOpen && source === 'amo' ? ' is-on' : ''}`}
            aria-label="Подключить amoCRM"
            aria-expanded={amoOpen && !amoClosing && source === 'amo'}
            onClick={() => openSource('amo')}
          >
            <span className="source-tile-icon" aria-hidden="true">
              <LogoAmo />
            </span>
            <span className="source-tile-name">amoCRM</span>
          </button>
          <button
            type="button"
            className={`source-tile source-bitrix${amoOpen && source === 'bitrix' ? ' is-on' : ''}`}
            aria-label="Подключить Битрикс24"
            aria-expanded={amoOpen && !amoClosing && source === 'bitrix'}
            onClick={() => openSource('bitrix')}
          >
            <span className="source-tile-icon" aria-hidden="true">
              <LogoBitrix24 />
            </span>
            <span className="source-tile-name">Битрикс24</span>
          </button>
          <button
            type="button"
            className={`source-tile source-moysklad${amoOpen && source === 'moysklad' ? ' is-on' : ''}`}
            aria-label="Подключить МойСклад"
            aria-expanded={amoOpen && !amoClosing && source === 'moysklad'}
            onClick={() => openSource('moysklad')}
          >
            <span className="source-tile-icon" aria-hidden="true">
              <LogoMoySklad />
            </span>
            <span className="source-tile-name">МойСклад</span>
          </button>
        </div>
        {soon ? <Notice tone="ok">{soon}</Notice> : null}
        {amoOpen
          ? createPortal(
              <div className={`download-sheet is-centered${amoClosing ? ' is-closing' : ''}`}>
                <button type="button" className="download-sheet-backdrop" aria-label="Закрыть" onClick={closeAmo} />
                <div className="amo-sheet-anchor" style={sheetFont}>
                  <p className={`amo-sheet-error${sheetError ? ' is-on' : ''}`} role="status">
                    {sheetError || amoErrorText.current}
                  </p>
                  <form
                    className="download-sheet-panel"
                    role="dialog"
                    aria-label={sheetTitle(source)}
                    onSubmit={(event) => {
                      event.preventDefault()
                      void connectSource()
                    }}
                  >
                    <p className="download-sheet-title">{sheetTitle(source)}</p>
                    {source === 'amo' ? (
                      <>
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
                      </>
                    ) : null}
                    {source === 'bitrix' ? (
                      <input
                        className="amo-input"
                        placeholder="https://имя.bitrix24.ru/rest/1/код/"
                        value={bitrixUrl}
                        onChange={(event) => setBitrixUrl(event.target.value)}
                        autoComplete="off"
                      />
                    ) : null}
                    {source === 'moysklad' ? (
                      <input
                        className="amo-input"
                        placeholder="Bearer-токен МоегоСклада"
                        value={msToken}
                        onChange={(event) => setMsToken(event.target.value)}
                        autoComplete="off"
                        type="password"
                      />
                    ) : null}
                    <button
                      type="submit"
                      className="amo-connect"
                      disabled={busy}
                      onPointerDown={(event) => {
                        const node = event.currentTarget
                        node.classList.remove('is-drop')
                        void node.offsetWidth
                        node.classList.add('is-drop')
                        window.setTimeout(() => node.classList.remove('is-drop'), 360)
                      }}
                    >
                      <span className="amo-connect-label">
                        <span className={busy ? 'is-out' : 'is-in'}>Подключиться</span>
                        <span className={busy ? 'is-in' : 'is-out'}>Подключаемся…</span>
                      </span>
                    </button>
                  </form>
                </div>
              </div>,
              document.body,
            )
          : null}
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

function sheetTitle(source: SourceKind): string {
  if (source === 'bitrix') return 'Подключить Битрикс24'
  if (source === 'moysklad') return 'Подключить МойСклад'
  return 'Подключить amoCRM'
}
