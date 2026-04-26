import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams.toString()
  return backendFetch(`/conversation/list${params ? `?${params}` : ""}`, {
    label: "conversation-list",
    timeoutMs: 30000,
  })
}

