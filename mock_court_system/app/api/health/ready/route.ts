import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, { path: "/health/ready", label: "health-ready", timeoutMs: 15000 })
}
