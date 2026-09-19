import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/evaluate/lexeval`, method: "POST", label: "game-eval-lexeval", timeoutMs: 180000})
}
