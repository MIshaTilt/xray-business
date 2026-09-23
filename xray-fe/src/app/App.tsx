import { Panel } from '@maxhub/max-ui'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { MetricId, UploadResponse } from '../api/types.ts'
import { bindBack, getPlatform, initBridge, showBack } from '../bridge/index.ts'
import { dealsAsTable } from '../domain/platform.ts'
import { Diagnosis } from '../screens/Diagnosis.tsx'
import { Home } from '../screens/Home.tsx'
import { MappingScreen } from '../screens/Mapping.tsx'
import { MetricDetail } from '../screens/MetricDetail.tsx'
import { MissingData } from '../screens/MissingData.tsx'
import { Processing } from '../screens/Processing.tsx'
import { ChatScreen } from '../screens/ChatScreen.tsx'
import { AnalyzeVeil } from '../widgets/AnalyzeVeil.tsx'
import { LiveWallpaper } from '../widgets/LiveWallpaper.tsx'
import { XRayLogo } from '../widgets/XRayLogo.tsx'
import type { Diagnosis as DiagnosisData } from '../api/types.ts'

type Screen =
  | { name: 'home' }
  | { name: 'mapping'; upload: UploadResponse }
  | { name: 'processing'; snapshotId: string }
  | { name: 'diagnosis'; snapshotId: string }
  | { name: 'metric'; snapshotId: string; metricId: MetricId }
  | { name: 'missing'; snapshotId: string }
  | { name: 'chat'; snapshotId: string; diagnosis: DiagnosisData }

export function App() {
  const [stack, setStack] = useState<Screen[]>([{ name: 'home' }])
  const [homeKey, setHomeKey] = useState(0)
  const [hostBack, setHostBack] = useState(false)
  const [veil, setVeil] = useState(false)
  const [veilStep, setVeilStep] = useState(0)
  const [homeSplash, setHomeSplash] = useState(false)
  const [dark, setDark] = useState(() => window.localStorage.getItem('xray-theme') === 'dark')
  const [themePlayed, setThemePlayed] = useState(false)
  const veilStarted = useRef(0)
  const current = stack[stack.length - 1] ?? { name: 'home' }
  const wide = dealsAsTable(getPlatform())

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    window.localStorage.setItem('xray-theme', dark ? 'dark' : 'light')
  }, [dark])

  const pop = useCallback(() => {
    setStack((currentStack) => (currentStack.length > 1 ? currentStack.slice(0, -1) : currentStack))
  }, [])

  const push = useCallback((screen: Screen) => {
    setStack((currentStack) => [...currentStack, screen])
  }, [])

  const replace = useCallback((screen: Screen) => {
    setStack((currentStack) => [...currentStack.slice(0, -1), screen])
  }, [])

  const reset = useCallback(() => {
    setStack([{ name: 'home' }])
    setHomeKey((value) => value + 1)
  }, [])

  const beginVeil = useCallback(() => {
    veilStarted.current = Date.now()
    setVeilStep(0)
    setVeil(true)
  }, [])

  const stopVeil = useCallback(() => {
    setVeil(false)
  }, [])

  const goHome = useCallback(() => {
    if (homeSplash) return
    setHomeSplash(true)
    window.setTimeout(() => {
      reset()
      setVeil(false)
      setHomeSplash(false)
    }, 900)
  }, [homeSplash, reset])

  const finishVeil = useCallback(() => {
    const wait = Math.max(0, 1800 - (Date.now() - veilStarted.current))
    window.setTimeout(() => setVeil(false), wait)
  }, [])

  useEffect(() => {
    if (!veil) return
    const tick = window.setInterval(() => setVeilStep((step) => step + 1), 700)
    return () => window.clearInterval(tick)
  }, [veil])

  useEffect(() => {
    initBridge()
    setHostBack(Boolean(window.WebApp?.initData && window.WebApp.BackButton))
  }, [])

  const scrollKey = [
    current.name,
    'snapshotId' in current ? current.snapshotId : '',
    'metricId' in current ? current.metricId : '',
  ].join(':')

  useEffect(() => {
    window.scrollTo(0, 0)
    document.documentElement.scrollTop = 0
    document.body.scrollTop = 0
    document.querySelectorAll('.app-panel, #root').forEach((node) => {
      node.scrollTop = 0
    })
  }, [scrollKey])

  useEffect(() => {
    if (stack.length <= 1) {
      showBack(false)
      return
    }
    showBack(true)
    return bindBack(pop)
  }, [pop, stack.length])

  return (
    <Panel mode="secondary" className="app-panel">
      <LiveWallpaper />
      <main className={`${wide ? 'app-shell wide' : 'app-shell'}${stack.length > 1 && !hostBack ? ' with-back' : ''}`}>
        <div className="nav-bar">
          {stack.length > 1 && !hostBack ? (
            <>
              <button type="button" className="back" onClick={pop}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M14.5 6.5 9 12l5.5 5.5" />
                </svg>
                <span>Назад</span>
              </button>
              <button type="button" className="home-btn" aria-label="Домой" onClick={goHome}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M4 11.2 12 5l8 6.2" />
                  <path d="M7.5 10.8V19h9v-8.2" />
                </svg>
              </button>
            </>
          ) : null}
          <button
            type="button"
            className={`theme-btn${dark ? ' is-dark' : ''}${themePlayed ? ' is-played' : ''}`}
            aria-label={dark ? 'Светлая тема' : 'Ночная тема'}
            onClick={() => {
              setThemePlayed(true)
              setDark((value) => !value)
            }}
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
        </div>
        {stack.length > 1 && !hostBack ? <div className="back-spacer" aria-hidden="true" /> : null}
        {current.name === 'home' ? (
          <Home
            key={homeKey}
            onUploaded={(upload) => push({ name: 'mapping', upload })}
            onDiagnosis={(snapshotId) => push({ name: 'diagnosis', snapshotId })}
            onProcessing={(snapshotId) => push({ name: 'processing', snapshotId })}
          />
        ) : null}
        {homeSplash ? (
          <div className="home-splash" role="status" aria-live="polite">
            <div className="home-splash-card">
              <span className="home-splash-logo" aria-hidden="true">
                <XRayLogo scanning />
              </span>
              <p className="home-splash-title">X-Ray</p>
            </div>
          </div>
        ) : null}
        {veil ? <AnalyzeVeil step={veilStep} /> : null}
        {current.name === 'mapping' ? (
          <MappingScreen
            upload={current.upload}
            onAnalyze={beginVeil}
            onAnalyzeStop={stopVeil}
            onStart={(snapshotId) => push({ name: 'processing', snapshotId })}
          />
        ) : null}
        {current.name === 'processing' ? (
          <Processing
            snapshotId={current.snapshotId}
            onReady={() => replace({ name: 'diagnosis', snapshotId: current.snapshotId })}
            onBack={pop}
            onFailed={stopVeil}
          />
        ) : null}
        {current.name === 'diagnosis' ? (
          <Diagnosis
            snapshotId={current.snapshotId}
            wide={wide}
            onMetric={(metricId) => push({ name: 'metric', snapshotId: current.snapshotId, metricId })}
            onMissing={() => push({ name: 'missing', snapshotId: current.snapshotId })}
            onNew={reset}
            onLoaded={finishVeil}
            onOpenChat={(diagnosisData) =>
              push({ name: 'chat', snapshotId: current.snapshotId, diagnosis: diagnosisData })
            }
          />
        ) : null}
        {current.name === 'metric' ? (
          <MetricDetail snapshotId={current.snapshotId} metricId={current.metricId} wide={wide} />
        ) : null}
        {current.name === 'missing' ? <MissingData snapshotId={current.snapshotId} /> : null}
        {current.name === 'chat' ? (
          <ChatScreen
            snapshotId={current.snapshotId}
            diagnosis={current.diagnosis}
            onBack={pop}
          />
        ) : null}
      </main>
    </Panel>
  )
}
