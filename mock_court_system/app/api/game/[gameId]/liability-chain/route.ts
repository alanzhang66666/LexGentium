import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/liability-chain`, label: "game-liability-chain", timeoutMs: 180000})
}
