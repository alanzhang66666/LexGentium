import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { proxySse } from "./backend-stream"

const ENV_KEYS = ["API_TOKEN", "BACKEND_API_TOKEN", "BFF_ALLOWED_ORIGINS", "BFF_MAX_BODY_BYTES"] as const
const VALID_REQ_ID = "c".repeat(32)

let savedEnv: Record<string, string | undefined>
let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  savedEnv = {}
  for (const key of ENV_KEYS) {
    savedEnv[key] = process.env[key]
    delete process.env[key]
  }
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  for (const key of ENV_KEYS) {
    if (savedEnv[key] === undefined) delete process.env[key]
    else process.env[key] = savedEnv[key]
  }
  vi.unstubAllGlobals()
})

function sseUpstream(chunks: string[], init: { status?: number; headers?: Record<string, string> } = {}) {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
  return new Response(stream, {
    status: init.status ?? 200,
    headers: { "content-type": "text/event-stream", ...(init.headers || {}) },
  })
}

function upstreamHeaders(): Record<string, string> {
  const init = fetchMock.mock.calls[0]?.[1] as RequestInit
  return (init.headers ?? {}) as Record<string, string>
}

describe("proxySse", () => {
  it("relays stream bytes in order without re-serializing", async () => {
    fetchMock.mockResolvedValue(sseUpstream(["data: a\n\n", "id: 1\ndata: b\n\n", "data: c\n\n"]))
    const res = await proxySse(new Request("http://localhost/api/x/stream", { method: "POST", body: "{}" }), {
      path: "/x/stream",
    })
    expect(res.status).toBe(200)
    expect(res.headers.get("content-type")).toContain("text/event-stream")
    expect(await res.text()).toBe("data: a\n\nid: 1\ndata: b\n\ndata: c\n\n")
  })

  it("preserves non-200 backend status instead of pinning to 200", async () => {
    fetchMock.mockResolvedValue(sseUpstream(["data: x\n\n"], { status: 503 }))
    const res = await proxySse(new Request("http://localhost/api/x/stream"), { path: "/x/stream" })
    expect(res.status).toBe(503)
  })

  it("forwards correlation IDs and rejects mismatched request-id echo", async () => {
    fetchMock.mockResolvedValue(
      sseUpstream(["data: x\n\n"], { headers: { "x-request-id": "d".repeat(32) } }),
    )
    const res = await proxySse(
      new Request("http://localhost/api/x/stream", {
        headers: { "x-request-id": VALID_REQ_ID, "x-operation-id": "op_9" },
      }),
      { path: "/x/stream" },
    )
    expect(upstreamHeaders()["x-request-id"]).toBe(VALID_REQ_ID)
    expect(upstreamHeaders()["x-operation-id"]).toBe("op_9")
    expect(res.status).toBe(502)
    expect((await res.json()).error.code).toBe("backend_contract_violation")
  })

  it("maps connect failure to 502 and header timeout to 504", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"))
    const res = await proxySse(new Request("http://localhost/api/x/stream"), { path: "/x/stream" })
    expect(res.status).toBe(502)
    expect((await res.json()).error.code).toBe("backend_unavailable")

    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("The operation was aborted", "AbortError")),
          )
        }),
    )
    const timedOut = await proxySse(new Request("http://localhost/api/x/stream"), {
      path: "/x/stream",
      timeoutMs: 5,
    })
    expect(timedOut.status).toBe(504)
    expect((await timedOut.json()).error.code).toBe("backend_timeout")
  })

  it("never forwards browser Authorization; uses server env token only", async () => {
    process.env.API_TOKEN = "server-token"
    fetchMock.mockResolvedValue(sseUpstream(["data: x\n\n"]))
    await proxySse(
      new Request("http://localhost/api/x/stream", {
        headers: { authorization: "Bearer browser-token" },
      }),
      { path: "/x/stream" },
    )
    expect(upstreamHeaders().Authorization ?? upstreamHeaders().authorization).toBe(
      "Bearer server-token",
    )
  })

  it("returns 502 backend_unavailable when the backend yields no stream", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 200 }))
    const res = await proxySse(new Request("http://localhost/api/x/stream"), { path: "/x/stream" })
    expect(res.status).toBe(502)
    expect((await res.json()).error.code).toBe("backend_unavailable")
  })
})
