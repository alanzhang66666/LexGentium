import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/config/llm", { label: "llm-config-get", timeoutMs: 30000 })
}

export async function POST(request: NextRequest) {
  return backendFetch("/config/llm", {
    method: "POST",
    body: await request.json(),
    label: "llm-config-update",
    timeoutMs: 30000,
  })
}

