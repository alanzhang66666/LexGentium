// Mirror of release/routes.yaml `experimental` section.
// Keep in sync with the catalog — the release gate validates the YAML;
// this module only exposes the same tags to the UI for labelling.

export const EXPERIMENTAL_LABEL = "实验功能"

const EXPERIMENTAL_PAGE_PATTERNS = ["/api-history", "/simulate"]

const EXPERIMENTAL_API_PATTERNS = [
  "/api/api-history",
  "/api/game",
  "/api/case/progressive-rag",
  "/api/case/dual-mode-reasoning",
  "/api/case/multi-judge",
  "/api/legacy",
  "/api/simulate",
]

function matchesPattern(path: string, pattern: string): boolean {
  return path === pattern || path.startsWith(`${pattern}/`)
}

export function isExperimentalPage(path: string): boolean {
  return EXPERIMENTAL_PAGE_PATTERNS.some((p) => matchesPattern(path, p))
}

export function isExperimentalApi(path: string): boolean {
  return EXPERIMENTAL_API_PATTERNS.some((p) => matchesPattern(path, p))
}
