import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/mediation/${encodeURIComponent(sessionId)}/options`, {
    method: "POST",
    body: {},
    label: "mediation-options",
    timeoutMs: 120000,
  })
}
