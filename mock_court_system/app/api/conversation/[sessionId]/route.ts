import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}`, label: "conversation-get", timeoutMs: 30000})
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/conversation/${encodeURIComponent(sessionId)}`, method: "DELETE", label: "conversation-delete", timeoutMs: 30000})
}

