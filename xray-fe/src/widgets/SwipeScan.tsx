import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'

const BASE = 156
const HIDDEN_PAD = 72

export function SwipeScan({
  open,
  onOpenChange,
  onActivate,
  onDelete,
  selecting = false,
  selected = false,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onActivate: () => void
  onDelete: () => void
  selecting?: boolean
  selected?: boolean
  children: ReactNode
}) {
  const [drag, setDrag] = useState<number | null>(null)
  const [live, setLive] = useState(false)
  const [full, setFull] = useState(false)
  const [sealed, setSealed] = useState(false)
  const [twitch, setTwitch] = useState(false)
  const [closing, setClosing] = useState(false)
  const [press, setPress] = useState(false)
  const [cardWidth, setCardWidth] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const onOpenChangeRef = useRef(onOpenChange)
  const onDeleteRef = useRef(onDelete)
  onOpenChangeRef.current = onOpenChange
  onDeleteRef.current = onDelete
  const selectingRef = useRef(selecting)
  selectingRef.current = selecting
  const dragging = useRef(false)
  const confirming = useRef(false)
  const openRef = useRef(open)
  openRef.current = open
  const startX = useRef(0)
  const startOffset = useRef(0)
  const startedOpen = useRef(false)
  const moved = useRef(0)
  const latest = useRef(0)
  const deleteTap = useRef<{ x: number; y: number } | null>(null)
  const twitchTimer = useRef(0)
  const pressTimer = useRef(0)
  const wheelTimer = useRef(0)
  const wheelActive = useRef(false)
  const wheelPendingX = useRef(0)
  const wheelPendingY = useRef(0)
  const wheelIgnoreUntil = useRef(0)
  const closingRef = useRef(false)
  const releaseTimer = useRef(0)
  const closeTimer = useRef(0)
  const sealTimer = useRef(0)
  const deleteTimer = useRef(0)
  const pressingDelete = useRef(false)
  const activating = useRef(false)
  const finishRef = useRef<(event: PointerEvent<HTMLDivElement>) => void>(() => {})
  const settleWheelRef = useRef<() => void>(() => {})

  const shown = full ? BASE : drag ?? (open ? BASE : 0)
  const progress = Math.min(1, Math.max(0, shown / BASE))
  const translate = full ? 0 : (1 - progress) * (BASE + HIDDEN_PAD)
  const restLeft = cardWidth > 0 ? cardWidth - 12 - BASE : null

  useLayoutEffect(() => {
    const node = rootRef.current
    if (!node) return
    let frame = 0
    const measure = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const width = Math.round(node.clientWidth)
        setCardWidth((current) => (current === width ? current : width))
      })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [])

  useEffect(() => {
    if (open || closingRef.current || confirming.current || full) return
    if (dragging.current || wheelActive.current) return
    if (latest.current <= 0) return
    slideAway()
  }, [open])

  function deleteFace() {
    return rootRef.current?.querySelector('.history-delete-face') ?? null
  }

  function overDelete(x: number, y: number) {
    const face = deleteFace()
    if (!face || confirming.current) return false
    const button = face.closest('.history-delete')
    if (!button || getComputedStyle(button).pointerEvents === 'none') return false
    const rect = face.getBoundingClientRect()
    if (rect.width < 8) return false
    return x >= rect.left - 8 && x <= rect.right + 8 && y >= rect.top - 8 && y <= rect.bottom + 8
  }

  function slideAway() {
    dragging.current = false
    wheelActive.current = false
    wheelPendingX.current = 0
    wheelPendingY.current = 0
    closingRef.current = true
    wheelIgnoreUntil.current = Date.now() + 480
    setLive(false)
    setDrag(latest.current)
    window.clearTimeout(releaseTimer.current)
    window.clearTimeout(closeTimer.current)
    releaseTimer.current = window.setTimeout(() => {
      setClosing(true)
      latest.current = 0
      setDrag(null)
      onOpenChangeRef.current(false)
      closeTimer.current = window.setTimeout(() => {
        setClosing(false)
        closingRef.current = false
      }, 460)
    }, 16)
  }

  function release(pull: number) {
    if (pull <= BASE * 0.45) {
      slideAway()
      return
    }
    wheelActive.current = false
    latest.current = BASE
    setLive(false)
    window.clearTimeout(releaseTimer.current)
    releaseTimer.current = window.setTimeout(() => {
      setDrag(null)
      onOpenChangeRef.current(true)
    }, 16)
  }

  function settleWheel() {
    wheelActive.current = false
    wheelPendingX.current = 0
    wheelPendingY.current = 0
    setPress(false)
    release(latest.current)
  }

  settleWheelRef.current = settleWheel

  function confirm() {
    if (confirming.current) return
    confirming.current = true
    dragging.current = false
    setDrag(null)
    setFull(true)
    window.clearTimeout(sealTimer.current)
    window.clearTimeout(deleteTimer.current)
    sealTimer.current = window.setTimeout(() => setSealed(true), 480)
    deleteTimer.current = window.setTimeout(() => onDeleteRef.current(), 1280)
  }

  useEffect(() => {
    const node = rootRef.current
    if (!node) return
    const onWheel = (event: WheelEvent) => {
      if (selectingRef.current || confirming.current || dragging.current || closingRef.current) return
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
      wheelTimer.current = window.setTimeout(() => {
        settleWheelRef.current()
      }, 16)
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
      const dx = originX - event.touches[0].clientX
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
      if (!dragging.current && !pressingDelete.current) return
      const touch = event.changedTouches[0]
      finishRef.current({
        type: 'pointerup',
        pointerType: 'touch',
        clientX: touch.clientX,
        clientY: touch.clientY,
        pointerId: -1,
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
      window.clearTimeout(twitchTimer.current)
      window.clearTimeout(pressTimer.current)
      window.clearTimeout(sealTimer.current)
      window.clearTimeout(deleteTimer.current)
      window.clearTimeout(closeTimer.current)
    }
  }, [])

  function armDeletePress(x: number, y: number) {
    deleteTap.current = { x, y }
    pressingDelete.current = true
    setTwitch(false)
    window.clearTimeout(twitchTimer.current)
    window.requestAnimationFrame(() => {
      setTwitch(true)
      twitchTimer.current = window.setTimeout(() => setTwitch(false), 320)
    })
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if (confirming.current || activating.current) return
    if (selectingRef.current) {
      dragging.current = true
      setPress(false)
      startX.current = event.clientX
      moved.current = 0
      startedOpen.current = false
      latest.current = 0
      event.currentTarget.setPointerCapture(event.pointerId)
      return
    }
    const target = event.target as HTMLElement
    if (target.closest('.history-delete') || overDelete(event.clientX, event.clientY)) {
      if (!target.closest('.history-delete')) {
        armDeletePress(event.clientX, event.clientY)
        event.currentTarget.setPointerCapture(event.pointerId)
      }
      return
    }
    dragging.current = true
    setPress(false)
    window.clearTimeout(pressTimer.current)
    startedOpen.current = open || latest.current > 8
    startX.current = event.clientX
    startOffset.current = drag ?? (open ? BASE : latest.current)
    moved.current = 0
    latest.current = startOffset.current
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return
    if (selectingRef.current) {
      moved.current = Math.max(moved.current, Math.abs(event.clientX - startX.current))
      return
    }
    const delta = startX.current - event.clientX
    moved.current = Math.max(moved.current, Math.abs(delta))
    if (moved.current < 8) return
    window.clearTimeout(pressTimer.current)
    setPress(false)
    const next = Math.max(0, Math.min(BASE + 280, startOffset.current + delta))
    latest.current = next
    if (!live) setLive(true)
    setDrag(next)
  }

  function finish(event: PointerEvent<HTMLDivElement>) {
    if (event.type === 'pointercancel' && event.pointerType === 'touch') return
    if (pressingDelete.current) {
      pressingDelete.current = false
      const tap = deleteTap.current
      deleteTap.current = null
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId)
      }
      if (!tap || confirming.current) return
      const travel = Math.hypot(event.clientX - tap.x, event.clientY - tap.y)
      if (travel <= 28) confirm()
      return
    }
    if (!dragging.current) return
    dragging.current = false
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    const pull = latest.current
    const gestureStartedOpen = startedOpen.current
    window.clearTimeout(pressTimer.current)
    if (moved.current < 8) {
      if (selectingRef.current) {
        setLive(false)
        setDrag(null)
        setPress(false)
        onActivate()
        return
      }
      if (!gestureStartedOpen) {
        setLive(false)
        setDrag(null)
        activating.current = true
        setPress(true)
        pressTimer.current = window.setTimeout(() => {
          setPress(false)
          activating.current = false
          onActivate()
        }, 300)
        return
      }
      setPress(false)
      slideAway()
      return
    }
    setPress(false)
    release(pull)
  }

  finishRef.current = finish

  return (
    <div
      ref={rootRef}
      className={`swipe${live ? ' is-dragging' : ''}${press ? ' is-press' : ''}${selecting ? ' is-selecting' : ''}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finish}
      onPointerCancel={finish}
    >
      <div className={`scan-card${selected ? ' is-picked' : ''}`}>
        <div
          className="scan-card-body"
          style={{
            filter: progress > 0 && !closing ? `blur(${Math.min(1, progress) * 10}px)` : undefined,
          }}
        >
          {children}
        </div>
        <span
          className="swipe-wash"
          style={{
            opacity: full || (progress > 0.12 && !closing) ? 1 : 0,
            ['--wash' as string]: 0.18 + Math.min(1, progress) * 0.2,
          }}
        />
      </div>
      <div
        role="button"
        className={`history-delete${full ? ' is-full' : ''}${sealed ? ' is-sealed' : ''}${twitch ? ' is-twitch' : ''}`}
        style={{
          left: full ? 12 : restLeft == null ? undefined : restLeft,
          width: full || restLeft != null ? 'auto' : BASE,
          transform: `translateX(${translate}px)`,
          transformOrigin: 'right center',
          opacity: full || closing || progress > 0 ? 1 : 0,
          boxShadow: !full && !closing && progress <= 0 ? 'none' : undefined,
          pointerEvents: !live && !closing && (full || progress > 0.4) ? 'auto' : 'none',
        }}
        tabIndex={!live && (progress > 0.4 || full) ? 0 : -1}
        onPointerDown={(event) => {
          event.stopPropagation()
          if (confirming.current) return
          armDeletePress(event.clientX, event.clientY)
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onPointerUp={(event) => {
          event.stopPropagation()
          if (event.currentTarget.hasPointerCapture(event.pointerId)) {
            event.currentTarget.releasePointerCapture(event.pointerId)
          }
          const tap = deleteTap.current
          deleteTap.current = null
          pressingDelete.current = false
          if (!tap || confirming.current) return
          const travel = Math.hypot(event.clientX - tap.x, event.clientY - tap.y)
          if (travel > 28) return
          confirm()
        }}
        onClick={(event) => {
          if (event.detail !== 0) return
          confirm()
        }}
        onKeyDown={(event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return
          event.preventDefault()
          confirm()
        }}
      >
        <span className="history-delete-face">
          <span className="history-delete-wash" />
          <span className="history-delete-status">
            <svg className="history-delete-check" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 12.6 9.2 16.8 19 7.2" />
            </svg>
            <span className="history-delete-words">
              <span className="is-remove" aria-hidden={sealed}>Удалить</span>
              <span className="is-done" aria-hidden={!sealed}>Удалено</span>
            </span>
          </span>
        </span>
      </div>
    </div>
  )
}
