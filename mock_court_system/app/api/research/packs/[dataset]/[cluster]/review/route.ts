import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ dataset: string; cluster: string }> },
) {
  const { dataset, cluster } = await params
  return proxyJson(request, {path: `/research/packs/${encodeURIComponent(dataset)}/${encodeURIComponent(cluster)}/review`, method: "PATCH", label: "research-review-patch"})
}
