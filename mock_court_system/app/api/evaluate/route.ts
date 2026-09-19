import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {
    path: "/evaluate",
    method: "POST",
    label: "evaluate-start",
    timeoutMs: 60000,
  })
}

export async function GET(request: NextRequest) {
  const reportId = new URL(request.url).searchParams.get("report_id")
  const path = reportId ? `/evaluation/status/${encodeURIComponent(reportId)}` : "/evaluation/results"
  return proxyJson(request, { path, label: "evaluate-read", timeoutMs: 30000 })
}
