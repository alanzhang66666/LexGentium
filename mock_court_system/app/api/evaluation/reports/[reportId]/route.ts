import { proxyJson } from "@/lib/backend-proxy"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ reportId: string }> },
) {
  const { reportId } = await params
  return proxyJson(request, {path: `/evaluation/reports/${encodeURIComponent(reportId)}`, label: "evaluation-report", timeoutMs: 30000})
}
