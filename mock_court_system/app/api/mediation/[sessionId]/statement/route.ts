import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/mediation/${encodeURIComponent(sessionId)}/statement`, method: "POST", label: "mediation-statement", timeoutMs: 120000})
}
