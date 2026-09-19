import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/api-history/stats", label: "api-history-stats", timeoutMs: 30000})
}

