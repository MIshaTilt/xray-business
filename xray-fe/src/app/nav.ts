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

export function tabOf(pathname: string): 'home' | 'scans' | 'chat' | 'menu' {
  if (pathname.startsWith('/menu') || pathname.startsWith('/settings')) return 'menu'
  if (pathname.startsWith('/templates')) return 'home'
  if (pathname === '/scans' || pathname.startsWith('/scans/')) return 'scans'
  if (pathname.endsWith('/chat') || pathname === '/chat') return 'chat'
  if (pathname === '/') return 'home'
  return 'scans'
}
