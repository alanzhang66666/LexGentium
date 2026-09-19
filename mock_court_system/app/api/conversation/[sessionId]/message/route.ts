import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}/message`, method: "POST", label: "conversation-message", timeoutMs: 120000})
}

