interface ReportResponse {
  reported: boolean
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string | { detail?: string }
    }
    if (typeof payload.detail === 'string') return payload.detail
    if (payload.detail && typeof payload.detail.detail === 'string') return payload.detail.detail
  } catch {
    // Mantém a mensagem genérica quando o servidor não retorna JSON.
  }
  return `Erro ${response.status}`
}

export async function reportReview(readingId: number): Promise<ReportResponse> {
  const response = await fetch(`/api/reviews/${readingId}/report`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ motivo: 'other', detalhe: '' }),
  })

  if (!response.ok) throw new Error(await readError(response))
  return (await response.json()) as ReportResponse
}
