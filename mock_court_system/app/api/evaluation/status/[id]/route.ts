import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return backendFetch(`/evaluation/status/${encodeURIComponent(id)}`, {
    label: "evaluation-status",
    timeoutMs: 30000,
  })
}
