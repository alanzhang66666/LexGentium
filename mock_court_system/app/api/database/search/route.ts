import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/database/search", method: "POST", label: "database-search", timeoutMs: 60000})
}

