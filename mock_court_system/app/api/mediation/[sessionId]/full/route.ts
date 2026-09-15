import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/mediation/${encodeURIComponent(sessionId)}/full`, {
    method: "POST",
    body: await request.json(),
    label: "mediation-full",
    timeoutMs: 300000,
    timeoutMessage: "完整调解超时。可改用分阶段按钮。",
  })
}
