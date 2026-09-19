import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const limit = searchParams.get("limit") || "40"
  const split = searchParams.get("split") || "test"
  return proxyJson(request, {path: `/reference/cases?limit=${encodeURIComponent(limit)}&split=${encodeURIComponent(split)}`, label: "reference-cases"})
}
