import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/case/progressive-rag", method: "POST", label: "case-progressive-rag", timeoutMs: 120000})
}
