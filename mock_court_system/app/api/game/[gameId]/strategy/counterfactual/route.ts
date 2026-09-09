import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return backendFetch(`/game/${encodeURIComponent(gameId)}/strategy/counterfactual`, {
    method: "POST",
    body: await request.json(),
    label: "game-counterfactual",
    timeoutMs: 60000,
  })
}
