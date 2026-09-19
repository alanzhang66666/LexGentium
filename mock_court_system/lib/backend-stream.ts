/**
 * Shared BFF SSE proxy. Streams are forwarded opaquely: no parsing, no
 * reordering, no re-serialization of event bytes, and the backend status
 * is preserved rather than pinned to 200.
 *
 * Same auth/identity/timeout rules as `proxyJson` — see backend-proxy.ts.
 */
import {
  BackendTarget,
  bffError,
  guardStateChange,
  identityEchoViolation,
  OPERATION_ID_HEADER,
  REQUEST_ID_HEADER,
} from "./backend-proxy"
import { BACKEND_URL, backendAuthHeaders } from "./backend-fetch"
import { CORRELATION_HEADERS, resolveRequestId } from "./backend-proxy"

const DEFAULT_TIMEOUT_MS = 30000
const DEFAULT_MAX_BODY_BYTES = 1_048_576
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

function resolveTargetUrl(target: BackendTarget): string {
  const path = target.path
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("://")) {
    throw new Error(`invalid backend target path: ${path}`)
  }
  return `${BACKEND_URL}${path}`
}

function isAbortError(error: unknown): boolean {
  const message = error instanceof Error ? `${error.name} ${error.message}` : String(error)
  return message.includes("AbortError") || message.includes("aborted") || message.includes("TimeoutError")
}

/**
 * Opaque SSE proxy: forwards request bytes, preserves backend status and
 * content-type, and relays the body stream untouched.
 */
export async function proxySse(request: Request, target: BackendTarget): Promise<Response> {
  const requestId = resolveRequestId(request)
  const label = target.label || target.path
  const maxBodyBytes = target.maxBodyBytes ?? Number(process.env.BFF_MAX_BODY_BYTES || DEFAULT_MAX_BODY_BYTES)

  const rejected = guardStateChange(request, maxBodyBytes)
  if (rejected) return rejected

  let body: ArrayBuffer | undefined
  if (request.body) {
    const bytes = await request.arrayBuffer()
    if (bytes.byteLength > maxBodyBytes) {
      return bffError(413, "request_too_large", requestId, "request body too large")
    }
    body = bytes
  }

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
  let upstream: Response
  try {
    upstream = await fetch(resolveTargetUrl(target), {
      method: (target.method || request.method).toUpperCase(),
      headers,
      body,
      signal: controller.signal,
      cache: "no-store",
      redirect: "manual",
    })
  } catch (error) {
    console.error(`[${label}] backend stream proxy error:`, error)
    if (isAbortError(error)) {
      return bffError(504, "backend_timeout", requestId, "backend response timeout", true)
    }
    return bffError(502, "backend_unavailable", requestId, "backend unavailable", true)
  } finally {
    clearTimeout(timeout)
  }

  const operationId = request.headers.get(OPERATION_ID_HEADER)
  if (identityEchoViolation(upstream, requestId, operationId)) {
    return bffError(502, "backend_contract_violation", requestId, "backend identity mismatch")
  }

  if (!upstream.body) {
    return bffError(502, "backend_unavailable", requestId, "backend returned no stream", true)
  }

  const responseHeaders = new Headers()
  for (const [name, value] of upstream.headers.entries()) {
    if (HOP_BY_HOP_HEADERS.has(name.toLowerCase())) continue
    responseHeaders.set(name, value)
  }
  if (!responseHeaders.has("content-type")) {
    responseHeaders.set("content-type", "text/event-stream; charset=utf-8")
  }
  responseHeaders.set("cache-control", "no-cache")
  responseHeaders.set("x-accel-buffering", "no")
  responseHeaders.set(REQUEST_ID_HEADER, requestId)

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}
