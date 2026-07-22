import { useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/* Renderiza os filhos direto no <body>, fora da árvore do app-frame. Modais
   e sheets precisam escapar do contexto de empilhamento das páginas para ficar
   acima da barra de navegação inferior (fixa). */
export function Portal({ children }: { children: ReactNode }) {
  const [container] = useState(() => {
    const node = document.createElement('div')
    node.className = 'lombada-portal'
    return node
  })

  useEffect(() => {
    document.body.appendChild(container)
    return () => {
      container.remove()
    }
  }, [container])

  return createPortal(children, container)
}
