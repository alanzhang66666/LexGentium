import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/database/stats", { label: "database-stats", timeoutMs: 30000 })
}

