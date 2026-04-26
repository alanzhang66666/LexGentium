import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/api-history/stats", { label: "api-history-stats", timeoutMs: 30000 })
}

