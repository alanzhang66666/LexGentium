import { apiFetch } from "@/lib/api/http"

export type GameStrategySide = {
  strategy_type?: string
  strategy_label?: string
}

export type GameState = {
  game_id: string
  status: string
  rounds_completed?: number
  created_at?: string
  session_id?: string
  strategy_state?: {
    plaintiff?: GameStrategySide
    defendant?: GameStrategySide
  }
  equilibrium?: {
    convergence_rate?: number
    current_convergence?: number
  }
  config?: Record<string, unknown>
  restored?: boolean
  degraded?: boolean
}

export type StrategyHistoryRound = {
  round: number
  plaintiff_strategy?: string
  defendant_strategy?: string
  score?: Record<string, unknown>
  degraded?: boolean
}

export type StrategyHistory = {
  game_id: string
  history?: Array<Record<string, unknown>>
  rounds?: StrategyHistoryRound[]
  degraded?: boolean
}

export type CounterfactualResult = {
  game_id: string
  party?: string
  current_strategy?: string
  hypothetical_strategy?: string
  matrix_prediction?: {
    current_payoff?: { plaintiff?: number; defendant?: number }
    hypothetical_payoff?: { plaintiff?: number; defendant?: number }
    payoff_delta?: { plaintiff?: number; defendant?: number }
  }
  llm_prediction?: Record<string, unknown>
}

export function createGame(body: {
  case_info: Record<string, unknown>
  session_id?: string
  plaintiff_strategy?: string
  defendant_strategy?: string
}) {
  return apiFetch<{ game_id: string; status: string; session_id?: string }>("/api/game/create", {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function listGames() {
  return apiFetch<{ sessions: Array<{ game_id: string; session_id?: string; status: string }>; total: number }>(
    "/api/game/list",
  )
}

export function getGame(gameId: string) {
  return apiFetch<GameState>(`/api/game/${encodeURIComponent(gameId)}`)
}

export function getStrategyHistory(gameId: string) {
  return apiFetch<StrategyHistory>(`/api/game/${encodeURIComponent(gameId)}/strategy/history`)
}

export function getPayoffMatrix(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/strategy/payoff-matrix`,
  )
}

export function getEquilibrium(gameId: string) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/equilibrium`)
}

export function getEquilibriumConvergence(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/equilibrium/convergence`,
  )
}

export function runCounterfactual(
  gameId: string,
  body: { party: "plaintiff" | "defendant"; hypothetical_strategy: string },
) {
  return apiFetch<CounterfactualResult>(`/api/game/${encodeURIComponent(gameId)}/strategy/counterfactual`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function evaluateGameOutcome(gameId: string, partyNames?: string[]) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/evaluate/outcome`, {
    method: "POST",
    body: JSON.stringify(partyNames ? { party_names: partyNames } : {}),
  })
}

export function evaluateGameComposite(gameId: string, partyNames?: string[]) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/evaluate/composite`, {
    method: "POST",
    body: JSON.stringify(partyNames ? { party_names: partyNames } : {}),
  })
}

export function evaluateGameLexeval(gameId: string) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/evaluate/lexeval`, {
    method: "POST",
    body: JSON.stringify({}),
  })
}

export function evaluateGameJ1eval(gameId: string) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/evaluate/j1eval`, {
    method: "POST",
    body: JSON.stringify({}),
  })
}

export function evaluateGameBehaviorSymmetry(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/evaluate/behavior-symmetry`,
    { method: "POST", body: JSON.stringify({}) },
  )
}

export function evaluateGameExplainable(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/evaluate/explainable`,
    { method: "POST", body: JSON.stringify({}) },
  )
}

export function evaluateGameProgressiveBenchmark(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/evaluate/progressive-benchmark`,
    { method: "POST", body: JSON.stringify({}) },
  )
}

export function getGamePolarization(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/evaluate/polarization`,
  )
}

export function getGameComplianceRealtime(gameId: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/compliance/realtime`,
  )
}

export function getLiabilityChain(gameId: string) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/liability-chain`)
}

export function setGameStrategy(
  gameId: string,
  body: { party: "plaintiff" | "defendant"; strategy_type: string; custom_instruction?: string },
) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/strategy/set`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function reflectGameStrategy(
  gameId: string,
  body: { party: "plaintiff" | "defendant"; strategy_type: string },
) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/strategy/reflect`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function runGameRound(gameId: string, evolutionMethod?: string) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/round`, {
    method: "POST",
    body: JSON.stringify(evolutionMethod ? { evolution_method: evolutionMethod } : {}),
  })
}

export function runLiabilityChainCounterfactual(
  gameId: string,
  body: { party: string; original_behavior: string; hypothetical_behavior: string },
) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/liability-chain/counterfactual`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

export function deleteGame(gameId: string) {
  return apiFetch<{ message: string; game_id: string }>(`/api/game/${encodeURIComponent(gameId)}`, {
    method: "DELETE",
  })
}

export function runGameProgressiveRag(
  gameId: string,
  body: { stage: string; context: Record<string, string>; top_k?: number },
) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/progressive-rag`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

export function runGameDualModeReasoning(
  gameId: string,
  body?: { case_info?: string; claims?: string; use_llm_eval?: boolean },
) {
  return apiFetch<Record<string, unknown>>(
    `/api/game/${encodeURIComponent(gameId)}/dual-mode-reasoning`,
    { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) },
  )
}

export function runGameMultiJudge(
  gameId: string,
  body?: {
    case_facts?: string
    claims?: string
    trial_summary?: string
    num_judges?: number
    aggregation?: string
  },
) {
  return apiFetch<Record<string, unknown>>(`/api/game/${encodeURIComponent(gameId)}/multi-judge`, {
    method: "POST",
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
}
