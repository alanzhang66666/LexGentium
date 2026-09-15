import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return backendFetch(`/mediation/${encodeURIComponent(sessionId)}/status`, {
    label: "mediation-status",
  })
}
