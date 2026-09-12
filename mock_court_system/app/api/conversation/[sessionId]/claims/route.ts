import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}/claims`, {
    label: "conversation-claims-get",
    request,
  })
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}/claims`, {
    method: "POST",
    body: parsed.body,
    label: "conversation-claims-post",
    request,
  })
}
