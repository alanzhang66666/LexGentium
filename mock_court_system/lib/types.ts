import type { DialogEntry, Scenario } from "@/lib/conversation-types"

export type { DialogEntry, Scenario }

export interface SimulateRequest {
  scenario: Scenario
  case_id: string
  dialog_history: DialogEntry[]
  input_json?: Record<string, unknown>
}

export interface SimulateResponse {
  scenario: string
  case_id: string
  response: {
    role: string
    message: string
  }
}

export interface RequestStatus {
  type: "ready" | "loading" | "error" | "success"
  message?: string
}
