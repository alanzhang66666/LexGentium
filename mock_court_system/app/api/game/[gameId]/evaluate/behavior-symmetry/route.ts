import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return backendFetch(`/game/${encodeURIComponent(gameId)}/evaluate/behavior-symmetry`, {
    method: "POST",
    body: {},
    label: "game-eval-cadd-symmetry",
    timeoutMs: 180000,
  })
}
