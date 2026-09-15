import { describe, expect, it } from "vitest"
import { castManifest } from "./cast-manifest"

describe("hearing cast manifest", () => {
  it("contains exactly the seven contract actor ids", () => {
    expect(castManifest.map((member) => member.actor_id)).toEqual([
      "judge", "clerk", "plaintiff_counsel", "plaintiff_party",
      "defendant_counsel", "defendant_party", "interpreter",
    ])
  })

  it("uses explicit procedural placeholders until formal assets arrive", () => {
    expect(castManifest.every((member) => member.status === "placeholder")).toBe(true)
    expect(castManifest.every((member) => member.asset_kind === "procedural")).toBe(true)
    expect(new Set(castManifest.map((member) => member.seat_id)).size).toBe(7)
  })
})
