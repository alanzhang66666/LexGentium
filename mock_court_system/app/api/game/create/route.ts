import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/game/create", method: "POST", label: "game-create", timeoutMs: 60000})
}
