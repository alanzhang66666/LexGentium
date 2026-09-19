import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { proxyJson } from "./backend-proxy"

const ENV_KEYS = ["API_TOKEN", "BACKEND_API_TOKEN", "BFF_ALLOWED_ORIGINS", "BFF_MAX_BODY_BYTES"] as const
const VALID_REQ_ID = "a".repeat(32)

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

function jsonUpstream(body: unknown, init: { status?: number; headers?: Record<string, string> } = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json", ...(init.headers || {}) },
  })
}

function upstreamInit(): RequestInit {
  return fetchMock.mock.calls[0]?.[1] as RequestInit
}

function upstreamHeaders(): Record<string, string> {
  return (upstreamInit().headers ?? {}) as Record<string, string>
}

describe("proxyJson", () => {
  it("preserves backend status, media type and body", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({ session_id: "s1" }, { status: 201 }))
    const res = await proxyJson(new Request("http://localhost/api/x"), {
      path: "/conversation/list",
    })
    expect(res.status).toBe(201)
    expect(res.headers.get("content-type")).toContain("application/json")
    expect(await res.json()).toEqual({ session_id: "s1" })
  })

  it("preserves a valid incoming X-Request-Id end-to-end", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({}))
    const res = await proxyJson(
      new Request("http://localhost/api/x", { headers: { "x-request-id": VALID_REQ_ID } }),
      { path: "/x" },
    )
    expect(upstreamHeaders()["x-request-id"]).toBe(VALID_REQ_ID)
    expect(res.headers.get("x-request-id")).toBe(VALID_REQ_ID)
  })

  it("generates exactly one ID when the incoming ID is missing or invalid", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({}))
    const res = await proxyJson(
      new Request("http://localhost/api/x", { headers: { "x-request-id": "bad id!" } }),
      { path: "/x" },
    )
    const forwarded = upstreamHeaders()["x-request-id"]
    expect(forwarded).toMatch(/^[A-Za-z0-9._-]{16,64}$/)
    expect(res.headers.get("x-request-id")).toBe(forwarded)
  })

  it("forwards X-Operation-Id and rejects mismatched echo", async () => {
    fetchMock.mockResolvedValue(
      jsonUpstream({}, { headers: { "x-operation-id": "op_other" } }),
    )
    const res = await proxyJson(
      new Request("http://localhost/api/x", { headers: { "x-operation-id": "op_1" } }),
      { path: "/x" },
    )
    expect(upstreamHeaders()["x-operation-id"]).toBe("op_1")
    expect(res.status).toBe(502)
    expect((await res.json()).error.code).toBe("backend_contract_violation")
  })

  it("rejects a mismatched backend X-Request-Id echo", async () => {
    fetchMock.mockResolvedValue(
      jsonUpstream({}, { headers: { "x-request-id": "b".repeat(32) } }),
    )
    const res = await proxyJson(
      new Request("http://localhost/api/x", { headers: { "x-request-id": VALID_REQ_ID } }),
      { path: "/x" },
    )
    expect(res.status).toBe(502)
    expect((await res.json()).error.code).toBe("backend_contract_violation")
  })

  it("maps connect failure to 502 backend_unavailable", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"))
    const res = await proxyJson(new Request("http://localhost/api/x"), { path: "/x" })
    expect(res.status).toBe(502)
    const body = await res.json()
    expect(body.error.code).toBe("backend_unavailable")
    expect(body.error.retriable).toBe(true)
    expect(JSON.stringify(body)).not.toContain("localhost:8000")
  })

  it("maps header timeout to 504 backend_timeout", async () => {
    fetchMock.mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("The operation was aborted", "AbortError")),
          )
        }),
    )
    const res = await proxyJson(new Request("http://localhost/api/x"), {
      path: "/x",
      timeoutMs: 5,
    })
    expect(res.status).toBe(504)
    expect((await res.json()).error.code).toBe("backend_timeout")
  })

  it("rejects a disallowed Origin before invoking the backend", async () => {
    const res = await proxyJson(
      new Request("http://localhost/api/x", {
        method: "POST",
        headers: { origin: "https://evil.example", "content-type": "application/json" },
        body: "{}",
      }),
      { path: "/x" },
    )
    expect(res.status).toBe(403)
    expect((await res.json()).error.code).toBe("origin_forbidden")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("allows same-origin and configured Origin values", async () => {
    process.env.BFF_ALLOWED_ORIGINS = "https://ops.example"
    fetchMock.mockResolvedValue(jsonUpstream({}))
    const res = await proxyJson(
      new Request("http://localhost/api/x", {
        method: "POST",
        headers: { origin: "https://ops.example", "content-type": "application/json" },
        body: "{}",
      }),
      { path: "/x" },
    )
    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it("rejects bodies above the byte limit without calling the backend", async () => {
    const res = await proxyJson(
      new Request("http://localhost/api/x", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ payload: "x".repeat(64) }),
      }),
      { path: "/x", maxBodyBytes: 16 },
    )
    expect(res.status).toBe(413)
    expect((await res.json()).error.code).toBe("request_too_large")
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("never forwards browser Authorization; uses server env token only", async () => {
    process.env.API_TOKEN = "server-token"
    fetchMock.mockResolvedValue(jsonUpstream({}))
    await proxyJson(
      new Request("http://localhost/api/x", {
        headers: { authorization: "Bearer browser-token" },
      }),
      { path: "/x" },
    )
    expect(upstreamHeaders().Authorization ?? upstreamHeaders().authorization).toBe(
      "Bearer server-token",
    )
  })

  it("detects declared JSON identity mismatches as contract violations", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({ report_id: "r_other" }))
    const res = await proxyJson(new Request("http://localhost/api/x"), {
      path: "/x",
      expectJsonIds: { report_id: "r_1" },
    })
    expect(res.status).toBe(502)
    expect((await res.json()).error.code).toBe("backend_contract_violation")
  })
})
