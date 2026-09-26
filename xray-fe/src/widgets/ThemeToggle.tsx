export function ThemeToggle({
  dark,
  played,
  onToggle,
}: {
  dark: boolean
  played: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      className={`theme-btn${dark ? ' is-dark' : ''}${played ? ' is-played' : ''}`}
      aria-label={dark ? 'Светлая тема' : 'Ночная тема'}
      onClick={onToggle}
    >
      <span className="theme-sky" aria-hidden="true">
        <span className="theme-moon">
          <span className="theme-glyph">
            <svg viewBox="0 0 24 24">
              <path d="M18.52 14.81A6.9 6.9 0 1 1 10.84 5.24 6.21 6.21 0 1 0 18.52 14.81Z" />
            </svg>
          </span>
        </span>
        <span className="theme-sun">
          <span className="theme-glyph">
            <svg viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="4" />
              <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5 5l1.6 1.6M17.4 17.4 19 19M19 5l-1.6 1.6M6.6 17.4 5 19" />
            </svg>
          </span>
        </span>
      </span>
    </button>
  )
}
