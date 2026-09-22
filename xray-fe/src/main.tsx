import { MaxUI } from '@maxhub/max-ui'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './app/App.tsx'
import '@maxhub/max-ui/dist/styles.css'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MaxUI colorScheme="light">
      <App />
    </MaxUI>
  </StrictMode>,
)
