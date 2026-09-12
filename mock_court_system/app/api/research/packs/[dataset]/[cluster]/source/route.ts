import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ dataset: string; cluster: string }> },
) {
  const { dataset, cluster } = await params
  const search = request.nextUrl.searchParams.toString()
  const suffix = search ? `?${search}` : ""
  return backendFetch(
    `/research/packs/${encodeURIComponent(dataset)}/${encodeURIComponent(cluster)}/source${suffix}`,
    { label: "research-source-get", request },
  )
}
