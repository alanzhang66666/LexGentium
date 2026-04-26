import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/conversation/import", {
    method: "POST",
    body: await request.json(),
    label: "conversation-import",
    timeoutMs: 30000,
  })
}

