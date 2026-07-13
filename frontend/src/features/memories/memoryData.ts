import type { Locale } from '../../i18n'
import type { LibraryRecap, PeriodRecap, PeriodRecapProgress } from '../../types/memories'
import type { ShelfReading } from '../../types/reading'
import { memoriesText } from './memoriesI18n'

export function buildLibraryRecap(readings: ShelfReading[]): LibraryRecap {
  const readBooks = readings.filter((reading) => reading.status === 'Lido')
  const pages = readBooks.reduce((total, reading) => total + Math.max(0, Number(reading.paginas) || 0), 0)
  const ratedBooks = readBooks.filter((reading) => Number(reading.nota) > 0)
  const averageRating = ratedBooks.length
    ? ratedBooks.reduce((total, reading) => total + Number(reading.nota), 0) / ratedBooks.length
    : null
  const favorite = ratedBooks.length
    ? [...ratedBooks].sort((a, b) => Number(b.nota) - Number(a.nota))[0]
    : null

  const byAuthor = new Map<string, ShelfReading[]>()
  for (const reading of readBooks) {
    const author = reading.autor.trim()
    if (!author) continue
    byAuthor.set(author, [...(byAuthor.get(author) || []), reading])
  }
  const topAuthorEntry = [...byAuthor.entries()].sort((a, b) => {
    if (b[1].length !== a[1].length) return b[1].length - a[1].length
    return a[0].localeCompare(b[0])
  })[0]

  return {
    readBooks,
    pages,
    ratedBooks,
    averageRating,
    favorite,
    topAuthor: topAuthorEntry ? { name: topAuthorEntry[0], books: topAuthorEntry[1] } : null,
  }
}

function parseDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year || 1970, Math.max(0, (month || 1) - 1), day || 1, 12)
}

export function periodLabel(recap: PeriodRecap, locale: Locale): string {
  const start = parseDate(recap.start_date)
  const end = parseDate(recap.end_date)
  if (recap.period === 'month') {
    return new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric' }).format(start)
  }
  const sameMonth = start.getMonth() === end.getMonth() && start.getFullYear() === end.getFullYear()
  const startText = new Intl.DateTimeFormat(locale, sameMonth
    ? { day: '2-digit' }
    : { day: '2-digit', month: 'short' }).format(start)
  const endText = new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', year: 'numeric' }).format(end)
  return `${startText} – ${endText}`
}

export function progressLabel(progress: PeriodRecapProgress, locale: Locale): string {
  if (progress.type === 'page' && progress.value !== undefined) {
    return `${memoriesText(locale, 'page')} ${progress.value.toLocaleString(locale)}`
  }
  if (progress.type === 'percentage' && progress.value !== undefined) {
    return `${progress.value.toLocaleString(locale)}%`
  }
  if (progress.type === 'chapter' && progress.label) {
    return `${memoriesText(locale, 'chapter')}: ${progress.label}`
  }
  return ''
}
