import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import './styles.css'
import './features/shelf/shelf.css'
import './features/shelf/reading-editor.css'
import './features/diary/diary.css'
import './features/catalog/catalog.css'
import './features/explore/explore.css'
import './features/feed/feed.css'
import './features/profile/profile.css'
import './features/memories/memories.css'
import './features/progress/progress.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Elemento #root não encontrado')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

/* PWA: o sw.js cacheia o shell (offline + instalável). Só em produção —
   no dev o Vite serve módulos soltos e o worker atrapalharia o HMR. */
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register(`${import.meta.env.BASE_URL}sw.js`)
      .catch(() => {})
  })
}
