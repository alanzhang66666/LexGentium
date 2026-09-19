import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/conversation/derive", method: "POST", label: "conversation-derive", timeoutMs: 15000})
}
