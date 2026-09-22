import { Button, Typography } from '@maxhub/max-ui'
import { useRef } from 'react'

function kindOf(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'csv') return 'CSV'
  if (ext === 'xlsx' || ext === 'xls') return 'Excel'
  return 'Файл'
}

function sizeOf(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

export function FileDrop({
  file,
  busy,
  onPick,
  onSend,
}: {
  file: File | null
  busy: boolean
  onPick: (file: File) => void
  onSend: () => void
}) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="file-drop">
      <input
        ref={input}
        className="file-input"
        type="file"
        accept=".csv,.xlsx,.xls"
        onChange={(event) => {
          const next = event.target.files?.[0]
          if (next) onPick(next)
          event.target.value = ''
        }}
      />
      <Button className="action action-primary" type="button" size="large" stretched variant="primary" onClick={() => input.current?.click()}>
        Загрузить файл
      </Button>
      {file ? (
        <div className="file-card">
          <Typography.Body variant="medium-strong">{file.name}</Typography.Body>
          <Typography.Label variant="small">
            {sizeOf(file.size)} · {kindOf(file.name)}
          </Typography.Label>
          <Button className="action action-secondary" type="button" size="medium" stretched variant="secondary" loading={busy} onClick={onSend}>
            Отправить таблицу
          </Button>
        </div>
      ) : null}
    </div>
  )
}
