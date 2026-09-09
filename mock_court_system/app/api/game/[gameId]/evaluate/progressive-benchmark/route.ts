import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return backendFetch(`/game/${encodeURIComponent(gameId)}/evaluate/progressive-benchmark`, {
    method: "POST",
    body: {},
    label: "game-eval-progressive-benchmark",
    timeoutMs: 180000,
  })
}
