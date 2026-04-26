export type Scenario = "CD" | "DD" | "CI"

export interface DialogEntry {
  turn?: number | null
  role: string
  message: string
}

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
