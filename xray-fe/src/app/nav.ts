import { flushSync } from 'react-dom'
import type { NavigateFunction, To } from 'react-router'

type GoOptions = { replace?: boolean }

let activeTransition: ViewTransition | null = null
let nextRun: (() => void) | null = null
let queuedFrame = 0

function stageElement() {
  const stage = document.querySelector('.page-stage:not([data-page-ghost])')
  return stage instanceof HTMLElement ? stage : null
}

function clearStageMotion() {
  document.querySelectorAll('[data-page-ghost]').forEach((node) => node.remove())
  const stage = stageElement()
  if (!stage) return
  stage.style.visibility = ''
  stage.style.pointerEvents = ''
  stage.style.opacity = ''
  stage.style.transform = ''
  stage.style.removeProperty('view-transition-name')
}

function begin() {
  const run = nextRun
  nextRun = null
  if (!run) return
  clearStageMotion()
  const stage = stageElement()
  let pending: ViewTransition
  try {
    pending = document.startViewTransition(() => {
      flushSync(run)
      if (stage instanceof HTMLElement) stage.style.viewTransitionName = 'xray-page-in'
    })
  } catch {
    clearStageMotion()
    run()
    return
  }
  activeTransition = pending
  void pending.finished.finally(() => {
    if (activeTransition !== pending) return
    activeTransition = null
    clearStageMotion()
    if (nextRun) queue()
  })
}

function queue() {
  if (queuedFrame) return
  queuedFrame = window.requestAnimationFrame(() => {
    queuedFrame = 0
    begin()
  })
}

export function go(navigate: NavigateFunction, to: To | number, options?: GoOptions) {
  nextRun = () => {
    if (typeof to === 'number') navigate(to)
    else navigate(to, options)
  }
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce || !document.startViewTransition) {
    activeTransition?.skipTransition()
    activeTransition = null
    clearStageMotion()
    const run = nextRun
    nextRun = null
    run()
    return
  }
  if (activeTransition || queuedFrame) {
    if (activeTransition) {
      const previous = activeTransition
      activeTransition = null
      clearStageMotion()
      previous.skipTransition()
    }
    queue()
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
