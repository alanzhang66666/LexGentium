import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ reportId: string }> },
) {
  const { reportId } = await params
  return backendFetch(`/evaluation/reports/${encodeURIComponent(reportId)}`, {
    label: "evaluate-report",
    timeoutMs: 30000,
  })
}

