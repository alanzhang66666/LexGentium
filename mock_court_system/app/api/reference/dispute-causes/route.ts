import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/reference/dispute-causes", label: "reference-dispute-causes"})
}
