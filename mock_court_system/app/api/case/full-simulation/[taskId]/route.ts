import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params
  return proxyJson(request, {path: `/case/full-simulation/${encodeURIComponent(taskId)}`, label: "full-simulation-status", timeoutMs: 30000})
}

