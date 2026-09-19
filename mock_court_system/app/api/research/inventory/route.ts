import { type NextRequest } from "next/server"
import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: NextRequest) {
  return proxyJson(request, {path: "/research/inventory", label: "research-inventory"})
}
