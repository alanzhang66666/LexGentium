import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/evaluation/results", label: "evaluation-results", timeoutMs: 30000})
}
