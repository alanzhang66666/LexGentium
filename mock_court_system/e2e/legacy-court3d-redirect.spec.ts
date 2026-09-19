import { expect, test } from "@playwright/test"

// Legacy /court3d redirect contract (Task 11.4). Verifies the three legacy
// routes resolve to /hearing-3d with preserved parameters. Intentionally
// does not open, screenshot, or evaluate /hearing-3d visuals.

const CASES = [
  { from: "/court3d", to: "/hearing-3d" },
  { from: "/court3d/replay", to: "/hearing-3d" },
  { from: "/court3d/sess-abc123", to: "/hearing-3d", param: "sessionId=sess-abc123" },
]

for (const c of CASES) {
  test(`${c.from} redirects to ${c.to}`, async ({ request }) => {
    const res = await request.get(c.from, { maxRedirects: 0 })
    if (res.status() >= 300 && res.status() < 400) {
      const location = res.headers()["location"] || ""
      expect(location).toContain(c.to)
      if (c.param) expect(location).toContain(c.param)
      return
    }
    // next dev 可用 RSC 流内 redirect：跟随后最终落点必须是目标路由
    const followed = await request.get(c.from)
    const finalUrl = followed.url()
    expect(finalUrl).toContain(c.to)
    if (c.param) expect(finalUrl).toContain(c.param)
  })
}
