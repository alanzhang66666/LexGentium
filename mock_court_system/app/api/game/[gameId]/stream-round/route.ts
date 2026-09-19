import { proxySse } from "@/lib/backend-stream"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxySse(request, {
    path: `/game/${encodeURIComponent(gameId)}/stream-round`,
    method: "POST",
    label: "game-stream-round",
  })
}
