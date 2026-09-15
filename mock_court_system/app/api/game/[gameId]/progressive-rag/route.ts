import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch(`/game/${encodeURIComponent(gameId)}/progressive-rag`, {
    method: "POST",
    body: parsed.body,
    label: "game-progressive-rag",
    timeoutMs: 120000,
  })
}
