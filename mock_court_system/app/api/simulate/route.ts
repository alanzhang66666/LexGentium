import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/", {
    method: "POST",
    body: await request.json(),
    label: "simulate",
    timeoutMs: 120000,
  })
}

