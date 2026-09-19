export class ApiError extends Error {
  status: number
  detail?: string
  suggestion?: string
  code?: string
  requestId?: string

  constructor(
    message: string,
    status: number,
    detail?: string,
    suggestion?: string,
    code?: string,
    requestId?: string,
  ) {
    super(message)
    this.status = status
    this.detail = detail
    this.suggestion = suggestion
    this.code = code
    this.requestId = requestId
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  })
  const text = await res.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { error: text }
  }
  if (!res.ok) {
    const payload = (data || {}) as {
      error?: string | { code?: string; message?: string; request_id?: string }
      detail?: unknown
      suggestion?: string
      request_id?: string
    }
    const detailText =
      typeof payload.detail === "string"
        ? payload.detail
        : payload.detail != null
          ? JSON.stringify(payload.detail)
          : undefined
    const errorText =
      typeof payload.error === "string"
        ? payload.error
        : payload.error?.message || undefined
    const code = typeof payload.error === "object" ? payload.error?.code : undefined
    const requestId =
      (typeof payload.error === "object" ? payload.error?.request_id : undefined) ||
      payload.request_id ||
      res.headers.get("x-request-id") ||
      undefined
    throw new ApiError(
      errorText || detailText || `HTTP ${res.status}`,
      res.status,
      detailText,
      payload.suggestion,
      code,
      requestId,
    )
  }
  return data as T
}
