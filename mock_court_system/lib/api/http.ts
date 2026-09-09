import { clientAuthHeaders } from "@/lib/session/unlock"

export class ApiError extends Error {
  status: number
  detail?: string
  suggestion?: string

  constructor(message: string, status: number, detail?: string, suggestion?: string) {
    super(message)
    this.status = status
    this.detail = detail
    this.suggestion = suggestion
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    cache: "no-store",
    ...init,
    headers: {
      ...clientAuthHeaders(),
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
    const payload = (data || {}) as { error?: string; detail?: unknown; suggestion?: string }
    const detailText =
      typeof payload.detail === "string"
        ? payload.detail
        : payload.detail != null
          ? JSON.stringify(payload.detail)
          : undefined
    throw new ApiError(payload.error || detailText || `HTTP ${res.status}`, res.status, detailText, payload.suggestion)
  }
  return data as T
}
