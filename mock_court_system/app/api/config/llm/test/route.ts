import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/config/llm/test", method: "POST", label: "llm-config-test", timeoutMs: 8000})
}

