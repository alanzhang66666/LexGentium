import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams.toString()
  return backendFetch(`/api-history/list${params ? `?${params}` : ""}`, {
    label: "api-history-list",
    timeoutMs: 30000,
  })
}

