import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/conversation/start", method: "POST", label: "conversation-start", timeoutMs: 15000})
}

