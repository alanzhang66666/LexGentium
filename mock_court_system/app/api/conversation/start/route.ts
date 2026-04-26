import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/conversation/start", {
    method: "POST",
    body: await request.json(),
    label: "conversation-start",
    timeoutMs: 15000,
  })
}

