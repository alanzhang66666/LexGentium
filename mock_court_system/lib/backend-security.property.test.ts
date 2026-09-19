import { afterEach, beforeEach, describe, expect, it } from "vitest"
import fc from "fast-check"

import { guardStateChange } from "./backend-proxy"

const ENV_KEYS = ["BFF_ALLOWED_ORIGINS"] as const
const STATE_CHANGING = ["POST", "PUT", "PATCH", "DELETE"]
const SAFE = ["GET", "HEAD", "OPTIONS"]

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
})

describe("Property 30: Origin allowlist fail-closed", () => {
  it("state-changing + 非白名单 Origin → 403；backend 永不被调用", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STATE_CHANGING),
        fc.webUrl(),
        (method, url) => {
          const origin = new URL(url).origin
          fc.pre(origin !== "http://localhost") // 请求 URL 的 origin 默认放行
          const req = new Request("http://localhost/api/x", {
            method,
            headers: { origin },
          })
          const res = guardStateChange(req, 1_048_576)
          expect(res).not.toBeNull()
          expect(res!.status).toBe(403)
        },
      ),
    )
  })

  it("safe methods 无 Origin 限制", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...SAFE),
        fc.webUrl(),
        (method, url) => {
          const req = new Request("http://localhost/api/x", {
            method,
            headers: { origin: new URL(url).origin },
          })
          expect(guardStateChange(req, 1_048_576)).toBeNull()
        },
      ),
    )
  })

  it("白名单 Origin（自身或配置）放行 state-changing 请求", () => {
    process.env.BFF_ALLOWED_ORIGINS = "https://allowed.example.com"
    fc.assert(
      fc.property(
        fc.constantFrom(...STATE_CHANGING),
        fc.constantFrom("http://localhost", "https://allowed.example.com"),
        (method, origin) => {
          const req = new Request("http://localhost/api/x", {
            method,
            headers: { origin },
          })
          expect(guardStateChange(req, 1_048_576)).toBeNull()
        },
      ),
    )
  })

  it("任意超限 Content-Length → 413", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...STATE_CHANGING),
        fc.integer({ min: 1025, max: 10_000_000 }),
        (method, size) => {
          const req = new Request("http://localhost/api/x", {
            method,
            headers: { "content-length": String(size) },
          })
          const res = guardStateChange(req, 1024)
          expect(res).not.toBeNull()
          expect(res!.status).toBe(413)
        },
      ),
    )
  })
})
