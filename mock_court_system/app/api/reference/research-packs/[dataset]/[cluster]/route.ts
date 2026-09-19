import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ dataset: string; cluster: string }> },
) {
  const { dataset, cluster } = await params
  const packVersion = new URL(request.url).searchParams.get("pack_version")
  const query = packVersion ? `?pack_version=${encodeURIComponent(packVersion)}` : ""
  return proxyJson(request, {path: `/reference/research-packs/${encodeURIComponent(dataset)}/${encodeURIComponent(cluster)}${query}`, label: "reference-research-pack"})
}
