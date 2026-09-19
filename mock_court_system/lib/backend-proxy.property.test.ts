import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import fc from "fast-check"

import {
  identityEchoViolation,
  isValidRequestId,
  newRequestId,
  proxyJson,
  resolveRequestId,
} from "./backend-proxy"

const ENV_KEYS = ["API_TOKEN", "BACKEND_API_TOKEN", "BFF_ALLOWED_ORIGINS", "BFF_MAX_BODY_BYTES"] as const

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

describe("Property 13: BFF 保持后端契约", () => {
  it("任意 JSON body/status 原样透传", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.jsonValue(),
        // 101/204/205/304 不允许携带 body，Response 构造器会拒绝
        fc.integer({ min: 200, max: 599 }).filter(
          (s) => ![101, 204, 205, 304].includes(s),
        ),
        async (body, status) => {
          fetchMock.mockResolvedValue(
            new Response(JSON.stringify(body), {
              status,
              headers: { "content-type": "application/json" },
            }),
          )
          const res = await proxyJson(new Request("http://localhost/api/x"), {
            path: "/conversation/list",
          })
          expect(res.status).toBe(status)
          expect(await res.json()).toEqual(body)
          expect(isValidRequestId(res.headers.get("x-request-id"))).toBe(true)
        },
      ),
    )
  })

  it("任意请求 ID 输入被归一化为合法值且端到端一致", async () => {
    await fc.assert(
      fc.asyncProperty(fc.string({ maxLength: 80 }), async (raw) => {
        fetchMock.mockResolvedValue(
          new Response("{}", { headers: { "content-type": "application/json" } }),
        )
        const req = new Request("http://localhost/api/x", {
          headers: { "x-request-id": raw },
        })
        const resolved = resolveRequestId(req)
        expect(isValidRequestId(resolved)).toBe(true)
        if (isValidRequestId(raw)) expect(resolved).toBe(raw)
        await proxyJson(req, { path: "/x" })
        const upstreamHeaders = (fetchMock.mock.calls.at(-1)?.[1] as RequestInit)
          .headers as Record<string, string>
        const forwarded = upstreamHeaders["x-request-id"]
        // 端到端一致：合法输入透传，非法输入替换为一次生成的合法值
        expect(isValidRequestId(forwarded)).toBe(true)
        if (isValidRequestId(raw)) expect(forwarded).toBe(raw)
      }),
    )
  })

  it("任意 echo 不匹配都被 identityEchoViolation 检出", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 16, maxLength: 64 }),
        fc.string({ minLength: 1, maxLength: 32 }),
        (echoReq, echoOp) => {
          const reqId = newRequestId()
          const res = new Response("{}", {
            headers: { "x-request-id": echoReq, "x-operation-id": echoOp },
          })
          const violation = identityEchoViolation(res, reqId, "op-1")
          const shouldViolate = echoReq !== reqId || echoOp !== "op-1"
          expect(violation).toBe(shouldViolate)
        },
      ),
    )
  })
})
