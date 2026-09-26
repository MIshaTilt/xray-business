import { Panel } from '@maxhub/max-ui'
import { useCallback, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router'
import type { Diagnosis as DiagnosisData, MetricId } from '../api/types.ts'
import { api } from '../api/client.ts'
import { bindBack, getPlatform, initBridge, showBack } from '../bridge/index.ts'
import { dealsAsTable } from '../domain/platform.ts'
import { ChatScreen } from '../screens/ChatScreen.tsx'
import { Diagnosis } from '../screens/Diagnosis.tsx'
import { Home } from '../screens/Home.tsx'
import { MappingScreen } from '../screens/Mapping.tsx'
import { MetricDetail } from '../screens/MetricDetail.tsx'
import { MissingData } from '../screens/MissingData.tsx'
import { Processing } from '../screens/Processing.tsx'
import { Menu } from '../screens/Menu.tsx'
import { Scans } from '../screens/Scans.tsx'
import { Templates } from '../screens/Templates.tsx'
import { AnalyzeVeil } from '../widgets/AnalyzeVeil.tsx'
import { LiveWallpaper } from '../widgets/LiveWallpaper.tsx'
import { FlowProvider, useFlow } from './flow.tsx'
import { go, tabOf } from './nav.ts'

const METRICS: MetricId[] = [
  'speed_to_lead',
  'stagnation',
  'discount_leakage',
  'sales_cycle',
  'key_account_risk',
  'dormant',
  'funnel_dropoff',
]

export function App() {
  return (
    <FlowProvider>
      <Shell />
    </FlowProvider>
  )
}

function Shell() {
  const location = useLocation()
  const navigate = useNavigate()
  const flow = useFlow()
  const [hostBack, setHostBack] = useState(false)
  const wide = dealsAsTable(getPlatform())
  const tab = tabOf(location.pathname)
  const inChat = location.pathname.endsWith('/chat')
  const nested =
    /\/scan\/[^/]+\/(metric|missing|chat)/.test(location.pathname) ||
    location.pathname.startsWith('/processing/')
  const showBackBtn =
    !hostBack && (nested || location.pathname.startsWith('/mapping') || location.pathname.startsWith('/templates'))
  const showTabs = !flow.veil && !flow.veilLeaving

  useEffect(() => {
    document.documentElement.dataset.scene = inChat ? 'chat' : 'home'
  }, [inChat])

  useEffect(() => {
    initBridge()
    setHostBack(Boolean(window.WebApp?.initData && window.WebApp.BackButton))
  }, [])

  useEffect(() => {
    const reset = () => {
      window.scrollTo(0, 0)
      document.documentElement.scrollTop = 0
      document.body.scrollTop = 0
      document.querySelectorAll('.app-panel, #root').forEach((node) => {
        node.scrollTop = 0
      })
    }
    reset()
    const frame = window.requestAnimationFrame(reset)
    return () => window.cancelAnimationFrame(frame)
  }, [location.pathname])

  const pop = useCallback(() => {
    if (location.key === 'default') {
      go(navigate, '/')
      return
    }
    go(navigate, -1)
  }, [location.key, navigate])

  useEffect(() => {
    if (!showBackBtn) {
      showBack(false)
      return
    }
    showBack(true)
    return bindBack(pop)
  }, [pop, showBackBtn])

  return (
    <Panel mode="secondary" className="app-panel">
      <LiveWallpaper />
      <main
        className={`${wide ? 'app-shell wide' : 'app-shell'}${showBackBtn ? ' with-back' : ''}${showTabs ? ' with-tabs' : ''}${inChat ? ' is-chat' : ''}`}
      >
        <div className="nav-bar">
          {showBackBtn ? (
            <button type="button" className="back" aria-label="Назад" onClick={pop}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14.5 6.5 9 12l5.5 5.5" />
              </svg>
              <span>Назад</span>
            </button>
          ) : null}
          {inChat ? <div className="chat-nav-actions" id="chat-nav-actions" /> : null}
        </div>
        {showBackBtn ? <div className="back-spacer" aria-hidden="true" /> : null}

        <div className="page-stage">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/templates" element={<TemplatesPage />} />
            <Route path="/scans" element={<ScansPage />} />
            <Route path="/chat" element={<ChatGatePage />} />
            <Route path="/menu" element={<MenuPage />} />
            <Route path="/settings" element={<Navigate to="/menu" replace />} />
            <Route path="/mapping" element={<MappingPage />} />
            <Route path="/processing/:snapshotId" element={<ProcessingPage />} />
            <Route path="/scan" element={<Navigate to="/scans" replace />} />
            <Route path="/scan/:snapshotId" element={<DiagnosisPage />} />
            <Route path="/scan/:snapshotId/metric/:metricId" element={<MetricPage />} />
            <Route path="/scan/:snapshotId/missing" element={<MissingPage />} />
            <Route path="/scan/:snapshotId/chat" element={<ChatPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>

        {flow.veil || flow.veilLeaving ? (
          <AnalyzeVeil
            leaving={flow.veilLeaving}
            phase={
              location.pathname.startsWith('/processing/')
                ? 'processing'
                : location.pathname.startsWith('/scan/')
                  ? 'diagnosis'
                  : 'mapping'
            }
          />
        ) : null}

        {showTabs ? (
          <nav className="tab-bar" aria-label="Навигация">
            <button type="button" className={`tab-item${tab === 'home' ? ' is-on' : ''}`} onClick={() => go(navigate, '/')}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 11.2 12 5l8 6.2" />
                <path d="M7.5 10.8V19h9v-8.2" />
              </svg>
              Главная
            </button>
            <button
              type="button"
              className={`tab-item${tab === 'scans' ? ' is-on' : ''}`}
              onClick={() => go(navigate, '/scans')}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="5" y="4.5" width="14" height="15" rx="2.2" />
                <path d="M8 9h8M8 12.5h8M8 16h5" />
              </svg>
              Сканы
            </button>
            <button
              type="button"
              className={`tab-item tab-chat${tab === 'chat' ? ' is-on' : ''}`}
              onClick={() => go(navigate, flow.lastScanId ? `/scan/${flow.lastScanId}/chat` : '/chat')}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 6.5h14v9.5H9.2L5 19.2V6.5Z" />
                <path d="M8.5 10h7M8.5 13h4.5" />
              </svg>
              Чат
            </button>
            <button
              type="button"
              className={`tab-item${tab === 'menu' ? ' is-on' : ''}`}
              onClick={() => go(navigate, '/menu')}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 7h14M5 12h14M5 17h14" />
              </svg>
              Меню
            </button>
          </nav>
        ) : null}
      </main>
    </Panel>
  )
}

function HomePage() {
  const navigate = useNavigate()
  const flow = useFlow()
  return (
    <Home
      onUploaded={(upload) => {
        flow.setUpload(upload)
        go(navigate, '/mapping')
      }}
      onTemplates={() => go(navigate, '/templates')}
    />
  )
}

function TemplatesPage() {
  const navigate = useNavigate()
  const flow = useFlow()
  return (
    <Templates
      onPicked={(upload) => {
        flow.setUpload(upload)
        go(navigate, '/mapping')
      }}
    />
  )
}

function ScansPage() {
  const navigate = useNavigate()
  const flow = useFlow()
  return (
    <Scans
      onDiagnosis={(snapshotId) => {
        flow.setLastScanId(snapshotId)
        go(navigate, `/scan/${snapshotId}`)
      }}
      onProcessing={(snapshotId) => {
        flow.setLastScanId(snapshotId)
        go(navigate, `/processing/${snapshotId}`)
      }}
    />
  )
}

function ChatGatePage() {
  const flow = useFlow()
  if (flow.lastScanId) return <Navigate to={`/scan/${flow.lastScanId}/chat`} replace />
  return (
    <div className="stack">
      <div className="lead">
        <h1>Чат</h1>
        <p className="home-hint">Сначала откройте снимок в разделе «Сканы».</p>
      </div>
    </div>
  )
}

function MenuPage() {
  const flow = useFlow()
  return <Menu dark={flow.dark} themePlayed={flow.themePlayed} onToggleTheme={flow.toggleTheme} />
}

function MappingPage() {
  const navigate = useNavigate()
  const flow = useFlow()
  if (!flow.upload) return <Navigate to="/" replace />
  return (
    <MappingScreen
      upload={flow.upload}
      onAnalyze={flow.beginVeil}
      onAnalyzeStop={flow.stopVeil}
      onStart={(snapshotId) => {
        flow.setLastScanId(snapshotId)
        go(navigate, `/processing/${snapshotId}`, { replace: true })
      }}
    />
  )
}

function ProcessingPage() {
  const { snapshotId = '' } = useParams()
  const navigate = useNavigate()
  const flow = useFlow()
  return (
    <Processing
      snapshotId={snapshotId}
      onReady={() => go(navigate, `/scan/${snapshotId}`, { replace: true })}
      onBack={() => go(navigate, flow.upload ? '/mapping' : '/')}
      onFailed={flow.stopVeil}
    />
  )
}

function DiagnosisPage() {
  const { snapshotId = '' } = useParams()
  const navigate = useNavigate()
  const { setLastScanId, finishVeil } = useFlow()
  const wide = dealsAsTable(getPlatform())
  useEffect(() => {
    setLastScanId(snapshotId)
  }, [setLastScanId, snapshotId])
  return (
    <Diagnosis
      snapshotId={snapshotId}
      wide={wide}
      onMetric={(metricId) => go(navigate, `/scan/${snapshotId}/metric/${metricId}`)}
      onMissing={() => go(navigate, `/scan/${snapshotId}/missing`)}
      onLoaded={finishVeil}
      onOpenChat={() => go(navigate, `/scan/${snapshotId}/chat`)}
    />
  )
}

function MetricPage() {
  const { snapshotId = '', metricId = '' } = useParams()
  if (!METRICS.includes(metricId as MetricId)) return <Navigate to={`/scan/${snapshotId}`} replace />
  return <MetricDetail snapshotId={snapshotId} metricId={metricId as MetricId} />
}

function MissingPage() {
  const { snapshotId = '' } = useParams()
  return <MissingData snapshotId={snapshotId} />
}

function ChatPage() {
  const { snapshotId = '' } = useParams()
  const navigate = useNavigate()
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null)
  useEffect(() => {
    let alive = true
    void api.diagnosis(snapshotId).then((result) => {
      if (alive) setDiagnosis(result)
    }).catch(() => {})
    return () => {
      alive = false
    }
  }, [snapshotId])
  return (
    <ChatScreen
      snapshotId={snapshotId}
      diagnosis={diagnosis}
      onBack={() => go(navigate, `/scan/${snapshotId}`)}
    />
  )
}
