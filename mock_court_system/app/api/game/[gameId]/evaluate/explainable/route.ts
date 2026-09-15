import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return backendFetch(`/game/${encodeURIComponent(gameId)}/evaluate/explainable`, {
    method: "POST",
    body: {},
    label: "game-eval-explainable",
    timeoutMs: 180000,
  })
}
