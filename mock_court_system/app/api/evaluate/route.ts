import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/evaluate", {
    method: "POST",
    body: await request.json(),
    label: "evaluate-start",
    timeoutMs: 60000,
  })
}

export async function GET(request: NextRequest) {
  const reportId = request.nextUrl.searchParams.get("report_id")
  const path = reportId ? `/evaluation/status/${encodeURIComponent(reportId)}` : "/evaluation/results"
  return backendFetch(path, { label: "evaluate-read", timeoutMs: 30000 })
}

