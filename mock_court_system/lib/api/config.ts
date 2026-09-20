import { ApiError, apiFetch } from "@/lib/api/http"

export type LlmConfigPayload = {
  provider: string
  api_key: string
  base_url: string
  model: string
  thinking: "enabled" | "disabled"
  reasoning_effort: "low" | "high" | "max"
  fast_thinking: "enabled" | "disabled"
  fast_reasoning_effort: "low" | "high" | "max"
  temperature: number
  max_tokens: number
  timeout: number
}

export type CurrentLlmConfig = {
  provider: string
  api_key_masked: string
  api_key_set: boolean
  base_url: string
  model: string
  thinking: "enabled" | "disabled"
  reasoning_effort: "low" | "high" | "max"
  fast_thinking: "enabled" | "disabled"
  fast_reasoning_effort: "low" | "high" | "max"
  temperature: number
  max_tokens: number
  timeout: number
  chat_model_ready: boolean
  demo_mode: boolean
}

export type LlmMutationResult = {
  success: boolean
  message?: string
  detail?: string
  reply?: string
  chat_model_ready?: boolean
}

export function defaultLlmPayload(partial?: Partial<LlmConfigPayload>): LlmConfigPayload {
  return {
    provider: "deepseek",
    api_key: "",
    base_url: "",
    model: "",
    thinking: "enabled",
    reasoning_effort: "high",
    fast_thinking: "disabled",
    fast_reasoning_effort: "low",
    temperature: 0.1,
    max_tokens: 4096,
    timeout: 60,
    ...partial,
  }
}

export function getLlmConfig() {
  return apiFetch<CurrentLlmConfig>("/api/config/llm")
}

export function saveLlmConfig(body: LlmConfigPayload, operationId?: string) {
  return apiFetch<LlmMutationResult>("/api/config/llm", {
    method: "POST",
    body: JSON.stringify(body),
    headers: operationId ? { "x-operation-id": operationId } : undefined,
  })
}

export function testLlmConfig(body: LlmConfigPayload, operationId?: string) {
  return apiFetch<LlmMutationResult>("/api/config/llm/test", {
    method: "POST",
    body: JSON.stringify(body),
    headers: operationId ? { "x-operation-id": operationId } : undefined,
  })
}

export function describeApiError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return [err.message, err.detail, err.suggestion].filter(Boolean).join(" — ") || fallback
  }
  if (err instanceof Error && err.message) return err.message
  return fallback
}
