import { type NextRequest } from "next/server"
import { BACKEND_URL } from "@/lib/backend-fetch"

// SSE 透传：不能走 backendFetch（它会缓冲 JSON），必须把字节流原样转发
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  const body = await request.json()

  const backendResponse = await fetch(
    `${BACKEND_URL}/conversation/${encodeURIComponent(sessionId)}/message/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  )

  if (!backendResponse.ok || !backendResponse.body) {
    const detail = await backendResponse.text().catch(() => "")
    return Response.json(
      { error: `后端返回 ${backendResponse.status}`, detail: detail.slice(0, 300) },
      { status: backendResponse.status },
    )
  }

  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  })
}
