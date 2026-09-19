import { proxyJson } from "@/lib/backend-proxy"

export async function GET(request: Request) {
  return proxyJson(request, {path: "/reference/progressive-benchmark", label: "reference-progressive-benchmark"})
}
