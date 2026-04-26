import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/case/full-simulation", {
    method: "POST",
    body: await request.json(),
    label: "full-simulation-start",
    timeoutMs: 60000,
  })
}

