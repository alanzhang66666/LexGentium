import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}`, {
    label: "conversation-get",
    timeoutMs: 30000,
  })
}

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
    label: "conversation-delete",
    timeoutMs: 30000,
  })
}

