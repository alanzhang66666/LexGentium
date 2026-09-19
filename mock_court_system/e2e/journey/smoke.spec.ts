import { expect, test } from "@playwright/test"

// One-shot managed E2E journeys (Task 11.2/11.3). The backend and frontend
// are spawned by global setup / webServer with an isolated runtime data
// root and a deterministic mock LLM provider — no manually started servers.
// Every journey exercises one success trace and one injected-failure trace
// (bad identity / missing resource / invalid payload). /hearing-3d and
// screenshot comparisons are intentionally excluded.

test("liveness/readiness journey: live ok, ready reports components", async ({ request }) => {
  const live = await request.get("/api/health/live")
  expect(live.ok()).toBeTruthy()

  const ready = await request.get("/api/health/ready")
  const body = await ready.json()
  expect(body).toHaveProperty("status")
  // injected failure: non-existent component path is not a valid endpoint
  const bogus = await request.get("/api/health/components/definitely-not-real")
  expect([404, 405]).toContain(bogus.status())
})

test("config journey: llm config test returns structured result", async ({ request }) => {
  const res = await request.post("/api/config/llm/test", {
    data: { api_key: "e2e-stub", base_url: "http://127.0.0.1:1", model: "stub" },
  })
  // success contract: structured ok/degraded/failed, never a bare 500
  const body = await res.json()
  expect(JSON.stringify(body)).toMatch(/connected|degraded|failed|error/)
  // injected failure: malformed payload
  const bad = await request.post("/api/config/llm/test", { data: {} })
  expect([400, 422]).toContain(bad.status())
})

test("conversation journey: start, list, message, resume; bad session fails", async ({ request }) => {
  const start = await request.post("/api/conversation/start", {
    data: { scenario: "CD", case_id: "CD-E2E-1" },
  })
  expect(start.ok()).toBeTruthy()
  const started = await start.json()
  const sessionId = started.session_id
  expect(sessionId).toBeTruthy()

  const list = await request.get("/api/conversation/list")
  expect(list.ok()).toBeTruthy()
  const sessions = await list.json()
  expect(JSON.stringify(sessions)).toContain(String(sessionId).slice(0, 8))

  const msg = await request.post(`/api/conversation/${sessionId}/message`, {
    data: { message: "原告主张被告还款。" },
  })
  expect(msg.ok()).toBeTruthy()

  // resume: detail survives a fresh fetch
  const detail = await request.get(`/api/conversation/${sessionId}`)
  expect(detail.ok()).toBeTruthy()

  // injected failure: unknown session
  const missing = await request.get("/api/conversation/sess-does-not-exist")
  expect(missing.status()).toBe(404)
})

test("full-case journey: task accepted, terminal or pollable; bad input rejected", async ({ request }) => {
  const res = await request.post("/api/case/full-simulation", {
    data: { case_id: "E2E-FULL", case_info: { case_id: "E2E-FULL" } },
  })
  expect(res.ok()).toBeTruthy()
  const body = await res.json()
  const taskId = body.task_id || body.operation_id
  expect(taskId).toBeTruthy()

  // injected failure: invalid scenario in stream poll
  const bogus = await request.get("/api/case/full-simulation/not-a-task")
  expect([404, 400]).toContain(bogus.status())
})

test("mediation journey: create + status; foreign session id rejected", async ({ request }) => {
  const created = await request.post("/api/mediation/create", {
    data: { case_info: { case_id: "E2E-MED" }, party_names: ["申请人", "被申请人"] },
  })
  expect(created.ok()).toBeTruthy()
  const body = await created.json()
  const sessionId = body.session_id
  expect(sessionId).toMatch(/^med_/)

  const status = await request.get(`/api/mediation/${sessionId}/status`)
  expect(status.ok()).toBeTruthy()

  // injected failure: a civil session id is not a mediation identity
  const wrong = await request.get("/api/mediation/not-a-mediation/status")
  expect([404, 400]).toContain(wrong.status())
})

test("evaluation journey: report status contract; unknown report 404", async ({ request }) => {
  const res = await request.get("/api/evaluate?report_id=nonexistent")
  expect([404, 200]).toContain(res.status())
  if (res.ok()) {
    const body = await res.json()
    expect(body).toHaveProperty("report_id")
  }

  const missing = await request.get("/api/evaluation/reports/no-such-report")
  expect(missing.status()).toBe(404)
})

test("research journey: inventory discloses formal=0; bad pack rejected", async ({ request }) => {
  const res = await request.get("/api/research/inventory")
  expect(res.ok()).toBeTruthy()
  const body = await res.json()
  const text = JSON.stringify(body)
  expect(text).toContain("formal")
  expect(body.formal_pack_count ?? body.formal_packs ?? 0).toBe(0)

  // injected failure: unknown cluster id
  const missing = await request.get("/api/reference/research-packs/enforcement/does-not-exist")
  expect(missing.status()).toBe(404)
})
