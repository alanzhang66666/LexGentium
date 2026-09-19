import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

/** 1:1 alias for FastAPI POST /. UI keeps POST /api/simulate. */
export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/", method: "POST", label: "legacy-simulate", timeoutMs: 120000})
}
