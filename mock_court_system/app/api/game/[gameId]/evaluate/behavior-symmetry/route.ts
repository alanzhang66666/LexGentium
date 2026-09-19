import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/evaluate/behavior-symmetry`, method: "POST", label: "game-eval-cadd-symmetry", timeoutMs: 180000})
}
