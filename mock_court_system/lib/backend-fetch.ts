import { NextResponse } from "next/server"

export const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000"

type BackendMethod = "GET" | "POST" | "DELETE"

interface BackendProxyOptions {
  method?: BackendMethod
  body?: unknown
  timeoutMs?: number
  label?: string
  timeoutMessage?: string
}

const DEFAULT_TIMEOUT_MS = 30000

function isConnectionError(message: string): boolean {
  return (
    message.includes("fetch failed") ||
    message.includes("ECONNREFUSED") ||
    message.includes("Failed to fetch") ||
    message.includes("NetworkError")
  )
}

function buildErrorResponse(error: unknown, timeoutMs: number, label: string, timeoutMessage?: string) {
  const message = error instanceof Error ? error.message : String(error)
  const isTimeout = message.includes("aborted") || message.includes("AbortError")
  const cannotConnect = isConnectionError(message)

  return NextResponse.json(
    {
      error: isTimeout ? "请求超时" : cannotConnect ? "无法连接到后端服务器" : "Internal server error",
      detail: message,
      backend_url: BACKEND_URL,
      suggestion: isTimeout
        ? timeoutMessage || `后端处理超时（>${timeoutMs / 1000}s）。可稍后重试。`
        : cannotConnect
          ? `请确保后端服务器正在运行 (python api_server.py)，并且地址为 ${BACKEND_URL}`
          : undefined,
      source: label,
    },
    { status: 500 },
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
    const response = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
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

