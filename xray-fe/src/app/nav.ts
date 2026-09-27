import type { NavigateFunction, To } from 'react-router'

type GoOptions = { replace?: boolean }

export function go(navigate: NavigateFunction, to: To | number, options?: GoOptions) {
  if (typeof to === 'number') {
    navigate(to)
  } else {
    navigate(to, options)
  }
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
