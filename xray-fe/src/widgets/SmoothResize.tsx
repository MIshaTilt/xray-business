import { useLayoutEffect, useRef, type ReactNode } from 'react'

const EASE = 'height 0.34s cubic-bezier(0.16, 1, 0.3, 1)'

export function SmoothResize({
  children,
  className,
  appear = false,
  collapse = false,
}: {
  children: ReactNode
  className?: string
  appear?: boolean
  collapse?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const prev = useRef<number | null>(null)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const target = collapse ? 0 : el.scrollHeight
    const from = prev.current
    prev.current = target
    if (reduce || (from != null && Math.abs(target - from) < 1)) return

    const clear = () => {
      if (collapse) return
      el.style.height = ''
      el.style.overflow = ''
      el.style.transition = ''
      prev.current = el.scrollHeight
    }
    const done = (event: TransitionEvent) => {
      if (event.propertyName !== 'height' || event.target !== el) return
      el.removeEventListener('transitionend', done)
      clear()
    }

    const start = from == null ? 0 : el.style.height !== '' ? el.getBoundingClientRect().height : from
    if (from == null && !appear) return

    el.style.overflow = 'hidden'
    el.style.transition = 'none'
    el.style.height = `${start}px`
    void el.offsetHeight
    el.style.transition = EASE
    el.style.height = `${target}px`
    el.addEventListener('transitionend', done)
    return () => el.removeEventListener('transitionend', done)
  })

  return (
    <div ref={ref} className={className} style={{ boxSizing: 'border-box' }}>
      <div className="smooth-resize-inner">{children}</div>
    </div>
  )
}
