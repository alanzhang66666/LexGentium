import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}/claims`, label: "conversation-claims-get"})
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}/claims`, method: "POST", label: "conversation-claims-post"})
}
