import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import { getMaxUser, getPlatform, isInsideMax } from '../bridge/index.ts'
import { Notice } from '../widgets/Notice.tsx'
import { ThemeToggle } from '../widgets/ThemeToggle.tsx'

type AmoSession = {
  id: number
  account: string
  last_error: string
}

export function Menu({
  dark,
  onToggleTheme,
  onOpenSnapshot,
}: {
  dark: boolean
  onToggleTheme: () => void
  onOpenSnapshot: (snapshotId: string) => void
}) {
  const user = useMemo(() => getMaxUser(), [])
  const name = user
    ? [user.first_name, user.last_name].filter(Boolean).join(' ')
    : 'Гость'
  const initials = user ? initialsOf(name) : 'XR'
  const platform = platformLabel(getPlatform())
  const inside = isInsideMax()
  const [sessions, setSessions] = useState<AmoSession[] | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api.amoSessions()
      .then((payload) => {
        if (alive) setSessions(payload.sessions)
      })
      .catch(() => {
        if (alive) setSessions([])
      })
    return () => {
      alive = false
    }
  }, [])

  async function fetchDeals(session: AmoSession) {
    setBusyId(session.id)
    setError('')
    try {
      const result = await api.syncAmo(session.id)
      onOpenSnapshot(result.snapshot_id)
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="stack menu-screen">
      <div className="lead">
        <h1>Меню</h1>
      </div>

      <section className="settings-card profile-card">
        {user?.photo_url ? (
          <img className="profile-avatar" src={user.photo_url} alt="" />
        ) : (
          <span className="profile-avatar is-fallback" aria-hidden="true">
            {initials}
          </span>
        )}
        <div className="settings-copy">
          <strong>{name}</strong>
          <span>
            {user?.username ? `@${user.username}` : inside ? 'Аккаунт MAX' : 'Откройте в MAX, чтобы увидеть профиль'}
          </span>
          <span className="profile-meta">
            {user ? `ID ${user.id}` : 'Без авторизации'}
            {` · ${platform}`}
          </span>
        </div>
      </section>

      <p className="eyebrow">Оформление</p>
      <div className="settings-card">
        <div className="settings-copy">
          <strong>Тема</strong>
          <span>{dark ? 'Ночная' : 'Светлая'}</span>
        </div>
        <ThemeToggle dark={dark} onToggle={onToggleTheme} />
      </div>

      <p className="eyebrow">Активные сессии</p>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {sessions && sessions.length === 0 ? (
        <p className="session-empty">Нет активных сессий</p>
      ) : (
        <ul className="connector-list">
          {(sessions ?? []).map((session) => (
            <li key={session.id} className="settings-card connector-card">
              <div className="settings-copy">
                <strong>amoCRM</strong>
                <span>{session.account}</span>
                {session.last_error ? <span>{session.last_error}</span> : null}
              </div>
              <button
                type="button"
                className="session-fetch"
                disabled={busyId === session.id}
                onClick={() => void fetchDeals(session)}
              >
                {busyId === session.id ? 'Читаем…' : 'Забрать сделки'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'XR'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
}

function platformLabel(platform: string): string {
  if (platform === 'ios') return 'iOS'
  if (platform === 'android') return 'Android'
  if (platform === 'desktop') return 'MAX Desktop'
  return 'Браузер'
}
