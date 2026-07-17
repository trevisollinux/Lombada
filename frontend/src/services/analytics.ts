export type ProductEventName =
  | 'app_opened'
  | 'search_submitted'
  | 'book_opened'
  | 'reading_created'
  | 'reading_updated'
  | 'progress_logged'
  | 'progress_feedback'
  | 'period_recap'
  | 'literary_reaction'
  | 'share_started'
  | 'profile_connected'

type ProductEventProperties = Record<string, string | boolean>

interface QueuedEvent {
  event: ProductEventName
  properties: ProductEventProperties
  client_event_id: string
}

const MAX_BATCH_SIZE = 10
const FLUSH_DELAY_MS = 1200
const queue: QueuedEvent[] = []
let analyticsEnabled = false
let flushing = false
let flushTimer: number | null = null
let listenersInstalled = false

function eventId(): string {
  try {
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  } catch {
    // Usa o fallback sem interromper a ação principal.
  }
  return `evt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 14)}`
}

function scheduleFlush() {
  if (!analyticsEnabled || flushTimer !== null || queue.length === 0) return
  flushTimer = window.setTimeout(() => {
    flushTimer = null
    void flushProductEvents()
  }, FLUSH_DELAY_MS)
}

function installLifecycleListeners() {
  if (listenersInstalled || typeof window === 'undefined') return
  listenersInstalled = true
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') void flushProductEvents()
  })
  window.addEventListener('pagehide', () => {
    void flushProductEvents()
  })
}

export function setProductAnalyticsEnabled(enabled: boolean) {
  analyticsEnabled = enabled
  installLifecycleListeners()
  if (!enabled) {
    queue.splice(0)
    if (flushTimer !== null) window.clearTimeout(flushTimer)
    flushTimer = null
    return
  }
  scheduleFlush()
}

export function trackProductEvent(event: ProductEventName, properties: ProductEventProperties = {}): boolean {
  try {
    if (!analyticsEnabled) return false
    queue.push({ event, properties, client_event_id: eventId() })
    if (queue.length >= MAX_BATCH_SIZE) void flushProductEvents()
    else scheduleFlush()
    return true
  } catch {
    return false
  }
}

export async function flushProductEvents(): Promise<boolean> {
  if (flushTimer !== null) {
    window.clearTimeout(flushTimer)
    flushTimer = null
  }
  if (!analyticsEnabled || flushing || queue.length === 0) return false

  flushing = true
  const events = queue.splice(0, MAX_BATCH_SIZE)
  try {
    const response = await fetch('/api/events', {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      keepalive: true,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ events }),
    })
    return response.ok
  } catch {
    return false
  } finally {
    flushing = false
    if (analyticsEnabled && queue.length > 0) scheduleFlush()
  }
}
