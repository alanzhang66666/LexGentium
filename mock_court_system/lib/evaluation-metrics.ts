export function evaluationScenarios(report: Record<string, unknown>): string[] {
  return ["CD", "DD", "CI"].filter((scenario) => Array.isArray(report[scenario]))
}

export function evaluationScore(score: unknown): number | null {
  const value = typeof score === "number"
    ? score
    : score && typeof score === "object" && "score" in score
      ? score.score
      : null
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

export function evaluationMetrics(rows: unknown) {
  const scores = (Array.isArray(rows) ? rows : [])
    .map((row) => evaluationScore(row?.score))
    .filter((score): score is number => score !== null)
  return {
    average: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0,
    total: scores.length,
    max: scores.length ? Math.max(...scores) : 0,
    min: scores.length ? Math.min(...scores) : 0,
  }
}
