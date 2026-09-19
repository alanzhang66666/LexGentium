import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { backendAuthHeaders, backendFetch } from "./backend-fetch"

const ENV_KEYS = ["API_TOKEN", "BACKEND_API_TOKEN"] as const

let savedEnv: Record<string, string | undefined>

beforeEach(() => {
  savedEnv = {}
  for (const key of ENV_KEYS) {
    savedEnv[key] = process.env[key]
    delete process.env[key]
  }
})

afterEach(() => {
  for (const key of ENV_KEYS) {
    if (savedEnv[key] === undefined) delete process.env[key]
    else process.env[key] = savedEnv[key]
  }
  vi.unstubAllGlobals()
})

describe("backendAuthHeaders", () => {
  it("returns empty headers when no server token is configured", async () => {
    expect(await backendAuthHeaders()).toEqual({})
  })

  it("uses API_TOKEN as Bearer credentials", async () => {
    process.env.API_TOKEN = "secret-token-1"
    expect(await backendAuthHeaders()).toEqual({ Authorization: "Bearer secret-token-1" })
  })

  it("falls back to BACKEND_API_TOKEN", async () => {
    process.env.BACKEND_API_TOKEN = "fallback-token"
    expect(await backendAuthHeaders()).toEqual({ Authorization: "Bearer fallback-token" })
  })

  it("prefers API_TOKEN over BACKEND_API_TOKEN", async () => {
    process.env.API_TOKEN = "primary"
    process.env.BACKEND_API_TOKEN = "secondary"
    expect(await backendAuthHeaders()).toEqual({ Authorization: "Bearer primary" })
  })
})

describe("backendFetch auth boundary", () => {
  function stubBackend() {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    )
    vi.stubGlobal("fetch", fetchMock)
    return fetchMock
  }

  function upstreamHeaders(fetchMock: ReturnType<typeof vi.fn>): Record<string, string> {
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit
    return (init.headers ?? {}) as Record<string, string>
  }

  it("never forwards a browser-supplied Authorization header", async () => {
    const fetchMock = stubBackend()
    const request = new Request("http://localhost/api/x", {
      headers: { Authorization: "Bearer browser-token" },
    })

    await backendFetch("/conversation/list", { request })

    const headers = upstreamHeaders(fetchMock)
    expect(headers.Authorization).toBeUndefined()
  })

  it("sends only the server-side env token, not the browser token", async () => {
    process.env.API_TOKEN = "server-token"
    const fetchMock = stubBackend()
    const request = new Request("http://localhost/api/x", {
      headers: { Authorization: "Bearer browser-token" },
    })

    await backendFetch("/conversation/list", { request })

    const headers = upstreamHeaders(fetchMock)
    expect(headers.Authorization).toBe("Bearer server-token")
  })
})
