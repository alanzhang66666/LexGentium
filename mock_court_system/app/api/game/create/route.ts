import { type NextRequest } from "next/server"
import { backendFetch } from "@/lib/backend-fetch"

export async function POST(request: NextRequest) {
  return backendFetch("/game/create", {
    method: "POST",
    body: await request.json(),
    label: "game-create",
    timeoutMs: 60000,
  })
}
