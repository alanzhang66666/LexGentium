import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, { path: "/health/live", label: "health-live", timeoutMs: 10000 })
}
