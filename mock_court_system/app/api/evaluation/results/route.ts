import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/evaluation/results", {
    label: "evaluation-results",
    timeoutMs: 30000,
  })
}
