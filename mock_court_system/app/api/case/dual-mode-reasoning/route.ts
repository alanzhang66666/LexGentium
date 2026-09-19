import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/case/dual-mode-reasoning", method: "POST", label: "case-dual-mode", timeoutMs: 180000})
}
