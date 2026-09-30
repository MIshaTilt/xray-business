import { Panel } from '@maxhub/max-ui'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import type { ComparisonResult, Diagnosis as DiagnosisData, MetricId } from '../api/types.ts'
import { api } from '../api/client.ts'
import { bindBack, initBridge, showBack } from '../bridge/index.ts'
import { ChatScreen } from '../screens/ChatScreen.tsx'
import { Compare } from '../screens/Compare.tsx'
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
import { backTarget, go, isViewTransitionCapture, tabOf, type TabName } from './nav.ts'

function playTabDrop(button: HTMLButtonElement) {
  if (!button.classList.contains('is-on')) return
  const nodes = [button, button.parentElement?.querySelector('.tab-pill')].filter(
    (node): node is HTMLElement => node instanceof HTMLElement,
  )
  for (const node of nodes) {
    node.classList.remove('is-drop')
    void node.offsetWidth
    node.classList.add('is-drop')
    window.setTimeout(() => node.classList.remove('is-drop'), 360)
  }
}

const TAB_ROOT: Record<TabName, string> = {
  home: '/',
  scans: '/scans',
  chat: '/chat',
  menu: '/menu',
}

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
  const tab = tabOf(location.pathname)
  const inChat = location.pathname.endsWith('/chat')
  const onDiagnosis = /^\/scan\/[^/]+$/.test(location.pathname)
  const onCompare = location.pathname.startsWith('/compare')
  const nested =
    /\/scan\/[^/]+\/(metric|missing|chat)/.test(location.pathname) ||
    location.pathname.startsWith('/processing/')
  const showBackBtn =
    !inChat &&
    (nested || onDiagnosis || onCompare || location.pathname.startsWith('/mapping') || location.pathname.startsWith('/templates'))
  const showTabs = true
  const tabBarRef = useRef<HTMLElement>(null)
  const pillReady = useRef(false)
  const seenTab = useRef<TabName | null>(null)
  const [pillMotion, setPillMotion] = useState(false)
  const [pill, setPill] = useState({ x: 4, w: 0, stretch: false })
  const lastTabPath = useRef<Record<TabName, string>>({ ...TAB_ROOT })
  const skipBack = useRef(false)
  useEffect(() => {
    const scene = inChat ? 'chat' : 'home'
    if (document.documentElement.dataset.scene !== scene) {
      document.documentElement.dataset.scene = scene
    }
    window.scrollTo(0, 0)
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
  }, [location.pathname, inChat])

  useEffect(() => {
    if (location.pathname.startsWith('/processing/')) return
    lastTabPath.current[tab] = location.pathname
  }, [location.pathname, tab])

  useEffect(() => {
    if (flow.lastScanId) {
      lastTabPath.current.chat = `/scan/${flow.lastScanId}/chat`
    }
  }, [flow.lastScanId])

  useLayoutEffect(() => {
    const bar = tabBarRef.current
    if (!bar) return
    const measure = (stretch: boolean) => {
      const active = bar.querySelector('.tab-item.is-on')
      if (!(active instanceof HTMLElement)) return
      setPill({
        x: active.offsetLeft,
        w: active.offsetWidth,
        stretch,
      })
    }
    const tabChanged = seenTab.current !== null && seenTab.current !== tab
    seenTab.current = tab
    measure(tabChanged && !isViewTransitionCapture())
    if (!pillReady.current) {
      pillReady.current = true
      window.requestAnimationFrame(() => setPillMotion(true))
    }
    const onResize = () => measure(false)
    window.addEventListener('resize', onResize)
    window.visualViewport?.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      window.visualViewport?.removeEventListener('resize', onResize)
    }
  }, [tab])

  useEffect(() => {
    initBridge()
  }, [])

  useEffect(() => {
    const overTabBar = (event: PointerEvent | MouseEvent) => {
      const bar = document.querySelector('.tab-bar')
      if (!bar) return false
      const rect = bar.getBoundingClientRect()
      return (
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom
      )
    }
    const onPointerDown = (event: PointerEvent) => {
      if (document.querySelector('.download-sheet, .chat-drawer') && overTabBar(event)) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    const onClick = (event: MouseEvent) => {
      if (document.querySelector('.download-sheet, .chat-drawer') && overTabBar(event)) {
        event.preventDefault()
        event.stopPropagation()
      }
    }
    window.addEventListener('pointerdown', onPointerDown, true)
    window.addEventListener('click', onClick, true)
    return () => {
      window.removeEventListener('pointerdown', onPointerDown, true)
      window.removeEventListener('click', onClick, true)
    }
  }, [])

  const pop = useCallback(() => {
    if (skipBack.current) return
    const next = backTarget(location.pathname)
    if (next === location.pathname) return
    go(navigate, next)
  }, [location.pathname, navigate])

  const openTab = useCallback(
    (name: TabName) => {
      if (document.querySelector('.download-sheet, .chat-drawer')) return
      const root = TAB_ROOT[name]
      const onThisTab = tabOf(location.pathname) === name
      if (name === 'chat' && onThisTab) return

      let next: string
      if (name === 'chat') {
        next = flow.lastScanId ? `/scan/${flow.lastScanId}/chat` : '/chat'
      } else {
        next = onThisTab ? root : lastTabPath.current[name] || root
        if (next.startsWith('/processing/') || tabOf(next) !== name) next = root
      }

      if (next === location.pathname) return
      skipBack.current = true
      window.setTimeout(() => {
        skipBack.current = false
      }, 500)
      go(navigate, next)
    },
    [location.pathname, navigate, flow.lastScanId],
  )

  useEffect(() => {
    if (!showBackBtn) {
      showBack(false)
      return
    }
    showBack(true)
    return bindBack(pop)
  }, [pop, showBackBtn])

  useEffect(() => {
    const root = document.documentElement
    const apply = () => {
      const viewport = window.visualViewport
      const active = document.activeElement
      const typing =
        active instanceof HTMLElement &&
        (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)
      const inset =
        viewport && typing
          ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop)
          : 0
      root.style.setProperty('--keyboard-inset', `${Math.round(inset)}px`)
    }
    const onFocusOut = () => {
      window.requestAnimationFrame(apply)
    }
    apply()
    window.visualViewport?.addEventListener('resize', apply)
    window.visualViewport?.addEventListener('scroll', apply)
    window.addEventListener('resize', apply)
    window.addEventListener('focusin', apply)
    window.addEventListener('focusout', onFocusOut)
    return () => {
      window.visualViewport?.removeEventListener('resize', apply)
      window.visualViewport?.removeEventListener('scroll', apply)
      window.removeEventListener('resize', apply)
      window.removeEventListener('focusin', apply)
      window.removeEventListener('focusout', onFocusOut)
      root.style.removeProperty('--keyboard-inset')
    }
  }, [])

  return (
    <Panel mode="secondary" className="app-panel">
      <LiveWallpaper />
      <main
        className={`app-shell${showBackBtn ? ' with-back' : ''}${showTabs ? ' with-tabs' : ''}${inChat ? ' is-chat' : ''}`}
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
          <div className="diag-more-slot" id="diag-more-slot" />
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
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/compare/chat" element={<CompareChatPage />} />
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
          <nav
            ref={tabBarRef}
            className="tab-bar"
            aria-label="Навигация"
            onPointerDown={(event) => {
              if (document.querySelector('.download-sheet, .chat-drawer')) return
              const button = event.target instanceof Element ? event.target.closest('.tab-item') : null
              if (button instanceof HTMLButtonElement) playTabDrop(button)
            }}
          >
            <span
              className={`tab-pill${pill.stretch ? ' is-stretch' : ''}${pillMotion ? ' is-ready' : ''}`}
              style={{ left: pill.x, width: pill.w }}
              aria-hidden="true"
              onAnimationEnd={() => setPill((current) => (current.stretch ? { ...current, stretch: false } : current))}
            />
            <button type="button" className={`tab-item${tab === 'home' ? ' is-on' : ''}`} onClick={() => openTab('home')}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 11.2 12 5l8 6.2" />
                <path d="M7.5 10.8V19h9v-8.2" />
              </svg>
              Главная
            </button>
            <button
              type="button"
              className={`tab-item${tab === 'scans' ? ' is-on' : ''}`}
              onClick={() => openTab('scans')}
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
              onClick={() => openTab('chat')}
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
              onClick={() => openTab('menu')}
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
      onCrmReady={(snapshotId) => {
        flow.setLastScanId(snapshotId)
        go(navigate, `/scan/${snapshotId}`)
      }}
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
      onCompare={(baseId, targetId) => {
        go(navigate, `/compare?base_id=${encodeURIComponent(baseId)}&target_id=${encodeURIComponent(targetId)}`)
      }}
    />
  )
}

function ComparePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { finishVeil, setLastScanId } = useFlow()
  const baseId = searchParams.get('base_id') || ''
  const targetId = searchParams.get('target_id') || ''

  if (!baseId || !targetId) {
    return <Navigate to="/scans" replace />
  }

  return (
    <Compare
      baseId={baseId}
      targetId={targetId}
      onLoaded={(comparisonId) => {
        finishVeil()
        if (comparisonId) {
          setLastScanId(comparisonId)
        }
      }}
      onOpenSnapshot={(snapshotId) => {
        setLastScanId(snapshotId)
        go(navigate, `/scan/${snapshotId}`)
      }}
      onOpenChat={(comparisonId) => {
        const effectiveId = comparisonId || baseId
        if (effectiveId) setLastScanId(effectiveId)
        if (comparisonId) {
          go(navigate, `/scan/${comparisonId}/chat`)
        } else {
          go(navigate, `/compare/chat?base_id=${encodeURIComponent(baseId)}&target_id=${encodeURIComponent(targetId)}`)
        }
      }}
    />
  )
}

function ChatGatePage() {
  const flow = useFlow()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(!flow.lastScanId)

  useEffect(() => {
    if (flow.lastScanId) return

    let alive = true
    api
      .list()
      .then((items) => {
        if (!alive) return
        if (items && items.length > 0) {
          const latest = items[0]
          flow.setLastScanId(latest.snapshot_id)
        } else {
          setLoading(false)
        }
      })
      .catch(() => {
        if (!alive) return
        setLoading(false)
      })

    return () => {
      alive = false
    }
  }, [flow.lastScanId, flow.setLastScanId])

  if (flow.lastScanId) return <Navigate to={`/scan/${flow.lastScanId}/chat`} replace />

  if (loading) {
    return (
      <div className="stack">
        <div className="lead">
          <h1>Чат</h1>
          <p className="home-hint">Поиск последнего анализа...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="stack">
      <div className="lead">
        <h1>Консультант</h1>
        <p className="home-hint">
          У вас пока нет загруженных данных для анализа. Загрузите таблицу на Главной, чтобы провести аудит и начать диалог с бизнес-ассистентом.
        </p>
      </div>
      <div style={{ marginTop: 16 }}>
        <button
          type="button"
          className="action action-primary"
          onClick={() => go(navigate, '/')}
          style={{ width: '100%', height: 48, borderRadius: 12, fontWeight: 600 }}
        >
          Загрузить таблицу
        </button>
      </div>
    </div>
  )
}

function MenuPage() {
  const navigate = useNavigate()
  const flow = useFlow()
  return (
    <Menu
      dark={flow.dark}
      onToggleTheme={flow.toggleTheme}
      onOpenSnapshot={(snapshotId) => {
        flow.setLastScanId(snapshotId)
        go(navigate, `/scan/${snapshotId}`)
      }}
    />
  )
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
  useEffect(() => {
    setLastScanId(snapshotId)
  }, [setLastScanId, snapshotId])
  return (
    <Diagnosis
      snapshotId={snapshotId}
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
  const { setLastScanId } = useFlow()
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null)
  const [comparison, setComparison] = useState<ComparisonResult | null>(null)

  useEffect(() => {
    let alive = true
    void api
      .diagnosis(snapshotId)
      .then((result) => {
        if (!alive) return
        setDiagnosis(result)
        if (result.item_type === 'comparison' && result.compare_base_id && result.compare_target_id) {
          api
            .compare(result.compare_base_id, result.compare_target_id)
            .then((cmp) => {
              if (alive) setComparison(cmp)
            })
            .catch(() => {})
        }
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [snapshotId])

  const isComparison = diagnosis?.item_type === 'comparison' || Boolean(comparison)
  const baseId = comparison?.base.snapshot_id || diagnosis?.compare_base_id || snapshotId
  const targetId = comparison?.target.snapshot_id || diagnosis?.compare_target_id
  const comparisonId = isComparison ? (comparison?.comparison_id || snapshotId) : undefined

  return (
    <ChatScreen
      comparisonId={comparisonId}
      snapshotId={baseId}
      targetSnapshotId={targetId}
      comparison={comparison}
      diagnosis={diagnosis}
      onOpenChat={(id) => {
        setLastScanId(id)
        go(navigate, `/scan/${id}/chat`)
      }}
      onBack={() => {
        if (isComparison && (diagnosis?.compare_base_id || comparison?.base.snapshot_id)) {
          const b = comparison?.base.snapshot_id || diagnosis?.compare_base_id
          const t = comparison?.target.snapshot_id || diagnosis?.compare_target_id
          go(navigate, `/compare?base_id=${encodeURIComponent(b || '')}&target_id=${encodeURIComponent(t || '')}`)
        } else {
          go(navigate, `/scan/${snapshotId}`)
        }
      }}
    />
  )
}

function CompareChatPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setLastScanId } = useFlow()
  const baseId = searchParams.get('base_id') || ''
  const targetId = searchParams.get('target_id') || ''
  const [comparison, setComparison] = useState<ComparisonResult | null>(null)

  useEffect(() => {
    let alive = true
    if (!baseId || !targetId) return
    api
      .compare(baseId, targetId)
      .then((result) => {
        if (!alive) return
        setComparison(result)
        if (result.comparison_id) {
          setLastScanId(result.comparison_id)
        }
      })
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [baseId, targetId, setLastScanId])

  if (!baseId || !targetId) {
    return <Navigate to="/scans" replace />
  }

  return (
    <ChatScreen
      comparisonId={comparison?.comparison_id}
      snapshotId={baseId}
      targetSnapshotId={targetId}
      comparison={comparison}
      onOpenChat={(id) => {
        setLastScanId(id)
        go(navigate, `/scan/${id}/chat`)
      }}
      onBack={() =>
        go(
          navigate,
          `/compare?base_id=${encodeURIComponent(baseId)}&target_id=${encodeURIComponent(targetId)}`,
        )
      }
    />
  )
}
