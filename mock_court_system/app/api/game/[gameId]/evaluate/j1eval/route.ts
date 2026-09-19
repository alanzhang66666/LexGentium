import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/evaluate/j1eval`, method: "POST", label: "game-eval-j1eval", timeoutMs: 180000})
}
