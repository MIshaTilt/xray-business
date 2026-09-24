import { useEffect, useRef, useState, type ReactNode } from 'react'

const FADE = 72

export function DataTable({ children }: { children: ReactNode }) {
  const scroller = useRef<HTMLDivElement>(null)
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
        <span className="data-table-hscroll" aria-hidden="true">
          <span
            className="data-table-hthumb"
            style={{ width: `${thumb.width}%`, left: `${thumb.x}%` }}
          />
        </span>
      ) : null}
    </div>
  )
}
