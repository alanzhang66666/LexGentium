import { NextResponse } from "next/server"

export const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

type BackendMethod = "GET" | "POST" | "DELETE" | "PATCH"

interface BackendProxyOptions {
  method?: BackendMethod
  body?: unknown
  timeoutMs?: number
  label?: string
  timeoutMessage?: string
  /** @deprecated Accepted for call-site compatibility; browser auth is never forwarded. */
  request?: Request
}

function envBackendToken(): string {
  return (process.env.API_TOKEN || process.env.BACKEND_API_TOKEN || "").trim()
}

/**
 * Server-only auth boundary. The backend token comes exclusively from
 * API_TOKEN / BACKEND_API_TOKEN environment configuration; browser-supplied
 * Authorization headers are never forwarded. Never log the token.
 */
export async function backendAuthHeaders(): Promise<Record<string, string>> {
  const envToken = envBackendToken()
  return envToken ? { Authorization: `Bearer ${envToken}` } : {}
}

const DEFAULT_TIMEOUT_MS = 30000

/**
 * Sanitized BFF error: PublicError envelope, no backend URL, no raw
 * exception text. Connect-level failures -> 502 backend_unavailable;
 * header timeout -> 504 backend_timeout.
 */
function buildErrorResponse(error: unknown, _timeoutMs: number, _label: string, _timeoutMessage?: string) {
  const message = error instanceof Error ? `${error.name} ${error.message}` : String(error)
  const isTimeout = message.includes("AbortError") || message.includes("aborted") || message.includes("TimeoutError")
  const requestId = crypto.randomUUID().replaceAll("-", "")

  return NextResponse.json(
    {
      error: {
        code: isTimeout ? "backend_timeout" : "backend_unavailable",
        message: isTimeout ? "backend response timeout" : "backend unavailable",
        request_id: requestId,
        retriable: true,
        field_errors: [],
      },
    },
    { status: isTimeout ? 504 : 502, headers: { "x-request-id": requestId } },
  )
}

async function relayBackendResponse(response: Response) {
  const text = await response.text()
  try {
    return NextResponse.json(JSON.parse(text), { status: response.status })
  } catch {
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": "text/plain" },
    })
  }
}

export async function parseJsonBody(request: Request) {
  try {
    return { ok: true as const, body: await request.json() }
  } catch (error) {
    return {
      ok: false as const,
      response: NextResponse.json(
        {
          error: "请求体必须是合法 JSON",
          detail: error instanceof Error ? error.message : String(error),
        },
        { status: 400 },
      ),
    }
  }
}

export async function backendFetch(path: string, options: BackendProxyOptions = {}) {
  const {
    method = "GET",
    body,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    label = path,
    timeoutMessage,
  } = options

  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)
    const headers: Record<string, string> = { ...(await backendAuthHeaders()) }
    if (body !== undefined) {
      headers["Content-Type"] = "application/json"
    }
    const response = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers: Object.keys(headers).length ? headers : undefined,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    }).finally(() => clearTimeout(timeout))

    return relayBackendResponse(response)
  } catch (error) {
    console.error(`[${label}] backend proxy error:`, error)
    return buildErrorResponse(error, timeoutMs, label, timeoutMessage)
  }
}

