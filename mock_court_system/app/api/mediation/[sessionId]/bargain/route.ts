import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  let body: unknown = {}
  try {
    body = await request.json()
  } catch {
    body = {}
  }
  return backendFetch(`/mediation/${encodeURIComponent(sessionId)}/bargain`, {
    method: "POST",
    body,
    label: "mediation-bargain",
    timeoutMs: 120000,
  })
}
