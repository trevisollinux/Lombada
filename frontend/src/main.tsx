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

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Elemento #root não encontrado')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
