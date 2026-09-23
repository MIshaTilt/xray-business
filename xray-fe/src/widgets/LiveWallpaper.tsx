import { useMemo } from 'react'

function between(min: number, max: number) {
  return min + Math.random() * (max - min)
}

export function LiveWallpaper() {
  const field = useMemo(() => {
    const grays = ['255,255,255', '214,232,226', '186,214,204', '156,196,184']
    return {
      shimmer: between(14, 26),
      clouds: Array.from({ length: 5 }, (_, id) => ({
        id,
        x: between(-12, 78),
        y: between(-18, 72),
        w: between(34, 68),
        h: between(24, 52),
        duration: between(16, 36),
        delay: between(-28, 0),
        opacity: between(0.28, 0.55),
        tone: grays[id % grays.length],
      })),
    }
  }, [])

  return (
    <div className="live-wallpaper" aria-hidden="true">
      {field.clouds.map((cloud) => (
        <span
          key={cloud.id}
          className="live-cloud"
          style={{
            left: `${cloud.x}%`,
            top: `${cloud.y}%`,
            width: `${cloud.w}vmax`,
            height: `${cloud.h}vmax`,
            ['--cloud' as string]: cloud.tone,
            ['--cloud-opacity' as string]: cloud.opacity,
            animationDuration: `${cloud.duration}s`,
            animationDelay: `${cloud.delay}s`,
          }}
        />
      ))}
      <span className="live-shimmer live-shimmer-light" style={{ animationDuration: `${field.shimmer}s` }} />
      <span className="live-shimmer live-shimmer-dark" style={{ animationDuration: `${field.shimmer}s` }} />
    </div>
  )
}
