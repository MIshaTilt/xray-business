import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { InsetVScroll } from './InsetVScroll.tsx'

type Option = { value: string; label: string }

export function FlyoutSelect({
  value,
  placeholder = 'Не выбрано',
  options,
  open,
  closing,
  onToggle,
  onChange,
}: {
  value: string
  placeholder?: string
  options: Option[]
  open: boolean
  closing: boolean
  onToggle: () => void
  onChange: (value: string) => void
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState<{
    top: number
    left: number
    width: number
    fontFamily: string
    fontSize: string
  } | null>(null)
  const selected = options.find((option) => option.value === value)
  const shown = open || closing

  useLayoutEffect(() => {
    if (!shown) {
      setBox(null)
      return
    }
    const node = wrapRef.current
    if (!node) return
    function place() {
      const trigger = (node.querySelector('.field-select-btn') ?? node) as HTMLElement
      const rect = trigger.getBoundingClientRect()
      const style = window.getComputedStyle(trigger)
      setBox({
        top: rect.bottom + window.scrollY + 8,
        left: rect.left + window.scrollX,
        width: rect.width,
        fontFamily: style.fontFamily,
        fontSize: style.fontSize,
      })
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [shown])

  const menu = shown && box
    ? createPortal(
        <div
          className={`template-dropdown-menu is-portal${closing ? ' is-closing' : ''}`}
          style={{
            top: box.top,
            left: box.left,
            width: box.width,
            right: 'auto',
            fontFamily: box.fontFamily,
            fontSize: box.fontSize,
          }}
        >
          <InsetVScroll watch={`${shown}:${options.length}:${box.width}`}>
            <button
              type="button"
              className={`template-item-btn${value ? '' : ' is-current'}`}
              onClick={() => onChange('')}
            >
              {placeholder}
            </button>
            {options.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`template-item-btn${value === option.value ? ' is-current' : ''}`}
                onClick={() => onChange(option.value)}
              >
                {option.label}
              </button>
            ))}
          </InsetVScroll>
        </div>,
        document.body,
      )
    : null

  return (
    <div ref={wrapRef} className="template-dropdown-wrapper field-dropdown">
      <button
        type="button"
        className="action action-secondary field-select-btn"
        aria-expanded={open && !closing}
        onClick={onToggle}
      >
        <span className="template-label">
          <span className={selected ? '' : 'field-select-placeholder'}>
            {selected ? selected.label : placeholder}
          </span>
          <span className={`template-caret${open && !closing ? ' open' : ''}`} aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M6 9.5 12 15.5 18 9.5" />
            </svg>
          </span>
        </span>
      </button>
      {menu}
    </div>
  )
}
