import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ dataset: string; cluster: string }> },
) {
  const { dataset, cluster } = await params
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch(`/research/packs/${encodeURIComponent(dataset)}/${encodeURIComponent(cluster)}/fields`, {
    method: "PATCH",
    body: parsed.body,
    label: "research-field-patch",
    request,
  })
}
