import { describe, expect, it } from "vitest"
import { castManifest } from "./cast-manifest"

describe("hearing cast manifest", () => {
  it("contains the seven contract actors plus the two supplied roles", () => {
    expect(castManifest.map((member) => member.actor_id)).toEqual([
      "judge", "clerk", "plaintiff_counsel", "plaintiff_party",
      "defendant_counsel", "defendant_party", "interpreter", "prosecutor", "fact_witness",
    ])
  })

  it("has a distinct seat and supplier OBJ asset for every character", () => {
    expect(castManifest.every((member) => member.status === "reference")).toBe(true)
    expect(castManifest.every((member) => member.asset_kind === "reference")).toBe(true)
    expect(new Set(castManifest.map((member) => member.seat_id)).size).toBe(9)
  })
})
