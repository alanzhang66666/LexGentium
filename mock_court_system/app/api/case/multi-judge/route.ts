import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/case/multi-judge", method: "POST", label: "case-multi-judge", timeoutMs: 180000})
}
