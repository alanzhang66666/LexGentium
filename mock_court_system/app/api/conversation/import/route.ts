import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/conversation/import", method: "POST", label: "conversation-import", timeoutMs: 30000})
}

