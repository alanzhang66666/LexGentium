import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params
  return proxyJson(request, {path: `/research/runs/${encodeURIComponent(runId)}`, label: "research-run-get"})
}
