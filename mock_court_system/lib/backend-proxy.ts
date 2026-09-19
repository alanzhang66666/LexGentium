/**
 * Shared BFF JSON proxy. Route handlers declare a server-side
 * `BackendTarget`; they never accept a browser-supplied backend URL.
 *
 * Contract (design.md §BFF Proxy):
 * - Browser Authorization is never forwarded; the backend token comes only
 *   from server-side environment (`backendAuthHeaders`).
 * - `X-Request-Id` is validated/normalized here; `X-Operation-Id` and the
 *   correlation headers are forwarded. If the backend echoes an ID header
 *   it must be identical, otherwise the response is a contract violation.
 * - Connect-level failures -> 502 `backend_unavailable`; waiting for
 *   response headers past `timeoutMs` -> 504 `backend_timeout`; echoed-ID
 *   mismatches -> 502 `backend_contract_violation`.
 * - State-changing methods are gated by an Origin allowlist and a request
 *   body byte limit (403 `origin_forbidden` / 413 `request_too_large`)
 *   before the backend is invoked.
 * - Public errors use the same PublicError envelope as the backend and
 *   never include the backend URL or raw exception text.
 */
import { BACKEND_URL, backendAuthHeaders } from "./backend-fetch"

export const REQUEST_ID_HEADER = "x-request-id"
export const OPERATION_ID_HEADER = "x-operation-id"
export const CORRELATION_HEADERS = [
  "x-operation-id",
  "x-session-id",
  "x-task-id",
  "x-run-id",
  "x-report-id",
  "x-game-id",
] as const

const REQUEST_ID_RE = /^[A-Za-z0-9._-]{16,64}$/
const DEFAULT_TIMEOUT_MS = 30000
const DEFAULT_MAX_BODY_BYTES = 1_048_576
const STATE_CHANGING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"])
const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
])

export interface BackendTarget {
  /** Server-side backend path, e.g. `/conversation/list`. No absolute URLs. */
  path: string
  /** Defaults to the incoming request method. */
  method?: string
  /** Response-header timeout. Defaults to 30s. */
  timeoutMs?: number
  /** Log label; never shown to the client. */
  label?: string
  /** Optional JSON body identity fields that must match the response. */
  expectJsonIds?: Record<string, string>
  /** Per-target body limit override (bytes). */
  maxBodyBytes?: number
}

export function isValidRequestId(value: string | null | undefined): value is string {
  return !!value && REQUEST_ID_RE.test(value)
}

export function newRequestId(): string {
  return crypto.randomUUID().replaceAll("-", "")
}

/** Preserve a valid incoming X-Request-Id, otherwise generate exactly one. */
export function resolveRequestId(request: Request): string {
  const incoming = request.headers.get(REQUEST_ID_HEADER)
  return isValidRequestId(incoming) ? incoming : newRequestId()
}

export function bffError(
  status: number,
  code: string,
  requestId: string,
  message: string,
  retriable = false,
): Response {
  return Response.json(
    {
      error: {
        code,
        message,
        request_id: requestId,
        retriable,
        field_errors: [],
      },
    },
    { status, headers: { [REQUEST_ID_HEADER]: requestId } },
  )
}

function resolveTargetUrl(target: BackendTarget): string {
  const path = target.path
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("://")) {
    throw new Error(`invalid backend target path: ${path}`)
  }
  return `${BACKEND_URL}${path}`
}

function allowedOrigins(request: Request): Set<string> {
  const origins = new Set<string>()
  try {
    origins.add(new URL(request.url).origin)
  } catch {
    /* keep allowlist-only behavior */
  }
  const configured = (process.env.BFF_ALLOWED_ORIGINS || "")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean)
  for (const origin of configured) origins.add(origin)
  return origins
}

/**
 * Early rejection for state-changing requests. Returns an error Response
 * when the Origin is outside the allowlist or Content-Length already
 * exceeds the body limit; null when the request may proceed.
 */
export function guardStateChange(request: Request, maxBodyBytes: number): Response | null {
  const method = request.method.toUpperCase()
  if (!STATE_CHANGING_METHODS.has(method)) return null

  const requestId = resolveRequestId(request)
  const origin = request.headers.get("origin")
  if (origin && !allowedOrigins(request).has(origin)) {
    return bffError(403, "origin_forbidden", requestId, "origin not allowed")
  }

  const contentLength = Number(request.headers.get("content-length") || "0")
  if (Number.isFinite(contentLength) && contentLength > maxBodyBytes) {
    return bffError(413, "request_too_large", requestId, "request body too large")
  }
  return null
}

async function readBoundedBody(
  request: Request,
  maxBodyBytes: number,
): Promise<{ ok: true; body: ArrayBuffer | undefined } | { ok: false }> {
  if (!STATE_CHANGING_METHODS.has(request.method.toUpperCase()) || !request.body) {
    return { ok: true, body: undefined }
  }
  const body = await request.arrayBuffer()
  if (body.byteLength > maxBodyBytes) return { ok: false }
  return { ok: true, body }
}

async function upstreamFetch(
  request: Request,
  target: BackendTarget,
  requestId: string,
  body: ArrayBuffer | undefined,
): Promise<Response> {
  const headers: Record<string, string> = { ...(await backendAuthHeaders()) }
  headers[REQUEST_ID_HEADER] = requestId
  for (const name of CORRELATION_HEADERS) {
    const value = request.headers.get(name)
    if (value) headers[name] = value
  }
  const contentType = request.headers.get("content-type")
  if (body !== undefined && contentType) headers["content-type"] = contentType

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), target.timeoutMs ?? DEFAULT_TIMEOUT_MS)
  try {
    return await fetch(resolveTargetUrl(target), {
      method: (target.method || request.method).toUpperCase(),
      headers,
      body,
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    })
  } finally {
    clearTimeout(timeout)
  }
}

function isConnectError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  const cause = error instanceof Error ? (error.cause as Error | undefined)?.message ?? "" : ""
  const combined = `${message} ${cause}`
  return (
    combined.includes("fetch failed") ||
    combined.includes("ECONNREFUSED") ||
    combined.includes("ECONNRESET") ||
    combined.includes("Failed to fetch") ||
    combined.includes("NetworkError") ||
    combined.includes("ENOTFOUND") ||
    combined.includes("EAI_AGAIN")
  )
}

function isAbortError(error: unknown): boolean {
  const message = error instanceof Error ? `${error.name} ${error.message}` : String(error)
  return message.includes("AbortError") || message.includes("aborted") || message.includes("TimeoutError")
}

/** Backend must echo forwarded identity headers identically when present. */
export function identityEchoViolation(
  response: Response,
  requestId: string,
  operationId: string | null,
): boolean {
  const echoedRequest = response.headers.get(REQUEST_ID_HEADER)
  if (echoedRequest && echoedRequest !== requestId) return true
  if (operationId) {
    const echoedOperation = response.headers.get(OPERATION_ID_HEADER)
    if (echoedOperation && echoedOperation !== operationId) return true
  }
  return false
}

function copyResponseHeaders(upstream: Response, requestId: string): Headers {
  const headers = new Headers()
  for (const [name, value] of upstream.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(name.toLowerCase())) continue
    headers.set(name, value)
  }
  headers.set(REQUEST_ID_HEADER, requestId)
  return headers
}

function mapUpstreamError(error: unknown, requestId: string, label: string): Response {
  console.error(`[${label}] backend proxy error:`, error)
  if (isAbortError(error)) {
    return bffError(504, "backend_timeout", requestId, "backend response timeout", true)
  }
  if (isConnectError(error)) {
    return bffError(502, "backend_unavailable", requestId, "backend unavailable", true)
  }
  return bffError(502, "backend_unavailable", requestId, "backend unavailable", true)
}

/**
 * Opaque JSON proxy: preserves backend status, media type and body bytes;
 * validates echoed identity headers and optional declared JSON IDs.
 */
export async function proxyJson(request: Request, target: BackendTarget): Promise<Response> {
  const requestId = resolveRequestId(request)
  const label = target.label || target.path
  const maxBodyBytes = target.maxBodyBytes ?? Number(process.env.BFF_MAX_BODY_BYTES || DEFAULT_MAX_BODY_BYTES)

  const rejected = guardStateChange(request, maxBodyBytes)
  if (rejected) return rejected

  const bounded = await readBoundedBody(request, maxBodyBytes)
  if (!bounded.ok) {
    return bffError(413, "request_too_large", requestId, "request body too large")
  }

  let upstream: Response
  try {
    upstream = await upstreamFetch(request, target, requestId, bounded.body)
  } catch (error) {
    return mapUpstreamError(error, requestId, label)
  }

  const operationId = request.headers.get(OPERATION_ID_HEADER)
  if (identityEchoViolation(upstream, requestId, operationId)) {
    return bffError(502, "backend_contract_violation", requestId, "backend identity mismatch")
  }

  const body = await upstream.arrayBuffer()
  if (target.expectJsonIds && (upstream.headers.get("content-type") || "").includes("json")) {
    try {
      const payload = JSON.parse(new TextDecoder().decode(body)) as Record<string, unknown>
      for (const [field, expected] of Object.entries(target.expectJsonIds)) {
        const actual = payload[field]
        if (actual !== undefined && String(actual) !== expected) {
          return bffError(502, "backend_contract_violation", requestId, "backend identity mismatch")
        }
      }
    } catch {
      return bffError(502, "backend_contract_violation", requestId, "backend payload unreadable")
    }
  }

  return new Response(body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: copyResponseHeaders(upstream, requestId),
  })
}
