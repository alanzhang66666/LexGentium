import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/evaluate/progressive-benchmark`, method: "POST", label: "game-eval-progressive-benchmark", timeoutMs: 180000})
}
