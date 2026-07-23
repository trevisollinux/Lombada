import { useEffect, type CSSProperties } from 'react'
import { useNavigate } from 'react-router'

import { Portal } from '../../components/Portal'
import type { Locale } from '../../i18n'

interface PostReadCelebrationProps {
  locale: Locale
  title: string
  milestone: number
  onClose: () => void
}

const CONFETTI_COLORS = ['#8B2E1F', '#6B1F1F', '#D45C68', '#C9A227', '#4A6B4F']

const copy = {
  'pt-BR': {
    kicker: 'pós-leitura',
    title: 'Leitura registrada.',
    message: (t: string) => `${t} foi adicionado aos seus livros lidos.`,
    milestone: (n: number) => `seu ${n}º livro lido`,
    share: 'Compartilhar leitura',
    diary: 'Escrever no diário',
    shelf: 'Ver na estante',
    later: 'Agora não',
    untitled: 'Livro sem título',
  },
  en: {
    kicker: 'after reading',
    title: 'Reading logged.',
    message: (t: string) => `${t} was added to your read books.`,
    milestone: (n: number) => `your ${ordinal(n)} book read`,
    share: 'Share reading',
    diary: 'Write in the diary',
    shelf: 'See on the shelf',
    later: 'Not now',
    untitled: 'Untitled book',
  },
  es: {
    kicker: 'tras la lectura',
    title: 'Lectura registrada.',
    message: (t: string) => `${t} se añadió a tus libros leídos.`,
    milestone: (n: number) => `tu ${n}º libro leído`,
    share: 'Compartir lectura',
    diary: 'Escribir en el diario',
    shelf: 'Ver en la estantería',
    later: 'Ahora no',
    untitled: 'Libro sin título',
  },
} as const

function ordinal(n: number): string {
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`
  switch (n % 10) {
    case 1: return `${n}st`
    case 2: return `${n}nd`
    case 3: return `${n}rd`
    default: return `${n}th`
  }
}

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export function PostReadCelebration({ locale, title, milestone, onClose }: PostReadCelebrationProps) {
  const navigate = useNavigate()
  const c = copy[locale]

  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [onClose])

  function go(path: string) {
    onClose()
    navigate(path)
  }

  const reduced = prefersReducedMotion()

  return (
    <Portal>
      <div className="panel-layer post-read" role="presentation">
        <button className="panel-backdrop" type="button" aria-label={c.later} onClick={onClose} />
        {!reduced && (
          <div className="confetti" aria-hidden="true">
            {Array.from({ length: 26 }, (_, index) => (
              <i
                key={index}
                style={{
                  left: `${Math.random() * 100}vw`,
                  background: CONFETTI_COLORS[index % CONFETTI_COLORS.length],
                  borderRadius: index % 3 === 0 ? '50%' : undefined,
                  '--dx': `${(Math.random() - 0.5) * 160}px`,
                  '--dur': `${1200 + Math.random() * 900}ms`,
                  '--delay': `${Math.random() * 280}ms`,
                  '--rot': `${Math.random() * 720 - 360}deg`,
                } as CSSProperties}
              />
            ))}
          </div>
        )}
        <section className="post-read__card" role="dialog" aria-modal="true" aria-labelledby="post-read-title">
          <p className="post-read__kicker">{c.kicker}</p>
          <h2 id="post-read-title">{c.title}</h2>
          <p className="post-read__message">{c.message(title.trim() || c.untitled)}</p>
          {milestone > 0 && <div className="post-read__milestone">📚 {c.milestone(milestone)}</div>}
          <div className="post-read__actions">
            <button type="button" className="button button--primary" onClick={() => go('/memorias')}>
              {c.share}
            </button>
            <button type="button" className="button button--secondary" onClick={() => go('/diario')}>
              {c.diary}
            </button>
            <button type="button" className="button button--secondary" onClick={() => go('/estante')}>
              {c.shelf}
            </button>
          </div>
          <button type="button" className="text-button post-read__later" onClick={onClose}>
            {c.later}
          </button>
        </section>
      </div>
    </Portal>
  )
}
