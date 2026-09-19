import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/evaluate/explainable`, method: "POST", label: "game-eval-explainable", timeoutMs: 180000})
}
