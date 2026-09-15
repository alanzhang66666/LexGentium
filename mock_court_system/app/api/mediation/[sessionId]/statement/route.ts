import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/mediation/${encodeURIComponent(sessionId)}/statement`, {
    method: "POST",
    body: await request.json(),
    label: "mediation-statement",
    timeoutMs: 120000,
  })
}
