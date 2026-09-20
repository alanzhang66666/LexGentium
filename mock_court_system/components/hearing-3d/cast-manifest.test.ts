import { describe, expect, it } from "vitest"
import { CHARACTER_ASSETS } from "./asset-adapter"
import { castManifest } from "./cast-manifest"

describe("hearing cast manifest", () => {
  it("contains all thirteen mapped arbitration roles", () => {
    expect(castManifest.map((member) => member.actor_id)).toEqual([
      "judge", "associate_judge", "people_juror", "clerk", "plaintiff_counsel", "prosecutor",
      "china_company_rep", "defendant_counsel", "defendant_party", "interpreter",
      "technical_expert_witness", "fact_witness", "judicial_police",
    ])
  })

  it("has a distinct seat and supplier OBJ asset for every character", () => {
    expect(castManifest.every((member) => member.status === "reference")).toBe(true)
    expect(castManifest.every((member) => member.asset_kind === "reference")).toBe(true)
    expect(new Set(castManifest.map((member) => member.seat_id)).size).toBe(13)
  })

  it("keeps each arbitration profile bound to its own name and OBJ/PBR asset", () => {
    const expected = [
      ["judge", "首席仲裁员", "Presiding Arbitrator", "周屹"],
      ["associate_judge", "仲裁员", "Co-Arbitrator", "陈启澜"],
      ["people_juror", "仲裁员", "Co-Arbitrator", "何敬"],
      ["clerk", "仲裁庭秘书", "Tribunal Secretary", "林澄"],
      ["plaintiff_counsel", "申请人首席代理律师", "Lead Counsel for Claimant", "顾清衡"],
      ["prosecutor", "申请人共同代理律师", "Co-Counsel for Claimant", "谢衡宁"],
      ["china_company_rep", "申请人代表", "Claimant Representative", "陆玮宁"],
      ["defendant_counsel", "被申请人代理律师", "Counsel for Respondent", "沈嘉宁"],
      ["defendant_party", "被申请人代表", "Respondent Representative", "Marco Rossi"],
      ["interpreter", "听证口译员", "Hearing Interpreter", "唐闻"],
      ["technical_expert_witness", "专家证人", "Expert Witness", "Dr. Leila Haddad"],
      ["fact_witness", "事实证人", "Fact Witness", "Adrian Tan"],
      ["judicial_police", "会务安保", "Venue Security", "赵峥"],
    ] as const

    for (const [actorId, label, english, name] of expected) {
      const member = castManifest.find((candidate) => candidate.actor_id === actorId)
      const asset = CHARACTER_ASSETS[actorId]
      expect(member).toMatchObject({ actor_id: actorId, label, english, name })
      expect(asset).toMatchObject({ actor_id: actorId, mode: "obj" })
      expect(asset.model_url).toMatch(/^\/hearing-3d\/models\//)
      expect(asset.texture_urls).toEqual({
        base_color: expect.stringMatching(/^\/hearing-3d\/models\//),
        metallic: expect.stringMatching(/^\/hearing-3d\/models\//),
        roughness: expect.stringMatching(/^\/hearing-3d\/models\//),
        normal: expect.stringMatching(/^\/hearing-3d\/models\//),
      })
    }

    expect(CHARACTER_ASSETS).not.toHaveProperty("foreign-defendant")
    expect(new Set(Object.values(CHARACTER_ASSETS).map((asset) => asset.model_url)).size).toBe(13)
  })
})
