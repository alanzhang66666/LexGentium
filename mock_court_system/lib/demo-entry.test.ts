import { describe, expect, it } from "vitest"

import { resolveDemoOpeningPath } from "./demo-entry"
import type { ConversationSummary } from "./conversation-types"


function session(overrides: Partial<ConversationSummary>): ConversationSummary {
  return {
    session_id: "fallback",
    scenario: "CI",
    case_id: "enf-us-yingfan-amazon-001",
    created_at: "2026-09-20T00:00:00Z",
    updated_at: "2026-09-20T00:00:00Z",
    message_count: 8,
    ...overrides,
  }
}

describe("resolveDemoOpeningPath", () => {
  it("opens the newest populated Yingfan CI session at the opening", () => {
    const path = resolveDemoOpeningPath([
      session({ session_id: "older", updated_at: "2026-09-20T01:00:00Z" }),
      session({ session_id: "newer", updated_at: "2026-09-20T02:00:00Z" }),
      session({ session_id: "empty", updated_at: "2026-09-20T03:00:00Z", message_count: 0 }),
      session({ session_id: "other-case", case_id: "another-case" }),
    ])

    expect(path).toBe("/conversation/newer?view=opening")
  })

  it("falls back to the hearing workbench when no preset session exists", () => {
    expect(resolveDemoOpeningPath([])).toBe("/conversation")
  })
})
