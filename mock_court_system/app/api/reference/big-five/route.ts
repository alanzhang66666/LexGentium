import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/reference/big-five-traits", label: "reference-big-five"})
}
