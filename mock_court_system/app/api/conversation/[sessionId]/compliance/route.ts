import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}/compliance`, {
    label: "conversation-compliance",
  })
}
