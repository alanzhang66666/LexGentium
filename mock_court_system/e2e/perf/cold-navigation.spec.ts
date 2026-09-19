import { createHash } from "node:crypto"
import { mkdirSync, writeFileSync } from "node:fs"
import { join } from "node:path"
import { test, type Page } from "@playwright/test"

// Cold-navigation performance sampling for non-hearing entry pages.
// Evidence contract: >= 30 valid samples per entry, fixed network profile,
// and a recorded profile digest; otherwise the entry verdict is `invalid`.

const SAMPLES_REQUIRED = 30
const NETWORK_PROFILE = {
  id: "fixed-40ms-5mbps-1mbps",
  latencyMs: 40,
  downloadThroughputBps: 5 * 1024 * 1024,
  uploadThroughputBps: 1024 * 1024,
} as const

const PROFILE_DIGEST = createHash("sha256").update(JSON.stringify(NETWORK_PROFILE)).digest("hex")

// Primary action per entry page — readiness is "the thing a user would
// click first" being visible. /hearing-3d and /court3d are excluded.
const ENTRIES: { id: string; path: string; primaryAction: string }[] = [
  { id: "home", path: "/", primaryAction: "text=开庭" },
  { id: "conversation", path: "/conversation", primaryAction: "button:has-text('创建会话')" },
  { id: "full-simulation", path: "/full-simulation", primaryAction: "button:has-text('开始')" },
  { id: "mediation", path: "/mediation", primaryAction: "button:has-text('创建调解')" },
  { id: "research", path: "/research", primaryAction: "h1:has-text('研究')" },
  { id: "evaluation", path: "/evaluation", primaryAction: "button:has-text('对照')" },
  { id: "system", path: "/system", primaryAction: "button:has-text('刷新')" },
  { id: "settings", path: "/settings", primaryAction: "button" },
  { id: "login", path: "/login", primaryAction: "button[type='submit'], button:has-text('登录')" },
  { id: "register", path: "/register", primaryAction: "button[type='submit'], button:has-text('开通')" },
  { id: "database", path: "/database", primaryAction: "input, textarea" },
  { id: "api-history", path: "/api-history", primaryAction: "h1:has-text('API 历史')" },
  { id: "simulate", path: "/simulate", primaryAction: "button:has-text('发送'), button:has-text('提交')" },
]

interface Sample {
  nav_ms: number
  ready_ms: number
}

interface EntryEvidence {
  entry: string
  path: string
  samples: Sample[]
  excluded: { index: number; reason: string }[]
  p50_ms: number | null
  p95_ms: number | null
  max_ms: number | null
  verdict: "pass" | "invalid"
  invalid_reasons: string[]
}

function nearestRank(sorted: number[], q: number): number | null {
  if (sorted.length === 0) return null
  return sorted[Math.ceil(q * sorted.length) - 1]
}

async function applyNetworkProfile(page: Page) {
  const session = await page.context().newCDPSession(page)
  await session.send("Network.enable")
  await session.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: NETWORK_PROFILE.latencyMs,
    downloadThroughput: NETWORK_PROFILE.downloadThroughputBps,
    uploadThroughput: NETWORK_PROFILE.uploadThroughputBps,
  })
}

const evidence: EntryEvidence[] = []

for (const entry of ENTRIES) {
  test(`cold navigation ${entry.path}`, async ({ browser }) => {
    const record: EntryEvidence = {
      entry: entry.id,
      path: entry.path,
      samples: [],
      excluded: [],
      p50_ms: null,
      p95_ms: null,
      max_ms: null,
      verdict: "invalid",
      invalid_reasons: [],
    }
    evidence.push(record)

    for (let i = 0; i < SAMPLES_REQUIRED; i++) {
      // Fresh context = cold cache, cold cookies, no SW state.
      const context = await browser.newContext()
      try {
        const page = await context.newPage()
        await applyNetworkProfile(page)
        const t0 = Date.now()
        const response = await page.goto(entry.path, { waitUntil: "domcontentloaded" })
        const navMs = Date.now() - t0
        if (!response || !response.ok()) {
          record.excluded.push({ index: i, reason: `status ${response?.status() ?? "none"}` })
          continue
        }
        try {
          await page.locator(entry.primaryAction).first().waitFor({ state: "visible", timeout: 15000 })
        } catch {
          record.excluded.push({ index: i, reason: "primary action not visible within 15s" })
          continue
        }
        record.samples.push({ nav_ms: navMs, ready_ms: Date.now() - t0 })
      } catch (err) {
        record.excluded.push({ index: i, reason: err instanceof Error ? err.message.slice(0, 120) : "navigation failed" })
      } finally {
        await context.close()
      }
    }

    const durations = record.samples.map((s) => s.ready_ms).sort((a, b) => a - b)
    record.p50_ms = nearestRank(durations, 0.5)
    record.p95_ms = nearestRank(durations, 0.95)
    record.max_ms = durations.length ? durations[durations.length - 1] : null

    if (record.samples.length < SAMPLES_REQUIRED) {
      record.invalid_reasons.push(`insufficient_samples ${record.samples.length}/${SAMPLES_REQUIRED}`)
    }
    if (PROFILE_DIGEST !== createHash("sha256").update(JSON.stringify(NETWORK_PROFILE)).digest("hex")) {
      record.invalid_reasons.push("profile_mismatch")
    }
    if (record.invalid_reasons.length === 0) record.verdict = "pass"
  })
}

test.afterAll(async () => {
  const outDir = join(__dirname, "evidence")
  mkdirSync(outDir, { recursive: true })
  const payload = {
    schema: "perf-cold-nav-v1",
    captured_at: new Date().toISOString(),
    environment: {
      node: process.version,
      platform: process.platform,
      playwright: process.env.npm_package_version ?? null,
      base_url: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000",
    },
    network_profile: { ...NETWORK_PROFILE, digest: PROFILE_DIGEST },
    samples_required: SAMPLES_REQUIRED,
    entries: evidence,
  }
  writeFileSync(join(outDir, "perf-cold-nav.json"), JSON.stringify(payload, null, 2))
})
