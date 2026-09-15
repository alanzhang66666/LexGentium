import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/reference/big-five-traits", {
    label: "reference-big-five-traits",
  })
}
