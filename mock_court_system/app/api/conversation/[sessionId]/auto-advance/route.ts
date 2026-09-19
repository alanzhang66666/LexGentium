import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}/auto-advance`, method: "POST", label: "conversation-auto-advance", timeoutMs: 300000})
}

