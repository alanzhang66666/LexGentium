import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch("/research/evaluate", {
    method: "POST",
    body: parsed.body,
    label: "research-evaluate",
    request,
  })
}
