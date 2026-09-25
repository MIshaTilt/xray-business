import { useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'

export function InsetVScroll({
  children,
  watch,
}: {
  children: ReactNode
  watch?: unknown
}) {
  const scroller = useRef<HTMLDivElement>(null)
  const drag = useRef<{ pointerId: number; startY: number; startScroll: number; track: HTMLElement } | null>(null)
  const [thumb, setThumb] = useState({ height: 0, y: 0, show: false })

  useLayoutEffect(() => {
    const node = scroller.current
    if (!node) return
    function update() {
      if (!node) return
      const max = node.scrollHeight - node.clientHeight
      if (max <= 2) {
        setThumb({ height: 0, y: 0, show: false })
        return
      }
      const height = Math.max(16, (node.clientHeight / node.scrollHeight) * 100)
      const y = (node.scrollTop / max) * (100 - height)
      setThumb({ height, y, show: true })
    }
    update()
    node.addEventListener('scroll', update, { passive: true })
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => {
      node.removeEventListener('scroll', update)
      observer.disconnect()
    }
  }, [watch])

  function onPointerDown(event: PointerEvent<HTMLSpanElement>) {
    const node = scroller.current
    const track = event.currentTarget
    if (!node) return
    event.preventDefault()
    event.stopPropagation()
    track.setPointerCapture(event.pointerId)
    const max = node.scrollHeight - node.clientHeight
    if (max <= 0) return
    const rect = track.getBoundingClientRect()
    const thumbPx = Math.max(16, (node.clientHeight / node.scrollHeight) * rect.height)
    const onThumb = (event.target as HTMLElement).classList.contains('flyout-vthumb')
    if (!onThumb) {
      const range = Math.max(1, rect.height - thumbPx)
      const y = event.clientY - rect.top - thumbPx / 2
      node.scrollTop = Math.min(1, Math.max(0, y / range)) * max
    }
    drag.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startScroll: node.scrollTop,
      track,
    }
  }

  function onPointerMove(event: PointerEvent<HTMLSpanElement>) {
    const active = drag.current
    const node = scroller.current
    if (!active || !node || event.pointerId !== active.pointerId) return
    const rect = active.track.getBoundingClientRect()
    const max = node.scrollHeight - node.clientHeight
    const thumbPx = Math.max(16, (node.clientHeight / node.scrollHeight) * rect.height)
    const range = Math.max(1, rect.height - thumbPx)
    node.scrollTop = Math.min(max, Math.max(0, active.startScroll + ((event.clientY - active.startY) / range) * max))
  }

  function onPointerUp(event: PointerEvent<HTMLSpanElement>) {
    if (drag.current?.pointerId === event.pointerId) drag.current = null
  }

  return (
    <>
      <div className="flyout-scroll" ref={scroller}>
        {children}
      </div>
      {thumb.show ? (
        <span
          className="flyout-vscroll"
          role="scrollbar"
          aria-orientation="vertical"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <span
            className="flyout-vthumb"
            style={{ height: `${thumb.height}%`, top: `${thumb.y}%` }}
          />
        </span>
      ) : null}
    </>
  )
}
