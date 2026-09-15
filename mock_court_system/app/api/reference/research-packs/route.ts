import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const dataset = searchParams.get("dataset")
  const suffix = dataset ? `?dataset=${encodeURIComponent(dataset)}` : ""
  return backendFetch(`/reference/research-packs${suffix}`, {
    label: "reference-research-packs",
  })
}
