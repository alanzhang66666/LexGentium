import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const dataset = request.nextUrl.searchParams.get("dataset")
  const query = dataset ? `?dataset=${encodeURIComponent(dataset)}` : ""
  return backendFetch(`/research/packs${query}`, {
    label: "research-packs-list",
    request,
  })
}
