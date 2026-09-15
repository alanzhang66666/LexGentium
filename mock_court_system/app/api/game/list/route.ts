import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/game/list", { label: "game-list" })
}
