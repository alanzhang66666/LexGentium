import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch("/conversation/derive", {
    method: "POST",
    body: parsed.body,
    label: "conversation-derive",
    timeoutMs: 15000,
    request,
  })
}
