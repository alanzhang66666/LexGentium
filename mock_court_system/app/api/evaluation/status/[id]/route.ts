import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxyJson(request, {path: `/evaluation/status/${encodeURIComponent(id)}`, label: "evaluation-status", timeoutMs: 30000})
}
