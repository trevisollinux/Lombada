import { apiGet } from '../../services/api'
import type { ReadingProgressSummary } from '../../types/features'

export function getReadingProgress(readingId: number, signal?: AbortSignal): Promise<ReadingProgressSummary> {
  return apiGet<ReadingProgressSummary>(`/api/leitura/${readingId}/progresso`, signal)
}
