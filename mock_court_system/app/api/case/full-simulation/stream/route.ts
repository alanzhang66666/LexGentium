import { type NextRequest } from "next/server"
import { BACKEND_URL, backendAuthHeaders } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  const body = await request.json()
  const backendResponse = await fetch(`${BACKEND_URL}/case/full-simulation/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await backendAuthHeaders(request)),
    },
    body: JSON.stringify(body),
  })

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
