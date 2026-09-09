import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return backendFetch(`/game/${encodeURIComponent(gameId)}/evaluate/polarization`, {
    label: "game-eval-polarization",
    timeoutMs: 180000,
  })
}
