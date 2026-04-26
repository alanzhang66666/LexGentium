import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}/message`, {
    method: "POST",
    body: await request.json(),
    label: "conversation-message",
    timeoutMs: 120000,
  })
}

