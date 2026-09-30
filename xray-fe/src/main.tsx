import { MaxUI } from '@maxhub/max-ui'
import { Component, type ReactNode, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './app/App.tsx'
import '@maxhub/max-ui/dist/styles.css'
import './index.css'

// Prevent WebKit/WebView benign errors from triggering AppTracer fatal crash
const isBenign = (msg: unknown, err?: unknown) => {
  const s = String(
    msg ||
      (err && typeof err === 'object' && ('message' in err || 'name' in err)
        ? (err as { message?: string; name?: string }).message || (err as { name?: string }).name
        : '') ||
      '',
  )
  return (
    s.includes('ResizeObserver') ||
    s.includes('Transition was skipped') ||
    s.includes('AbortError') ||
    s.includes('InvalidStateError') ||
    s.includes('Script error.')
  )
}

window.addEventListener(
  'error',
  (event) => {
    if (isBenign(event.message, event.error)) {
      event.preventDefault()
      event.stopImmediatePropagation()
      return true
    }
  },
  true,
)

window.addEventListener(
  'unhandledrejection',
  (event) => {
    const reason = event.reason
    if (isBenign(reason && (reason.message || reason.name), reason)) {
      event.preventDefault()
      event.stopImmediatePropagation()
    }
  },
  true,
)

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  state: { hasError: boolean; error: Error | null } = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: unknown) {
    if (!isBenign(error.message, error)) {
      console.warn('[App Crash Caught]:', error, errorInfo)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, textAlign: 'center', color: '#172033', fontFamily: 'sans-serif' }}>
          <h2>Что-то пошло не так</h2>
          <p style={{ opacity: 0.7, fontSize: 14 }}>Произошла ошибка при загрузке экрана.</p>
          <button
            type="button"
            style={{
              marginTop: 16,
              padding: '10px 20px',
              borderRadius: 12,
              border: 'none',
              background: '#0d9488',
              color: '#fff',
              fontSize: 14,
              cursor: 'pointer',
            }}
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.href = '/'
            }}
          >
            Вернуться на главную
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <MaxUI colorScheme="light">
          <App />
        </MaxUI>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
