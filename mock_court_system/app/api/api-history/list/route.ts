import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams.toString()
  const path = `/api-history/list${params ? `?${params}` : ""}`
  return proxyJson(request, { path, label: "api-history-list", timeoutMs: 30000 })
}
