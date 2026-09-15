import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/mediation/create", {
    method: "POST",
    body: await request.json(),
    label: "mediation-create",
    timeoutMs: 60000,
  })
}
