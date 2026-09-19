import { proxyJson } from "@/lib/backend-proxy"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params
  return proxyJson(request, {path: `/mediation/${encodeURIComponent(sessionId)}/preliminary`, method: "POST", label: "mediation-preliminary", timeoutMs: 120000})
}
