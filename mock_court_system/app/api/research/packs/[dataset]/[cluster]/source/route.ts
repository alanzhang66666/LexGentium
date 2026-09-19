import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ dataset: string; cluster: string }> },
) {
  const { dataset, cluster } = await params
  const search = request.nextUrl.searchParams.toString()
  const suffix = search ? `?${search}` : ""
  return proxyJson(request, {path: `/research/packs/${encodeURIComponent(dataset)}/${encodeURIComponent(cluster)}/source${suffix}`, label: "research-source-get"})
}
