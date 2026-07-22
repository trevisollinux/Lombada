import type { ReactNode } from 'react'

/* Como no app legado: o cabeçalho de página é só o título serif —
   sem eyebrow/tagline por cima. */
interface PageHeaderProps {
  title: string
  /** Exibida como tooltip no título, nunca como texto corrido na tela. */
  description?: string
  aside?: ReactNode
}

export function PageHeader({ title, description, aside }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div title={description || undefined}>
        <h1>{title}</h1>
      </div>
      {aside && <div className="page-header__aside">{aside}</div>}
    </header>
  )
}
