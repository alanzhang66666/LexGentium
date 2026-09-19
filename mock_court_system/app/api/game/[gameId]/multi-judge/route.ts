import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {
    path: `/game/${encodeURIComponent(gameId)}/multi-judge`,
    method: "POST",
    label: "game-multi-judge",
    timeoutMs: 180000,
  })
}
