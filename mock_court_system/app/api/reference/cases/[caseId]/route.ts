import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await params
  const split = new URL(request.url).searchParams.get("split")
  const query = split ? `?split=${encodeURIComponent(split)}` : ""
  return proxyJson(request, {path: `/reference/cases/${encodeURIComponent(caseId)}${query}`, label: "reference-case-full"})
}
