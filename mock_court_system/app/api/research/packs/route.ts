import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const dataset = request.nextUrl.searchParams.get("dataset")
  const query = dataset ? `?dataset=${encodeURIComponent(dataset)}` : ""
  return proxyJson(request, {path: `/research/packs${query}`, label: "research-packs-list"})
}
