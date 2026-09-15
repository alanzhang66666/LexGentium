import { type NextRequest } from "next/server"
import { backendFetch, parseJsonBody } from "@/lib/backend-fetch"

/** 1:1 alias for FastAPI POST /. UI keeps POST /api/simulate. */
export async function POST(request: NextRequest) {
  const parsed = await parseJsonBody(request)
  if (!parsed.ok) return parsed.response
  return backendFetch("/", {
    method: "POST",
    body: parsed.body,
    label: "legacy-simulate",
    timeoutMs: 120000,
  })
}
