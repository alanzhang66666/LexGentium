import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return backendFetch(`/game/${encodeURIComponent(gameId)}/evaluate/j1eval`, {
    method: "POST",
    body: {},
    label: "game-eval-j1eval",
    timeoutMs: 180000,
  })
}
