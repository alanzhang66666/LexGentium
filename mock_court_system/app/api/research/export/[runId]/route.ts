import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params
  return backendFetch(`/research/export/${encodeURIComponent(runId)}`, {
    label: "research-export",
    request,
  })
}
