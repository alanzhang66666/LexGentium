import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const search = request.nextUrl.searchParams.toString()
  const suffix = search ? `?${search}` : ""
  return proxyJson(request, {path: `/research/runs${suffix}`, label: "research-runs-list"})
}
