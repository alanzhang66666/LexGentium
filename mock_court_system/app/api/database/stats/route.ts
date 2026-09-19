import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/database/stats", label: "database-stats", timeoutMs: 30000})
}

