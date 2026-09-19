import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/config/llm", label: "llm-config-get", timeoutMs: 30000})
}

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/config/llm", method: "POST", label: "llm-config-update", timeoutMs: 30000})
}

