import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client.ts'
import { errorText } from '../api/errors.ts'
import { getMaxUser, getPlatform, isInsideMax } from '../bridge/index.ts'
import { Notice } from '../widgets/Notice.tsx'
import { ThemeToggle } from '../widgets/ThemeToggle.tsx'

type SessionKind = 'amo' | 'bitrix' | 'moysklad'

type CrmSession = {
  key: string
  id: number
  kind: SessionKind
  label: string
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
  const [sessions, setSessions] = useState<CrmSession[] | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    Promise.all([
      api.amoSessions().catch(() => ({ sessions: [] as { id: number; account: string; last_error: string }[] })),
      api.bitrixSessions().catch(() => ({ sessions: [] as { id: number; account: string; last_error: string }[] })),
      api.moyskladSessions().catch(() => ({ sessions: [] as { id: number; account: string; last_error: string }[] })),
    ]).then(([amo, bitrix, moysklad]) => {
      if (!alive) return
      setSessions([
        ...asSessions(amo.sessions, 'amo', 'amoCRM'),
        ...asSessions(bitrix.sessions, 'bitrix', 'Битрикс24'),
        ...asSessions(moysklad.sessions, 'moysklad', 'МойСклад'),
      ])
    })
    return () => {
      alive = false
    }
  }, [])

  async function fetchDeals(session: CrmSession) {
    setBusyKey(session.key)
    setError('')
    try {
      const result =
        session.kind === 'bitrix'
          ? await api.syncBitrix(session.id)
          : session.kind === 'moysklad'
            ? await api.syncMoySklad(session.id)
            : await api.syncAmo(session.id)
      onOpenSnapshot(result.snapshot_id)
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusyKey(null)
    }
  }

  async function removeSession(session: CrmSession) {
    setBusyKey(session.key)
    setError('')
    try {
      if (session.kind === 'bitrix') await api.deleteBitrix(session.id)
      else if (session.kind === 'moysklad') await api.deleteMoySklad(session.id)
      else await api.deleteAmo(session.id)
      setSessions((current) => (current ?? []).filter((item) => item.key !== session.key))
    } catch (reason) {
      setError(errorText(reason))
    } finally {
      setBusyKey(null)
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
            <li key={session.key} className="settings-card connector-card">
              <div className="settings-copy">
                <strong>{session.label}</strong>
                <span>{session.account}</span>
                {session.last_error ? <span>{session.last_error}</span> : null}
              </div>
              <div className="session-actions">
                <button
                  type="button"
                  className="session-fetch"
                  disabled={busyKey === session.key}
                  onClick={() => void fetchDeals(session)}
                >
                  {busyKey === session.key ? 'Читаем…' : 'Забрать сделки'}
                </button>
                <button
                  type="button"
                  className="session-delete"
                  disabled={busyKey === session.key}
                  onClick={() => void removeSession(session)}
                >
                  Удалить
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function asSessions(
  items: { id: number; account: string; last_error: string }[],
  kind: SessionKind,
  label: string,
): CrmSession[] {
  return items.map((item) => ({
    key: `${kind}-${item.id}`,
    id: item.id,
    kind,
    label,
    account: item.account,
    last_error: item.last_error,
  }))
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
