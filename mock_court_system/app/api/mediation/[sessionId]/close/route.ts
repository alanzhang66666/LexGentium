import { backendFetch } from "@/lib/backend-fetch"

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/mediation/${encodeURIComponent(sessionId)}/close`, {
    method: "POST",
    body: {},
    label: "mediation-close",
    timeoutMs: 120000,
  })
}
