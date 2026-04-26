import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/conversation/${encodeURIComponent(sessionId)}/auto-advance`, {
    method: "POST",
    body: await request.json(),
    label: "conversation-auto-advance",
    timeoutMs: 300000,
    timeoutMessage: "自动推进超时，多轮 LLM 调用耗时较长，请减少推进轮数后重试。",
  })
}

