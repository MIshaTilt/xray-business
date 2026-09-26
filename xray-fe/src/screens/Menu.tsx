import { useMemo } from 'react'
import { getMaxUser, getPlatform, isInsideMax } from '../bridge/index.ts'
import { ThemeToggle } from '../widgets/ThemeToggle.tsx'

const CONNECTORS = [
  { id: '1c', title: '1С', hint: 'Обмен справочниками и сделками' },
  { id: 'bitrix', title: 'Битрикс24', hint: 'Воронка и менеджеры из CRM' },
  { id: 'moysklad', title: 'МойСклад', hint: 'Отгрузки и остатки' },
] as const

export function Menu({
  dark,
  themePlayed,
  onToggleTheme,
}: {
  dark: boolean
  themePlayed: boolean
  onToggleTheme: () => void
}) {
  const user = useMemo(() => getMaxUser(), [])
  const name = user
    ? [user.first_name, user.last_name].filter(Boolean).join(' ')
    : 'Гость'
  const initials = user ? initialsOf(name) : 'XR'
  const platform = platformLabel(getPlatform())
  const inside = isInsideMax()

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
        <ThemeToggle dark={dark} played={themePlayed} onToggle={onToggleTheme} />
      </div>

      <p className="eyebrow">Подключения</p>
      <ul className="connector-list">
        {CONNECTORS.map((item) => (
          <li key={item.id} className="settings-card connector-card">
            <div className="settings-copy">
              <strong>{item.title}</strong>
              <span>{item.hint}</span>
            </div>
            <span className="connector-status">Скоро</span>
          </li>
        ))}
      </ul>
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
