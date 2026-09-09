import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/reference/dispute-causes", {
    label: "reference-dispute-causes",
  })
}
