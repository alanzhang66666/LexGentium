import { backendFetch } from "@/lib/backend-fetch"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ taskId: string }> },
) {
  const { taskId } = await params
  return backendFetch(`/case/full-simulation/${encodeURIComponent(taskId)}`, {
    label: "full-simulation-status",
    timeoutMs: 30000,
  })
}

