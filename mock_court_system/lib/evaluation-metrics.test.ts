import { describe, expect, it } from "vitest"
import { evaluationMetrics, evaluationScenarios, evaluationScore } from "./evaluation-metrics"

describe("evaluation reports", () => {
  it("does not treat report metadata as scenario arrays", () => {
    expect(evaluationScenarios({ report_id: "uuid", run_id: "run", summary: { evaluated_samples: 1 }, CI: [] })).toEqual(["CI"])
  })
  it("keeps genuine zero scores in the denominator and minimum", () => {
    expect(evaluationMetrics([{ score: { score: 0 } }, { score: { score: 1 } }])).toEqual({ average: 0.5, total: 2, max: 1, min: 0 })
  })
  it("does not invent scores from reference metadata or invalid numbers", () => {
    expect(evaluationScore({ reference_version: 1, gold_labels: {} })).toBeNull()
    expect(evaluationScore(Number.NaN)).toBeNull()
  })
})
