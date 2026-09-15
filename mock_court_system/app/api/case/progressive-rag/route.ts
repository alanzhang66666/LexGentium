import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch("/case/progressive-rag", {
    method: "POST",
    body: parsed.body,
    label: "case-progressive-rag",
    timeoutMs: 120000,
  })
}
