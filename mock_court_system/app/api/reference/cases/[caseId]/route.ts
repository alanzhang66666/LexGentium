import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await params
  const split = new URL(request.url).searchParams.get("split")
  const query = split ? `?split=${encodeURIComponent(split)}` : ""
  return backendFetch(`/reference/cases/${encodeURIComponent(caseId)}${query}`, {
    label: "reference-case-full",
  })
}
