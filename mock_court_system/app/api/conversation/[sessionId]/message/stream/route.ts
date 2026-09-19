import { proxySse } from "@/lib/backend-stream"

// SSE 透传：opaque 字节转发，保持后端 status/event 顺序
export async function POST(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxySse(request, {
    path: `/conversation/${encodeURIComponent(sessionId)}/message/stream`,
    method: "POST",
    label: "conversation-message-stream",
  })
}
