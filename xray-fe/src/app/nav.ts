import { flushSync } from 'react-dom'
import type { NavigateFunction, To } from 'react-router'

type GoOptions = { replace?: boolean }

export function go(navigate: NavigateFunction, to: To | number, options?: GoOptions) {
  const run = () => {
    if (typeof to === 'number') navigate(to)
    else navigate(to, options)
  }
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const start = document.startViewTransition?.bind(document)
  if (reduce || !start) {
    run()
    return
  }
  start(() => {
    flushSync(run)
  })
}

export type TabName = 'home' | 'scans' | 'chat' | 'menu'

export function tabOf(pathname: string): TabName {
  if (pathname.startsWith('/menu') || pathname.startsWith('/settings')) return 'menu'
  if (pathname.endsWith('/chat') || pathname === '/chat') return 'chat'
  if (
    pathname === '/' ||
    pathname.startsWith('/templates') ||
    pathname.startsWith('/mapping') ||
    pathname.startsWith('/processing')
  ) {
    return 'home'
  }
  return 'scans'
}
