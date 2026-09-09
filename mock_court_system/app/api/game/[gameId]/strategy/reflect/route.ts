import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  let body: unknown = {}
  try {
    body = await request.json()
  } catch {
    body = {}
  }
  return backendFetch(`/game/${encodeURIComponent(gameId)}/strategy/reflect`, {
    method: "POST",
    body,
    label: "game-strategy-reflect",
    timeoutMs: 180000,
  })
}
