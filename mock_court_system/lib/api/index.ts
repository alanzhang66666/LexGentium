export * from "@/lib/api/http"
export * from "@/lib/api/config"
export * from "@/lib/api/conversation"
export * from "@/lib/api/simulation"
export * from "@/lib/api/game"
export * from "@/lib/api/evaluate"
export * from "@/lib/api/mediation"
export * from "@/lib/api/sse"

import { apiFetch } from "@/lib/api/http"

export function getHealth() {
  return apiFetch<Record<string, unknown>>("/api/health")
}
