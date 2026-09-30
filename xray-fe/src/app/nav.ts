import { flushSync } from 'react-dom'
import type { NavigateFunction, To } from 'react-router'

type GoOptions = { replace?: boolean }

let activeTransition: ViewTransition | null = null
let nextRun: (() => void) | null = null
let nextTo: To | number | null = null
let queuedFrame = 0
let hostLeaving = false
let hostTimer = 0
let chromeGeneration = 0
let capturingTransition = false

export function isViewTransitionCapture() {
  return capturingTransition
}

export function activeViewTransition() {
  return activeTransition
}

function insideHostWebView() {
  const app = window.WebApp ?? window.Telegram?.WebApp
  if (typeof app?.initData === 'string' && app.initData.length > 0) return true
  return /\bwv\b/.test(navigator.userAgent)
}

function stageElement() {
  const stage = document.querySelector('.page-stage:not([data-page-ghost])')
  return stage instanceof HTMLElement ? stage : null
}

function tabBarElement() {
  const bar = document.querySelector('.tab-bar')
  return bar instanceof HTMLElement ? bar : null
}

function pinTabBar() {
  chromeGeneration += 1
  tabBarElement()?.style.setProperty('view-transition-name', 'xray-tabs')
  return chromeGeneration
}

function unpinTabBar(generation: number) {
  if (generation !== chromeGeneration) return
  tabBarElement()?.style.removeProperty('view-transition-name')
}

function markRouteLeave() {
  document.documentElement.classList.add('is-route-leave')
}

function clearRouteLeave() {
  window.requestAnimationFrame(() => {
    document.documentElement.classList.remove('is-route-leave')
  })
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

function quickCompareElement() {
  const node = document.querySelector('.scans-quick-compare-wrap')
  return node instanceof HTMLElement ? node : null
}

function fadeQuickCompare() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const node = quickCompareElement()
  if (!node) return
  node.classList.remove('is-in')
  node.classList.add('is-closing')
}

function settleQuickCompare() {
  const node = quickCompareElement()
  if (!node) return
  node.style.animation = 'none'
  node.getAnimations().forEach((motion) => motion.cancel())
}

function settleStageAnimations() {
  const stage = stageElement()
  if (!stage) return
  stage.querySelectorAll('*').forEach((node) => {
    if (!(node instanceof HTMLElement)) return
    const motions = node.getAnimations()
    if (!motions.length) return
    const style = getComputedStyle(node)
    node.style.animation = 'none'
    node.style.opacity = style.opacity
    if (style.transform && style.transform !== 'none') node.style.transform = style.transform
    motions.forEach((motion) => motion.cancel())
  })
}

function settleTabBar() {
  const bar = tabBarElement()
  if (!bar) return
  bar.querySelectorAll('.is-stretch, .is-drop').forEach((node) => {
    node.classList.remove('is-stretch', 'is-drop')
  })
  void bar.offsetWidth
  bar.getAnimations({ subtree: true }).forEach((motion) => motion.cancel())
}

function pickBarElement() {
  const node = document.querySelector('.scans-pick-bar')
  return node instanceof HTMLElement ? node : null
}

function fadePickBar() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const node = pickBarElement()
  if (!node) return
  node.style.removeProperty('transition')
  node.style.removeProperty('opacity')
  node.classList.remove('is-in')
  node.classList.add('is-closing')
}

function isChatPath(path: string | null | undefined) {
  if (!path) return false
  const bare = path.split('?')[0].split('#')[0]
  return bare === '/chat' || bare.endsWith('/chat')
}

function pathOf(to: To | number | null) {
  if (typeof to === 'number' || to == null) return null
  if (typeof to === 'string') {
    try {
      return new URL(to, window.location.href).pathname
    } catch {
      return null
    }
  }
  return to.pathname ?? null
}

function chatChromeNodes() {
  return [...document.querySelectorAll('.chat-history-nav, .chat-clear-nav.is-on')].flatMap((node) =>
    node instanceof HTMLElement && node.getBoundingClientRect().width > 1 ? [node] : [],
  )
}

function chatChromeName(node: HTMLElement) {
  return node.classList.contains('chat-clear-nav') ? 'xray-chat-clear' : 'xray-chat-history'
}

function settleChatChrome(nodes: HTMLElement[]) {
  for (const node of nodes) {
    const style = getComputedStyle(node)
    const width = style.width
    const opacity = style.opacity
    const marginRight = style.marginRight
    node.style.transition = 'none'
    node.style.animation = 'none'
    node.style.width = width
    node.style.opacity = opacity
    node.style.marginRight = marginRight
    node.getAnimations().forEach((motion) => motion.cancel())
  }
}

function pinChatChrome(nodes: HTMLElement[]) {
  for (const node of nodes) node.style.setProperty('view-transition-name', chatChromeName(node))
}

function unpinChatChrome() {
  document.querySelectorAll('.chat-history-nav, .chat-clear-nav').forEach((node) => {
    if (!(node instanceof HTMLElement)) return
    node.style.removeProperty('view-transition-name')
    node.style.removeProperty('transition')
    node.style.removeProperty('animation')
    node.style.removeProperty('width')
    node.style.removeProperty('opacity')
    node.style.removeProperty('margin-right')
  })
}

function fadeChatChrome() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  chatChromeNodes().forEach((node) => {
    node.getAnimations().forEach((motion) => motion.cancel())
    node.style.animation = 'none'
    node.style.opacity = '0'
  })
}

function begin() {
  const run = nextRun
  const to = nextTo
  nextRun = null
  nextTo = null
  if (!run) return
  clearStageMotion()
  markRouteLeave()
  settleQuickCompare()
  settleStageAnimations()
  const fromChat = isChatPath(window.location.pathname)
  const toPath = pathOf(to)
  const toChat = toPath == null ? fromChat : isChatPath(toPath)
  const leaveChat = fromChat && !toChat
  unpinChatChrome()
  if (leaveChat) {
    const leaving = chatChromeNodes()
    settleChatChrome(leaving)
    pinChatChrome(leaving)
  }
  settleTabBar()
  const chromePin = pinTabBar()
  let pending: ViewTransition
  try {
    pending = document.startViewTransition(() => {
      capturingTransition = true
      try {
        flushSync(run)
      } finally {
        capturingTransition = false
      }
    })
  } catch {
    unpinTabBar(chromePin)
    unpinChatChrome()
    clearStageMotion()
    run()
    clearRouteLeave()
    return
  }
  activeTransition = pending
  void pending.ready.then(() => clearRouteLeave()).catch(() => {})
  void pending.ready.catch(() => {})
  void pending.finished.finally(() => {
    unpinTabBar(chromePin)
    unpinChatChrome()
    if (activeTransition !== pending) return
    activeTransition = null
    clearStageMotion()
    if (nextRun) queue()
  }).catch(() => {})
}

function finishHost() {
  if (!hostLeaving) return
  hostLeaving = false
  window.clearTimeout(hostTimer)
  const stage = stageElement()
  stage?.getAnimations().forEach((motion) => motion.cancel())
  if (stage) {
    stage.style.pointerEvents = ''
    stage.style.opacity = ''
    stage.style.transform = ''
  }
  const run = nextRun
  nextRun = null
  if (run) flushSync(run)
  clearRouteLeave()
  const next = stageElement()
  if (!next) return
  const enter = next.animate(
    [
      { opacity: 0, transform: 'translateY(28px)' },
      { opacity: 1, transform: 'translateY(0px)' },
    ],
    { duration: 320, easing: 'ease', fill: 'forwards' },
  )
  const clear = () => {
    enter.cancel()
    next.style.opacity = ''
    next.style.transform = ''
  }
  window.setTimeout(clear, 340)
  void enter.finished.then(clear).catch(() => undefined)
}

function beginHost() {
  fadeQuickCompare()
  fadePickBar()
  fadeChatChrome()
  const stage = stageElement()
  if (!stage) {
    const run = nextRun
    nextRun = null
    if (run) flushSync(run)
    return
  }
  if (hostLeaving) return
  hostLeaving = true
  markRouteLeave()
  stage.getAnimations().forEach((motion) => motion.cancel())
  stage.style.pointerEvents = 'none'
  const leave = stage.animate(
    [
      { opacity: 1, transform: 'translateY(0px)' },
      { opacity: 0, transform: 'translateY(28px)' },
    ],
    { duration: 320, easing: 'ease', fill: 'forwards' },
  )
  hostTimer = window.setTimeout(() => finishHost(), 340)
  void leave.finished.then(() => finishHost()).catch(() => undefined)
}

function queue() {
  if (queuedFrame) return
  queuedFrame = window.requestAnimationFrame(() => {
    queuedFrame = 0
    begin()
  })
}

export function go(navigate: NavigateFunction, to: To | number, options?: GoOptions) {
  nextTo = to
  nextRun = () => {
    if (typeof to === 'number') navigate(to)
    else navigate(to, options)
  }
  if (insideHostWebView()) {
    beginHost()
    return
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
