import { backendFetch } from "@/lib/backend-fetch"

export async function GET() {
  return backendFetch("/health", { label: "health", timeoutMs: 10000 })
}

