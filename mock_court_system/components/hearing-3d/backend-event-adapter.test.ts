import { describe, expect, it } from "vitest"
import { actorForRole, conversationToHearingEvents } from "./backend-event-adapter"

describe("conversation backend event adapter", () => {
  it("maps conversation history into ordered backend_run events", () => {
    const events = conversationToHearingEvents({
      session_id: "s1", scenario: "CD", case_id: "case-1",
      created_at: "2026-01-01T00:00:00Z", dialog_history: [
        { turn: 0, role: "Judge", message: "请说明争点" },
        { turn: 1, role: "Client", message: "借款未还" },
      ], is_finished: true,
    })
    expect(events[0].type).toBe("session_started")
    expect(events[0].source_type).toBe("backend_run")
    expect(events.map((event) => event.seq)).toEqual([1, 2, 3, 4, 5])
    expect(events[2].payload.actor_id).toBe("judge")
    expect(events[3].payload.actor_id).toBe("plaintiff_counsel")
    expect(events.at(-1)?.type).toBe("session_finished")
  })

  it("preserves reasoning metadata on live utterance events", () => {
    const event = conversationToHearingEvents({
      session_id: "s3", scenario: "CI", case_id: "case-3",
      reasoning_meta: { judgment_status: "degraded", case_warnings: ["missing facts"] },
    })[0]
    expect(event.provenance?.reasoning_meta).toEqual({ judgment_status: "degraded", case_warnings: ["missing facts"] })
  })

  it("does not claim a finished conversation is a legal judgment", () => {
    const [finished] = conversationToHearingEvents({
      session_id: "s2", scenario: "CI", case_id: "case-2", is_finished: true,
    }).slice(-1)
    expect(finished.payload.note).toContain("不自动等同于法律裁决")
  })

  it("maps current international-arbitration role aliases to the cast", () => {
    const aliases = [
      ["Presiding Arbitrator", "judge"],
      ["Co-Arbitrator", "associate_judge"],
      ["Second Co-Arbitrator", "people_juror"],
      ["Tribunal Secretary", "clerk"],
      ["Claimant Co-Counsel", "prosecutor"],
      ["申请人代表", "china_company_rep"],
      ["被申请人代表", "defendant_party"],
      ["Expert Witness", "technical_expert_witness"],
      ["Fact Witness", "fact_witness"],
      ["Venue Security", "judicial_police"],
    ] as const

    for (const [role, actorId] of aliases) expect(actorForRole(role)).toBe(actorId)
  })
})
