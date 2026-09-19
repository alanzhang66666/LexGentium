import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {
    path: `/game/${encodeURIComponent(gameId)}/round`,
    method: "POST",
    label: "game-round",
    timeoutMs: 300000,
  })
}
