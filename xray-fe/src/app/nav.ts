import { flushSync } from 'react-dom'
import type { NavigateFunction, To } from 'react-router'

type GoOptions = { replace?: boolean }

let activeTransition: ViewTransition | null = null

export function go(navigate: NavigateFunction, to: To | number, options?: GoOptions) {
  const run = () => {
    if (typeof to === 'number') navigate(to)
    else navigate(to, options)
  }
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce || !document.startViewTransition) {
    activeTransition?.skipTransition()
    activeTransition = null
    run()
    return
  }
  const begin = () => {
    const stage = document.querySelector('.page-stage')
    let pending: ViewTransition
    try {
      pending = document.startViewTransition(() => {
        flushSync(run)
        if (stage instanceof HTMLElement) stage.style.viewTransitionName = 'xray-page-in'
      })
    } catch {
      run()
      return
    }
    activeTransition = pending
    void pending.finished.finally(() => {
      if (activeTransition !== pending) return
      activeTransition = null
      if (stage instanceof HTMLElement) stage.style.removeProperty('view-transition-name')
    })
  }
  if (activeTransition) {
    const previous = activeTransition
    activeTransition = null
    previous.skipTransition()
    window.requestAnimationFrame(begin)
    return
  }
  begin()
}

export type TabName = 'home' | 'scans' | 'chat' | 'menu'

export function backTarget(pathname: string): string {
  const tab = tabOf(pathname)
  if (tab === 'home') return '/'
  if (tab === 'chat') return '/chat'
  if (tab === 'menu') return '/menu'
  const nestedScan = pathname.match(/^\/scan\/([^/]+)\/(?:metric|missing)(?:\/|$)/)
  if (nestedScan) return `/scan/${nestedScan[1]}`
  return '/scans'
}

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
