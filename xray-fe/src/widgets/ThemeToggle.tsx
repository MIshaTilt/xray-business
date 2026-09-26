import { useEffect, useRef, useState, type PointerEvent } from 'react'

const BASE = 64

export function ThemeToggle({
  dark,
  onToggle,
}: {
  dark: boolean
  onToggle: () => void
}) {
  const [drag, setDrag] = useState<number | null>(null)
  const [live, setLive] = useState(false)
  const [press, setPress] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startOffset = useRef(0)
  const moved = useRef(0)
  const latest = useRef(dark ? BASE : 0)
  const darkRef = useRef(dark)
  darkRef.current = dark
  const onToggleRef = useRef(onToggle)
  onToggleRef.current = onToggle
  const wheelTimer = useRef(0)
  const wheelActive = useRef(false)
  const wheelPendingX = useRef(0)
  const wheelPendingY = useRef(0)
  const wheelIgnoreUntil = useRef(0)
  const releaseTimer = useRef(0)
  const pressTimer = useRef(0)
  const finishRef = useRef<(event: PointerEvent<HTMLDivElement>) => void>(() => {})
  const settleWheelRef = useRef<() => void>(() => {})

  const rest = dark ? BASE : 0
  const shown = drag ?? rest
  const progress = Math.min(1, Math.max(0, shown / BASE))

  function commit(nextDark: boolean, fromTap: boolean) {
    const dest = nextDark ? BASE : 0
    latest.current = dest
    wheelActive.current = false
    setLive(false)
    window.clearTimeout(releaseTimer.current)
    if (fromTap) {
      setDrag(null)
    } else {
      setDrag(dest)
      releaseTimer.current = window.setTimeout(() => setDrag(null), 16)
    }
    if (nextDark === darkRef.current) return
    onToggleRef.current()
  }

  function release(pull: number, fromTap: boolean) {
    if (fromTap) {
      commit(!darkRef.current, true)
      return
    }
    commit(pull >= BASE * 0.45, false)
  }

  function settleWheel() {
    wheelActive.current = false
    wheelPendingX.current = 0
    wheelPendingY.current = 0
    setPress(false)
    release(latest.current, false)
  }

  settleWheelRef.current = settleWheel

  useEffect(() => {
    if (dragging.current || wheelActive.current) return
    latest.current = dark ? BASE : 0
  }, [dark])

  useEffect(() => {
    const node = rootRef.current
    if (!node) return
    const onWheel = (event: WheelEvent) => {
      if (dragging.current) return
      if (Date.now() < wheelIgnoreUntil.current) return
      if (!wheelActive.current) {
        wheelPendingX.current += event.deltaX
        wheelPendingY.current += event.deltaY
        if (
          Math.abs(wheelPendingX.current) < 8 ||
          Math.abs(wheelPendingX.current) <= Math.abs(wheelPendingY.current)
        ) {
          return
        }
        event.preventDefault()
        wheelActive.current = true
        latest.current = Math.max(0, Math.min(BASE, latest.current + wheelPendingX.current))
        wheelPendingX.current = 0
        wheelPendingY.current = 0
        setLive(true)
        setDrag(latest.current)
      } else {
        event.preventDefault()
        latest.current = Math.max(0, Math.min(BASE, latest.current + event.deltaX))
        setDrag(latest.current)
      }
      window.clearTimeout(wheelTimer.current)
      wheelTimer.current = window.setTimeout(() => settleWheelRef.current(), 16)
    }
    let originX = 0
    let originY = 0
    let axis: 'x' | 'y' | null = null
    const onTouchStart = (event: TouchEvent) => {
      if (event.touches.length !== 1) return
      originX = event.touches[0].clientX
      originY = event.touches[0].clientY
      axis = null
    }
    const onTouchMove = (event: TouchEvent) => {
      if (event.touches.length !== 1) return
      const dx = event.touches[0].clientX - originX
      const dy = event.touches[0].clientY - originY
      if (!axis) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return
        axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y'
      }
      if (axis === 'x' && event.cancelable) event.preventDefault()
    }
    const onTouchEnd = (event: TouchEvent) => {
      const claimed = axis
      axis = null
      if (claimed === 'y') {
        dragging.current = false
        setLive(false)
        setDrag(null)
        return
      }
      if (!dragging.current) return
      const touch = event.changedTouches[0]
      finishRef.current({
        type: 'pointerup',
        pointerType: 'touch',
        clientX: touch.clientX,
        clientY: touch.clientY,
        pointerId: -1,
        button: 0,
        currentTarget: node,
        hasPointerCapture: () => false,
        releasePointerCapture: () => {},
      } as unknown as PointerEvent<HTMLDivElement>)
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    node.addEventListener('touchstart', onTouchStart, { passive: true })
    node.addEventListener('touchmove', onTouchMove, { passive: false })
    node.addEventListener('touchend', onTouchEnd)
    node.addEventListener('touchcancel', onTouchEnd)
    return () => {
      node.removeEventListener('wheel', onWheel)
      node.removeEventListener('touchstart', onTouchStart)
      node.removeEventListener('touchmove', onTouchMove)
      node.removeEventListener('touchend', onTouchEnd)
      node.removeEventListener('touchcancel', onTouchEnd)
      window.clearTimeout(wheelTimer.current)
      window.clearTimeout(releaseTimer.current)
      window.clearTimeout(pressTimer.current)
    }
  }, [])

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return
    dragging.current = true
    setPress(false)
    window.clearTimeout(pressTimer.current)
    startX.current = event.clientX
    startOffset.current = drag ?? rest
    moved.current = 0
    latest.current = startOffset.current
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return
    const delta = event.clientX - startX.current
    moved.current = Math.max(moved.current, Math.abs(delta))
    if (moved.current < 8) return
    window.clearTimeout(pressTimer.current)
    setPress(false)
    const next = Math.max(0, Math.min(BASE, startOffset.current + delta))
    latest.current = next
    if (!live) setLive(true)
    setDrag(next)
  }

  function finish(event: PointerEvent<HTMLDivElement>) {
    if (event.type === 'pointercancel' && event.pointerType === 'touch') return
    if (!dragging.current) return
    dragging.current = false
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    const tapped = moved.current < 8
    window.clearTimeout(pressTimer.current)
    if (tapped) {
      setLive(false)
      setDrag(null)
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        setPress(true)
        pressTimer.current = window.setTimeout(() => setPress(false), 320)
      }
      commit(!dark, true)
      return
    }
    setPress(false)
    wheelIgnoreUntil.current = Date.now() + 480
    release(latest.current, false)
  }

  finishRef.current = finish

  return (
    <div
      ref={rootRef}
      className={`theme-switch${live ? ' is-dragging' : ''}${press ? ' is-press' : ''}`}
      role="switch"
      aria-checked={dark}
      aria-label={dark ? 'Светлая тема' : 'Ночная тема'}
      tabIndex={0}
      style={{ ['--theme-p' as string]: String(progress) }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finish}
      onPointerCancel={finish}
      onKeyDown={(event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        onToggle()
      }}
    >
      <span className="theme-btn">
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
      </span>
    </div>
  )
}
