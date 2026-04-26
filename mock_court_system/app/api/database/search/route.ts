import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/database/search", {
    method: "POST",
    body: await request.json(),
    label: "database-search",
    timeoutMs: 60000,
  })
}

