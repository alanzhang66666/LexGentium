import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const dataset = searchParams.get("dataset")
  const suffix = dataset ? `?dataset=${encodeURIComponent(dataset)}` : ""
  return proxyJson(request, {path: `/reference/research-packs${suffix}`, label: "reference-research-packs"})
}
