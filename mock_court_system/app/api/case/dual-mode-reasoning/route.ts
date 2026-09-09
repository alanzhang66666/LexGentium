import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch("/case/dual-mode-reasoning", {
    method: "POST",
    body: parsed.body,
    label: "case-dual-mode",
    timeoutMs: 180000,
  })
}
