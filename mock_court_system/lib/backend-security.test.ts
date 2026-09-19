import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { guardStateChange, proxyJson, resolveRequestId } from "./backend-proxy"

let savedEnv: Record<string, string | undefined>
let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  savedEnv = {}
  for (const key of ["BFF_ALLOWED_ORIGINS", "API_TOKEN", "BACKEND_API_TOKEN"]) {
    savedEnv[key] = process.env[key]
    delete process.env[key]
  }
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  for (const key of Object.keys(savedEnv)) {
    if (savedEnv[key] === undefined) delete process.env[key]
    else process.env[key] = savedEnv[key]
  }
  vi.unstubAllGlobals()
})

describe("BFF security boundary", () => {
  it("rejects cross-origin POST with 403 before any backend call", async () => {
    const req = new Request("http://localhost/api/conversation/start", {
      method: "POST",
      headers: { origin: "https://evil.example.com" },
    })
    const blocked = guardStateChange(req, 1_048_576)
    expect(blocked?.status).toBe(403)
    const res = await proxyJson(req, { path: "/conversation/start", method: "POST" })
    expect(res.status).toBe(403)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("allows same-origin and allowlisted origins", () => {
    process.env.BFF_ALLOWED_ORIGINS = "https://ops.example.com"
    for (const origin of ["http://localhost", "https://ops.example.com"]) {
      const req = new Request("http://localhost/api/x", {
        method: "DELETE",
        headers: { origin },
      })
      expect(guardStateChange(req, 1_048_576)).toBeNull()
    }
  })

  it("rejects oversized declared body with 413", async () => {
    const req = new Request("http://localhost/api/x", {
      method: "POST",
      headers: { "content-length": "2097153" },
    })
    expect(guardStateChange(req, 1_048_576)?.status).toBe(413)
  })

  it("does not forward browser Authorization upstream", async () => {
    process.env.BACKEND_API_TOKEN = "server-token"
    fetchMock.mockResolvedValue(
      new Response("{}", { headers: { "content-type": "application/json" } }),
    )
    await proxyJson(
      new Request("http://localhost/api/x", {
        headers: { authorization: "Bearer browser-token" },
      }),
      { path: "/x" },
    )
    const headers = (fetchMock.mock.calls[0]?.[1] as RequestInit)
      .headers as Record<string, string>
    const auth = Object.entries(headers).find(
      ([k]) => k.toLowerCase() === "authorization",
    )?.[1]
    expect(auth).toBe("Bearer server-token")
  })

  it("rejects absolute/protocol-relative backend target paths", async () => {
    for (const path of ["http://evil.com/x", "//evil.com/x", "x-no-slash"]) {
      const res = await proxyJson(new Request("http://localhost/api/x"), { path })
      // fail-closed：非 2xx 且 backend 永不被调用
      expect(res.status).toBeGreaterThanOrEqual(400)
      expect(res.status).toBeLessThan(600)
      expect(fetchMock).not.toHaveBeenCalled()
      fetchMock.mockClear()
    }
  })

  it("preserves valid request id and generates for invalid", () => {
    const valid = new Request("http://localhost/api/x", {
      headers: { "x-request-id": "req-0123456789abcdef" },
    })
    expect(resolveRequestId(valid)).toBe("req-0123456789abcdef")
    const invalid = new Request("http://localhost/api/x", {
      headers: { "x-request-id": "bad id!" },
    })
    expect(resolveRequestId(invalid)).not.toBe("bad id!")
  })
})
