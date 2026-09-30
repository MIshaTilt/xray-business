export function XRayLogo({ scanning = false }: { scanning?: boolean }) {
  return (
    <svg className="xray-logo" viewBox="0 0 80 80" aria-hidden="true">
      <g fill="#128a82">
        <rect x="33" y="8" width="14" height="64" rx="7" transform="rotate(42 40 40)" />
        <rect x="33" y="8" width="14" height="64" rx="7" transform="rotate(-42 40 40)" />
      </g>
      <rect x="6" y="33" width="68" height="14" rx="7" fill="#1b2430" />
      <rect x="9.5" y="36.4" width="61" height="7.2" rx="3.6" fill="#d8fff8" />
      <circle cx="40" cy="40" r="4.2" fill="#128a82">
        {scanning ? (
          <animate
            attributeName="cx"
            values="18;62;18"
            dur="1.35s"
            repeatCount="indefinite"
            calcMode="spline"
            keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
          />
        ) : null}
      </circle>
    </svg>
  )
}
