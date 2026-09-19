import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  return proxyJson(request, {path: `/game/${encodeURIComponent(gameId)}/equilibrium/convergence`, label: "game-equilibrium-convergence"})
}
