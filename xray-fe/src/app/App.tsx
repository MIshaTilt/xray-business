import { Panel } from '@maxhub/max-ui'
import { useCallback, useEffect, useState } from 'react'
import type { MetricId, UploadResponse } from '../api/types.ts'
import { bindBack, getPlatform, initBridge, showBack } from '../bridge/index.ts'
import { dealsAsTable } from '../domain/platform.ts'
import { Diagnosis } from '../screens/Diagnosis.tsx'
import { Home } from '../screens/Home.tsx'
import { MappingScreen } from '../screens/Mapping.tsx'
import { MetricDetail } from '../screens/MetricDetail.tsx'
import { MissingData } from '../screens/MissingData.tsx'
import { Processing } from '../screens/Processing.tsx'

type Screen =
  | { name: 'home' }
  | { name: 'mapping'; upload: UploadResponse }
  | { name: 'processing'; snapshotId: string }
  | { name: 'diagnosis'; snapshotId: string }
  | { name: 'metric'; snapshotId: string; metricId: MetricId }
  | { name: 'missing'; snapshotId: string }

export function App() {
  const [stack, setStack] = useState<Screen[]>([{ name: 'home' }])
  const [homeKey, setHomeKey] = useState(0)
  const [hostBack, setHostBack] = useState(false)
  const current = stack[stack.length - 1] ?? { name: 'home' }
  const wide = dealsAsTable(getPlatform())

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

  useEffect(() => {
    initBridge()
    setHostBack(Boolean(window.WebApp?.initData && window.WebApp.BackButton))
  }, [])

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
      <main className={`${wide ? 'app-shell wide' : 'app-shell'}${stack.length > 1 && !hostBack ? ' with-back' : ''}`}>
        {stack.length > 1 && !hostBack ? (
          <>
            <button type="button" className="back" aria-label="Назад" onClick={pop}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14.5 6.5 9 12l5.5 5.5" />
              </svg>
            </button>
            <div className="back-spacer" aria-hidden="true" />
          </>
        ) : null}
        {current.name === 'home' ? (
          <Home
            key={homeKey}
            onUploaded={(upload) => push({ name: 'mapping', upload })}
            onDiagnosis={(snapshotId) => push({ name: 'diagnosis', snapshotId })}
            onProcessing={(snapshotId) => push({ name: 'processing', snapshotId })}
          />
        ) : null}
        {current.name === 'mapping' ? (
          <MappingScreen upload={current.upload} onStart={(snapshotId) => push({ name: 'processing', snapshotId })} />
        ) : null}
        {current.name === 'processing' ? (
          <Processing
            snapshotId={current.snapshotId}
            onReady={() => replace({ name: 'diagnosis', snapshotId: current.snapshotId })}
            onBack={pop}
          />
        ) : null}
        {current.name === 'diagnosis' ? (
          <Diagnosis
            snapshotId={current.snapshotId}
            wide={wide}
            onMetric={(metricId) => push({ name: 'metric', snapshotId: current.snapshotId, metricId })}
            onMissing={() => push({ name: 'missing', snapshotId: current.snapshotId })}
            onNew={reset}
          />
        ) : null}
        {current.name === 'metric' ? (
          <MetricDetail snapshotId={current.snapshotId} metricId={current.metricId} wide={wide} />
        ) : null}
        {current.name === 'missing' ? <MissingData snapshotId={current.snapshotId} /> : null}
      </main>
    </Panel>
  )
}
