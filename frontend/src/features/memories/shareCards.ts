import type { Locale } from '../../i18n'
import type {
  ShareCardCoverMode,
  ShareCardOptions,
  ShareCardPayload,
  ShareCardTheme,
} from '../../types/memories'
import type { ShelfReading } from '../../types/reading'
import { periodLabel, progressLabel } from './memoryData'
import { memoriesText } from './memoriesI18n'

export const SHARE_CARD_WIDTH = 1080
export const SHARE_CARD_HEIGHT = 1920

interface CardPalette {
  backgroundA: string
  backgroundB: string
  text: string
  muted: string
  accent: string
  line: string
  panel: string
  texture: string
}

function resolvedTheme(theme: ShareCardTheme): 'light' | 'dark' {
  if (theme === 'light' || theme === 'dark') return theme
  return document.documentElement.dataset.theme === 'light' || document.body.dataset.theme === 'light'
    ? 'light'
    : 'dark'
}

function palette(theme: ShareCardTheme): CardPalette {
  return resolvedTheme(theme) === 'dark'
    ? {
        backgroundA: '#15110E',
        backgroundB: '#35181A',
        text: '#F4EFE6',
        muted: '#CBBFAE',
        accent: '#D6A75B',
        line: 'rgba(244,239,230,.18)',
        panel: 'rgba(244,239,230,.055)',
        texture: 'rgba(255,255,255,.025)',
      }
    : {
        backgroundA: '#F4EDDF',
        backgroundB: '#E2D3BC',
        text: '#342A23',
        muted: '#716454',
        accent: '#9C712D',
        line: 'rgba(52,42,35,.18)',
        panel: 'rgba(255,255,255,.34)',
        texture: 'rgba(52,42,35,.025)',
      }
}

function roundRectPath(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  const r = Math.min(radius, width / 2, height / 2)
  context.beginPath()
  context.moveTo(x + r, y)
  context.arcTo(x + width, y, x + width, y + height, r)
  context.arcTo(x + width, y + height, x, y + height, r)
  context.arcTo(x, y + height, x, y, r)
  context.arcTo(x, y, x + width, y, r)
  context.closePath()
}

function drawTexture(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  color: string,
) {
  context.save()
  context.strokeStyle = color
  context.lineWidth = 1
  for (let position = -height; position < width; position += 34) {
    context.beginPath()
    context.moveTo(position, 0)
    context.lineTo(position + height, height)
    context.stroke()
  }
  context.restore()
}

function drawBackground(context: CanvasRenderingContext2D, colors: CardPalette) {
  const gradient = context.createLinearGradient(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT)
  gradient.addColorStop(0, colors.backgroundA)
  gradient.addColorStop(1, colors.backgroundB)
  context.fillStyle = gradient
  context.fillRect(0, 0, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT)
  drawTexture(context, SHARE_CARD_WIDTH, SHARE_CARD_HEIGHT, colors.texture)
}

function splitLines(
  context: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  maxLines: number,
): string[] {
  const words = text.trim().split(/\s+/).filter(Boolean)
  const lines: string[] = []
  let line = ''
  let truncated = false

  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word
    if (!line || context.measureText(candidate).width <= maxWidth) {
      line = candidate
      continue
    }
    if (lines.length >= maxLines - 1) {
      truncated = true
      break
    }
    lines.push(line)
    line = word
  }
  if (line && lines.length < maxLines) lines.push(line)
  if (truncated && lines.length) {
    let last = lines[lines.length - 1].replace(/[\s.,;:!?…–—-]+$/, '')
    while (last && context.measureText(`${last}…`).width > maxWidth) last = last.slice(0, -1).trimEnd()
    lines[lines.length - 1] = `${last}…`
  }
  return lines.length ? lines : ['']
}

function drawLines(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines: number,
  align: CanvasTextAlign = 'left',
): number {
  context.textAlign = align
  const lines = splitLines(context, text, maxWidth, maxLines)
  lines.forEach((line, index) => context.fillText(line, x, y + index * lineHeight))
  return y + Math.max(0, lines.length - 1) * lineHeight
}

function fitFont(
  context: CanvasRenderingContext2D,
  text: string,
  font: (size: number) => string,
  maxWidth: number,
  maxSize: number,
  minSize: number,
): number {
  let size = maxSize
  while (size > minSize) {
    context.font = font(size)
    if (context.measureText(text).width <= maxWidth) break
    size -= 2
  }
  context.font = font(size)
  return size
}

function proxyCover(url: string): string {
  const value = url.trim()
  if (!value) return ''
  if (value.startsWith('/') || value.startsWith('data:') || value.startsWith('blob:')) return value
  return `/api/capa?url=${encodeURIComponent(value)}`
}

function loadImage(url: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const source = proxyCover(url)
    if (!source) {
      resolve(null)
      return
    }
    const image = new Image()
    image.onload = () => resolve(image.naturalWidth > 4 ? image : null)
    image.onerror = () => resolve(null)
    image.src = source
  })
}

function fitContain(
  image: HTMLImageElement,
  x: number,
  y: number,
  width: number,
  height: number,
) {
  const ratio = Math.min(width / image.naturalWidth, height / image.naturalHeight)
  const renderedWidth = image.naturalWidth * ratio
  const renderedHeight = image.naturalHeight * ratio
  return {
    x: x + (width - renderedWidth) / 2,
    y: y + (height - renderedHeight) / 2,
    width: renderedWidth,
    height: renderedHeight,
  }
}

function bookHue(title: string, author: string): number {
  const source = `${title}|${author}`
  let value = 7
  for (const character of source) value = (value * 31 + character.charCodeAt(0)) % 360
  return value
}

function drawGeneratedCover(
  context: CanvasRenderingContext2D,
  reading: Pick<ShelfReading, 'titulo' | 'autor'>,
  x: number,
  y: number,
  width: number,
  height: number,
  dark: boolean,
) {
  const accent = `hsl(${bookHue(reading.titulo, reading.autor)} 42% ${dark ? '58%' : '38%'})`
  context.save()
  context.fillStyle = 'rgba(0,0,0,.23)'
  context.fillRect(x + 18, y + 22, width, height)
  context.fillStyle = dark ? '#12100E' : '#EFE2C8'
  context.fillRect(x, y, width, height)
  context.strokeStyle = dark ? 'rgba(234,224,205,.52)' : 'rgba(60,44,34,.62)'
  context.lineWidth = 5
  context.strokeRect(x + 44, y + 44, width - 88, height - 88)
  context.lineWidth = 2
  context.strokeRect(x + 66, y + 66, width - 132, height - 132)
  context.fillStyle = accent
  context.fillRect(x + width * 0.28, y + 125, width * 0.44, 7)
  context.textAlign = 'center'
  context.fillStyle = dark ? '#EAE0CD' : '#3C2C22'
  context.font = `600 italic ${Math.min(64, width * 0.14)}px Fraunces, serif`
  drawLines(context, reading.titulo, x + width / 2, y + height * 0.43, width - 140, 68, 3, 'center')
  context.fillStyle = dark ? 'rgba(234,224,205,.76)' : 'rgba(60,44,34,.72)'
  context.font = "400 24px 'Space Mono', monospace"
  drawLines(context, reading.autor, x + width / 2, y + height * 0.68, width - 150, 31, 2, 'center')
  context.fillStyle = accent
  context.font = '600 italic 31px Fraunces, serif'
  context.fillText('lombada.', x + width / 2, y + height - 80)
  context.restore()
}

async function drawBookCover(
  context: CanvasRenderingContext2D,
  reading: Pick<ShelfReading, 'titulo' | 'autor' | 'capa_url'>,
  x: number,
  y: number,
  width: number,
  height: number,
  mode: ShareCardCoverMode,
) {
  const image = mode === 'original' ? await loadImage(reading.capa_url) : null
  if (!image) {
    drawGeneratedCover(context, reading, x, y, width, height, mode === 'editorial-dark')
    return
  }
  const rect = fitContain(image, x, y, width, height)
  context.save()
  context.fillStyle = 'rgba(0,0,0,.22)'
  context.fillRect(rect.x + 16, rect.y + 20, rect.width, rect.height)
  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(image, rect.x, rect.y, rect.width, rect.height)
  context.strokeStyle = 'rgba(255,255,255,.18)'
  context.lineWidth = 2
  context.strokeRect(rect.x, rect.y, rect.width, rect.height)
  context.restore()
}

function starPath(context: CanvasRenderingContext2D, x: number, y: number, radius: number) {
  let angle = -Math.PI / 2
  const step = Math.PI / 5
  context.beginPath()
  context.moveTo(x + Math.cos(angle) * radius, y + Math.sin(angle) * radius)
  for (let index = 0; index < 5; index += 1) {
    angle += step
    context.lineTo(x + Math.cos(angle) * radius * 0.42, y + Math.sin(angle) * radius * 0.42)
    angle += step
    context.lineTo(x + Math.cos(angle) * radius, y + Math.sin(angle) * radius)
  }
  context.closePath()
}

function drawStars(context: CanvasRenderingContext2D, rating: number, x: number, y: number, color: string) {
  for (let index = 0; index < 5; index += 1) {
    const centerX = x + 27 + index * 72
    const fraction = Math.max(0, Math.min(1, rating - index))
    starPath(context, centerX, y, 27)
    context.strokeStyle = color
    context.lineWidth = 3
    context.stroke()
    if (fraction <= 0) continue
    context.save()
    starPath(context, centerX, y, 27)
    context.clip()
    context.fillStyle = color
    context.fillRect(centerX - 27, y - 27, 54 * fraction, 54)
    context.restore()
  }
}

function footer(context: CanvasRenderingContext2D, colors: CardPalette, handle: string) {
  context.strokeStyle = colors.line
  context.lineWidth = 2
  context.beginPath()
  context.moveTo(96, 1765)
  context.lineTo(984, 1765)
  context.stroke()
  context.textAlign = 'left'
  context.fillStyle = colors.muted
  context.font = "400 24px 'Space Mono', monospace"
  context.fillText(handle ? `@${handle}` : 'LOMBADA', 96, 1820)
  context.fillStyle = colors.accent
  context.font = '600 italic 42px Fraunces, serif'
  context.fillText('lombada.', 96, 1875)
}

function diaryProgress(payload: Extract<ShareCardPayload, { kind: 'diary' }>, locale: Locale): string {
  const { entry } = payload
  if (entry.progresso_tipo === 'pagina' && entry.pagina) return `${memoriesText(locale, 'page')} ${entry.pagina}`
  if (entry.progresso_tipo === 'porcentagem' && entry.porcentagem !== null) return `${entry.porcentagem}%`
  if (entry.progresso_tipo === 'capitulo' && entry.capitulo) return `${memoriesText(locale, 'chapter')}: ${entry.capitulo}`
  return ''
}

function excerpt(payload: ShareCardPayload): string {
  if (payload.kind === 'reading') return payload.reading.relato.trim()
  if (payload.kind === 'diary') return payload.entry.nota.trim()
  return ''
}

export function shareCardHasExcerpt(payload: ShareCardPayload): boolean {
  return Boolean(excerpt(payload))
}

export function shareCardHasSpoiler(payload: ShareCardPayload): boolean {
  if (payload.kind === 'reading') return payload.reading.spoiler
  if (payload.kind === 'diary') return payload.entry.spoiler
  return false
}

export function shareCardSupportsCover(payload: ShareCardPayload): boolean {
  return payload.kind === 'reading' || payload.kind === 'diary'
}

export function defaultIncludeExcerpt(payload: ShareCardPayload): boolean {
  return shareCardHasExcerpt(payload) && !shareCardHasSpoiler(payload)
}

function readingEyebrow(payload: Extract<ShareCardPayload, { kind: 'reading' }>, locale: Locale): string {
  return payload.reading.relato.trim()
    ? memoriesText(locale, 'review_card')
    : memoriesText(locale, 'reading_card')
}

async function drawReadingCard(
  context: CanvasRenderingContext2D,
  payload: Extract<ShareCardPayload, { kind: 'reading' | 'diary' }>,
  options: ShareCardOptions,
  locale: Locale,
  colors: CardPalette,
) {
  const reading = payload.reading
  context.textBaseline = 'alphabetic'
  context.textAlign = 'left'
  context.fillStyle = colors.accent
  context.font = "700 26px 'Space Mono', monospace"
  context.fillText('LOMBADA', 96, 90)
  context.fillStyle = colors.muted
  context.font = "400 24px 'Space Mono', monospace"
  context.fillText(
    payload.kind === 'diary' ? memoriesText(locale, 'diary_card') : readingEyebrow(payload, locale),
    96,
    138,
  )

  await drawBookCover(context, reading, 110, 195, 860, 830, options.coverMode)

  let y = 1120
  context.fillStyle = colors.text
  context.font = '500 italic 68px Fraunces, serif'
  y = drawLines(context, reading.titulo, 96, y, 888, 74, 2) + 58
  context.fillStyle = colors.muted
  context.font = 'italic 34px Spectral, serif'
  y = drawLines(context, reading.autor, 96, y, 888, 42, 2) + 68

  if (payload.kind === 'diary') {
    const progress = diaryProgress(payload, locale)
    if (progress) {
      context.fillStyle = colors.accent
      context.font = "700 25px 'Space Mono', monospace"
      y = drawLines(context, progress.toUpperCase(), 96, y, 888, 34, 2) + 45
    }
  } else if (reading.nota !== null && reading.nota > 0) {
    drawStars(context, reading.nota, 96, y, colors.accent)
    y += 70
  } else {
    context.fillStyle = colors.accent
    context.font = "700 24px 'Space Mono', monospace"
    context.fillText(reading.status.toUpperCase(), 96, y)
    y += 46
  }

  const rawExcerpt = excerpt(payload).replace(/\s+/g, ' ').trim()
  if (options.includeExcerpt && rawExcerpt) {
    context.fillStyle = colors.text
    context.font = 'italic 39px Spectral, serif'
    drawLines(context, `“${rawExcerpt}”`, 96, y, 888, 50, Math.max(1, Math.min(5, Math.floor((1730 - y) / 50))))
  } else if (shareCardHasSpoiler(payload) && rawExcerpt) {
    context.fillStyle = colors.muted
    context.font = 'italic 36px Spectral, serif'
    drawLines(context, memoriesText(locale, 'excerpt_spoiler_warning'), 96, y, 888, 46, 2)
  }

  footer(context, colors, payload.handle)
}

function drawMetric(
  context: CanvasRenderingContext2D,
  colors: CardPalette,
  x: number,
  y: number,
  width: number,
  value: string,
  label: string,
  emphasis = false,
) {
  roundRectPath(context, x, y, width, 165, 16)
  context.fillStyle = colors.panel
  context.fill()
  context.strokeStyle = emphasis ? colors.accent : colors.line
  context.lineWidth = 2
  context.stroke()
  context.textAlign = 'left'
  context.fillStyle = colors.text
  context.font = '500 51px Fraunces, serif'
  context.fillText(value, x + 22, y + 72)
  context.fillStyle = colors.muted
  context.font = "700 14px 'Space Mono', monospace"
  drawLines(context, label.toUpperCase(), x + 22, y + 116, width - 44, 18, 2)
}

async function drawPeriodCard(
  context: CanvasRenderingContext2D,
  payload: Extract<ShareCardPayload, { kind: 'period' }>,
  locale: Locale,
  colors: CardPalette,
) {
  const { recap } = payload
  context.textAlign = 'center'
  context.fillStyle = colors.accent
  context.font = "700 26px 'Space Mono', monospace"
  context.fillText('LOMBADA.APP', 540, 85)
  context.fillStyle = colors.text
  context.font = '500 italic 66px Fraunces, serif'
  context.fillText(
    memoriesText(locale, recap.period === 'month' ? 'period_card_month' : 'period_card_week'),
    540,
    170,
  )
  context.fillStyle = colors.muted
  context.font = '400 27px Spectral, serif'
  context.fillText(`${memoriesText(locale, 'reading_memory')} · ${periodLabel(recap, locale)}`, 540, 220)

  const finalMetric = recap.page_sessions_calculable > 0
    ? [recap.pages_advanced, memoriesText(locale, 'pages_advanced')]
    : [recap.sessions, memoriesText(locale, 'updates')]
  const metrics: Array<[number, string]> = [
    [recap.sessions, memoriesText(locale, 'sessions')],
    [recap.active_days, memoriesText(locale, 'active_days')],
    [recap.books_touched, memoriesText(locale, 'books_touched')],
    [Number(finalMetric[0]), String(finalMetric[1])],
  ]
  metrics.forEach(([value, label], index) => {
    const column = index % 2
    const row = Math.floor(index / 2)
    drawMetric(
      context,
      colors,
      95 + column * 455,
      285 + row * 190,
      430,
      value.toLocaleString(locale),
      label,
      index === 3,
    )
  })

  context.textAlign = 'left'
  context.fillStyle = colors.muted
  context.font = "700 17px 'Space Mono', monospace"
  context.fillText(memoriesText(locale, 'highlights').toUpperCase(), 95, 700)

  const positions = [[95, 750], [555, 750], [95, 1130], [555, 1130]]
  for (let index = 0; index < positions.length; index += 1) {
    const highlight = recap.highlights[index]
    if (!highlight) continue
    const [x, y] = positions[index]
    roundRectPath(context, x, y, 430, 335, 16)
    context.fillStyle = colors.panel
    context.fill()
    context.strokeStyle = colors.line
    context.stroke()
    const reading: Pick<ShelfReading, 'titulo' | 'autor' | 'capa_url'> = {
      titulo: highlight.title,
      autor: highlight.author,
      capa_url: highlight.cover_url,
    }
    await drawBookCover(context, reading, x + 18, y + 18, 145, 220, 'original')
    context.fillStyle = colors.text
    context.font = '500 27px Fraunces, serif'
    drawLines(context, highlight.title, x + 182, y + 52, 225, 31, 3)
    context.fillStyle = colors.muted
    context.font = '400 19px Spectral, serif'
    drawLines(context, highlight.author, x + 182, y + 164, 225, 24, 2)
    context.fillStyle = colors.accent
    context.font = "700 14px 'Space Mono', monospace"
    const details = [
      `${highlight.sessions.toLocaleString(locale)} ${memoriesText(locale, 'sessions')}`,
      highlight.pages_advanced > 0 ? `+${highlight.pages_advanced.toLocaleString(locale)} ${memoriesText(locale, 'pages_advanced')}` : '',
      progressLabel(highlight.last_progress, locale),
    ].filter(Boolean).join(' · ')
    drawLines(context, details.toUpperCase(), x + 182, y + 260, 225, 19, 3)
  }
  footer(context, colors, payload.handle)
}

async function drawLibraryCard(
  context: CanvasRenderingContext2D,
  payload: Extract<ShareCardPayload, { kind: 'library' }>,
  locale: Locale,
  colors: CardPalette,
) {
  const { recap } = payload
  context.textAlign = 'center'
  context.fillStyle = colors.accent
  context.font = "700 27px 'Space Mono', monospace"
  context.fillText('LOMBADA · MEMÓRIA DE LEITURA', 540, 115)
  context.fillStyle = colors.text
  context.font = '500 italic 70px Fraunces, serif'
  context.fillText(memoriesText(locale, 'library_card'), 540, 215)
  context.font = '600 260px Fraunces, serif'
  context.fillText(String(recap.readBooks.length), 540, 500)
  context.fillStyle = colors.muted
  context.font = "400 30px 'Space Mono', monospace"
  context.fillText(memoriesText(locale, 'books_read').toUpperCase(), 540, 560)

  const covers = recap.readBooks.slice(0, 5)
  const coverWidth = covers.length >= 5 ? 145 : 165
  const coverHeight = Math.round(coverWidth * 1.5)
  const gap = 24
  let x = (SHARE_CARD_WIDTH - (covers.length * coverWidth + Math.max(0, covers.length - 1) * gap)) / 2
  for (const reading of covers) {
    await drawBookCover(context, reading, x, 650, coverWidth, coverHeight, 'original')
    x += coverWidth + gap
  }

  const metrics: Array<[string, string]> = []
  if (recap.pages > 0) metrics.push([recap.pages.toLocaleString(locale), memoriesText(locale, 'pages_read')])
  if (recap.topAuthor) metrics.push([recap.topAuthor.name, memoriesText(locale, 'top_author')])
  if (recap.averageRating !== null) metrics.push([recap.averageRating.toFixed(1), memoriesText(locale, 'average_rating')])
  if (recap.favorite) metrics.push([recap.favorite.titulo, memoriesText(locale, 'favorite')])

  let y = 1095
  for (const [value, label] of metrics.slice(0, 4)) {
    context.strokeStyle = colors.line
    context.lineWidth = 2
    context.beginPath()
    context.moveTo(220, y - 48)
    context.lineTo(860, y - 48)
    context.stroke()
    context.fillStyle = colors.accent
    context.font = "700 18px 'Space Mono', monospace"
    context.fillText(label.toUpperCase(), 540, y)
    context.fillStyle = colors.text
    fitFont(context, value, (size) => `500 ${size}px Fraunces, serif`, 820, 52, 30)
    drawLines(context, value, 540, y + 64, 820, 58, 2, 'center')
    y += 185
  }
  footer(context, colors, payload.handle)
}

export async function renderShareCard(
  canvas: HTMLCanvasElement,
  payload: ShareCardPayload,
  options: ShareCardOptions,
  locale: Locale,
): Promise<HTMLCanvasElement> {
  canvas.width = SHARE_CARD_WIDTH
  canvas.height = SHARE_CARD_HEIGHT
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Canvas indisponível')
  try {
    await document.fonts.ready
  } catch {
    // O canvas continua com as fontes de fallback do navegador.
  }
  const colors = palette(options.theme)
  drawBackground(context, colors)
  if (payload.kind === 'period') await drawPeriodCard(context, payload, locale, colors)
  else if (payload.kind === 'library') await drawLibraryCard(context, payload, locale, colors)
  else await drawReadingCard(context, payload, options, locale, colors)
  return canvas
}

export function shareCardFilename(payload: ShareCardPayload): string {
  if (payload.kind === 'diary') return 'lombada-diario.png'
  if (payload.kind === 'period') return `lombada-retrospectiva-${payload.recap.period}.png`
  if (payload.kind === 'library') return 'lombada-retrospectiva-estante.png'
  return payload.reading.relato.trim() ? 'lombada-critica.png' : 'lombada-leitura.png'
}

export function shareCardTitle(payload: ShareCardPayload, locale: Locale): string {
  if (payload.kind === 'period') return memoriesText(locale, 'period_title')
  if (payload.kind === 'library') return memoriesText(locale, 'library_title')
  if (payload.kind === 'diary') return payload.reading.titulo
  return payload.reading.titulo
}

export function shareCardText(payload: ShareCardPayload, locale: Locale): string {
  if (payload.kind === 'period') {
    return `${memoriesText(locale, 'period_title')} · ${periodLabel(payload.recap, locale)}`
  }
  if (payload.kind === 'library') {
    return `${payload.recap.readBooks.length} ${memoriesText(locale, 'books_read')} · Lombada`
  }
  if (payload.kind === 'diary') {
    return `${memoriesText(locale, 'diary_card')} · ${payload.reading.titulo}`
  }
  return `${payload.reading.relato.trim() ? memoriesText(locale, 'review_card') : memoriesText(locale, 'reading_card')} · ${payload.reading.titulo}`
}

export function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('Não foi possível exportar a imagem.'))
    }, 'image/png')
  })
}

export async function downloadShareCard(canvas: HTMLCanvasElement, filename: string): Promise<void> {
  const blob = await canvasToBlob(canvas)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1800)
}

export async function shareOrDownloadCard(
  canvas: HTMLCanvasElement,
  payload: ShareCardPayload,
  locale: Locale,
): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const blob = await canvasToBlob(canvas)
  const file = new File([blob], shareCardFilename(payload), { type: 'image/png' })
  const data: ShareData = {
    title: shareCardTitle(payload, locale),
    text: shareCardText(payload, locale),
    files: [file],
  }
  if (navigator.share && (!navigator.canShare || navigator.canShare(data))) {
    try {
      await navigator.share(data)
      return 'shared'
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') return 'cancelled'
    }
  }
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = file.name
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1800)
  return 'downloaded'
}
