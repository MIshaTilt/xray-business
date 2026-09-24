import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'

const FADE = 72

export function DataTable({ children }: { children: ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null)
  const drag = useRef<{ pointerId: number; startX: number; startScroll: number; track: HTMLElement } | null>(null)
  const [left, setLeft] = useState(0)
  const [right, setRight] = useState(0)
  const [thumb, setThumb] = useState({ width: 0, x: 0, show: false })

  useEffect(() => {
    const node = scroller.current
    if (!node) return

    function update() {
      if (!node) return
      const max = node.scrollWidth - node.clientWidth
      setLeft(max <= 0 ? 0 : Math.min(1, node.scrollLeft / FADE))
      setRight(max <= 0 ? 0 : Math.min(1, (max - node.scrollLeft) / FADE))
      if (max <= 2) {
        setThumb({ width: 0, x: 0, show: false })
        return
      }
      const width = Math.max(12, (node.clientWidth / node.scrollWidth) * 100)
      const x = (node.scrollLeft / max) * (100 - width)
      setThumb({ width, x, show: true })
    }

    update()
    node.addEventListener('scroll', update, { passive: true })
    const observer = new ResizeObserver(update)
    observer.observe(node)
    if (node.firstElementChild) observer.observe(node.firstElementChild)
    return () => {
      node.removeEventListener('scroll', update)
      observer.disconnect()
    }
  }, [])

  function seek(clientX: number, track: HTMLElement) {
    const node = scroller.current
    if (!node) return
    const max = node.scrollWidth - node.clientWidth
    if (max <= 0) return
    const rect = track.getBoundingClientRect()
    const thumbPx = Math.max(12, (node.clientWidth / node.scrollWidth) * rect.width)
    const range = Math.max(1, rect.width - thumbPx)
    const x = clientX - rect.left - thumbPx / 2
    node.scrollLeft = Math.min(1, Math.max(0, x / range)) * max
  }

  function onPointerDown(event: PointerEvent<HTMLSpanElement>) {
    const node = scroller.current
    const track = event.currentTarget
    if (!node) return
    event.preventDefault()
    track.setPointerCapture(event.pointerId)
    const onThumb = (event.target as HTMLElement).classList.contains('data-table-hthumb')
    if (!onThumb) seek(event.clientX, track)
    drag.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScroll: node.scrollLeft,
      track,
    }
  }

  function onPointerMove(event: PointerEvent<HTMLSpanElement>) {
    const active = drag.current
    const node = scroller.current
    if (!active || !node || event.pointerId !== active.pointerId) return
    const rect = active.track.getBoundingClientRect()
    const max = node.scrollWidth - node.clientWidth
    const thumbPx = Math.max(12, (node.clientWidth / node.scrollWidth) * rect.width)
    const range = Math.max(1, rect.width - thumbPx)
    node.scrollLeft = Math.min(max, Math.max(0, active.startScroll + ((event.clientX - active.startX) / range) * max))
  }

  function onPointerUp(event: PointerEvent<HTMLSpanElement>) {
    if (drag.current?.pointerId === event.pointerId) drag.current = null
  }

  return (
    <div className="data-table">
      <span className="data-table-edge data-table-edge-left" style={{ ['--edge' as string]: left }} aria-hidden="true">
        <span className="data-table-edge-blur" />
      </span>
      <span className="data-table-edge data-table-edge-right" style={{ ['--edge' as string]: right }} aria-hidden="true">
        <span className="data-table-edge-blur" />
      </span>
      <div className="data-table-scroll" ref={scroller}>
        {children}
      </div>
      {thumb.show ? (
        <span
          className="data-table-hscroll"
          role="scrollbar"
          aria-orientation="horizontal"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(thumb.x)}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <span
            className="data-table-hthumb"
            style={{ width: `${thumb.width}%`, left: `${thumb.x}%` }}
          />
        </span>
      ) : null}
    </div>
  )
}
