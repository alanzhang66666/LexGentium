import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/reference/progressive-benchmark", {
    label: "reference-progressive-benchmark",
  })
}
