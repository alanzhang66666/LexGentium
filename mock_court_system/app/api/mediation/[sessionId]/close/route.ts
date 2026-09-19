import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/mediation/${encodeURIComponent(sessionId)}/close`, method: "POST", label: "mediation-close", timeoutMs: 120000})
}
