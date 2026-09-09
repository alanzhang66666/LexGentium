import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const limit = searchParams.get("limit") || "40"
  const split = searchParams.get("split") || "test"
  return backendFetch(`/reference/cases?limit=${encodeURIComponent(limit)}&split=${encodeURIComponent(split)}`, {
    label: "reference-cases",
  })
}
