import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function POST(request: NextRequest) {
  return proxyJson(request, {path: "/research/evaluate", method: "POST", label: "research-evaluate"})
}
