import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}/compliance`, label: "conversation-compliance"})
}
