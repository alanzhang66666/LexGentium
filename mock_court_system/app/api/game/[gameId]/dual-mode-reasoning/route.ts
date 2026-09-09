import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ gameId: string }> },
) {
  const { gameId } = await params
  let body: unknown
  try {
    const parsed = await request.json()
    if (parsed && typeof parsed === "object" && Object.keys(parsed as object).length > 0) {
      body = parsed
    }
  } catch {
    body = undefined
  }
  return backendFetch(`/game/${encodeURIComponent(gameId)}/dual-mode-reasoning`, {
    method: "POST",
    body,
    label: "game-dual-mode",
    timeoutMs: 180000,
  })
}
