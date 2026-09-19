import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { GET, POST } from "./route"
import { GET as reportGET } from "./reports/[reportId]/route"

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal("fetch", fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonUpstream(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function upstreamUrl(): string {
  return String(fetchMock.mock.calls[0]?.[0])
}

describe("evaluate BFF routes", () => {
  it("POST /api/evaluate proxies to /evaluate", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({ report_id: "r1", status: "running" }))
    const res = await POST(
      new Request("http://localhost/api/evaluate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scenarios: ["CD"], session_id: "s1" }),
      }) as never,
    )
    expect(res.status).toBe(200)
    expect(upstreamUrl()).toContain("/evaluate")
    expect((await res.json()).report_id).toBe("r1")
  })

  it("GET /api/evaluate?report_id maps to /evaluation/status/{id}", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({ report_id: "r9", status: "completed" }))
    const res = await GET(
      new Request("http://localhost/api/evaluate?report_id=r9") as never,
    )
    expect(res.status).toBe(200)
    expect(upstreamUrl()).toContain("/evaluation/status/r9")
  })

  it("GET /api/evaluate without report_id lists results", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({ reports: [] }))
    const res = await GET(new Request("http://localhost/api/evaluate") as never)
    expect(upstreamUrl()).toContain("/evaluation/results")
    expect((await res.json()).reports).toEqual([])
  })

  it("passes provenance and correlation through unchanged", async () => {
    const payload = {
      report_id: "r5",
      status: "completed",
      provenance: {
        provenance_id: "prov_abc",
        namespace: "research",
        rubric_version: "research-6d-1.0",
        degraded: true,
        affected_metrics: ["accuracy"],
      },
      correlation: {
        session_id: "s5",
        operation_id: "eval:r5",
        report_id: "r5",
        run_id: "run_1",
      },
    }
    fetchMock.mockResolvedValue(jsonUpstream(payload))
    const res = await GET(
      new Request("http://localhost/api/evaluate?report_id=r5") as never,
    )
    const body = await res.json()
    expect(body.provenance.namespace).toBe("research")
    expect(body.provenance.degraded).toBe(true)
    expect(body.correlation.operation_id).toBe("eval:r5")
  })

  it("GET /api/evaluate/reports/{id} maps to /evaluation/reports/{id}", async () => {
    fetchMock.mockResolvedValue(jsonUpstream({ report_id: "r7", results: {} }))
    const res = await reportGET(new Request("http://localhost/api/evaluate/reports/r7"), {
      params: Promise.resolve({ reportId: "r7" }),
    })
    expect(res.status).toBe(200)
    expect(upstreamUrl()).toContain("/evaluation/reports/r7")
  })
})
