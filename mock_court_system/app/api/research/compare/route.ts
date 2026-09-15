import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const search = request.nextUrl.searchParams.toString()
  const suffix = search ? `?${search}` : ""
  return backendFetch(`/research/compare${suffix}`, {
    label: "research-compare",
    request,
  })
}
