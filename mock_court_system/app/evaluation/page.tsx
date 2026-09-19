"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { StatusBadge } from "@/components/status-badge"
import { WorkbenchShell } from "@/components/shell"
import { AlertCircle, CheckCircle2, Play, RefreshCw } from "lucide-react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  createGame,
  deleteGame,
  evaluateGameBehaviorSymmetry,
  evaluateGameComposite,
  evaluateGameExplainable,
  evaluateGameJ1eval,
  evaluateGameLexeval,
  evaluateGameOutcome,
  evaluateGameProgressiveBenchmark,
  getCompliance,
  getConversation,
  getEvaluationStatus,
  getEquilibrium,
  getEquilibriumConvergence,
  getGame,
  getGameComplianceRealtime,
  getGamePolarization,
  getLiabilityChain,
  getPayoffMatrix,
  getStrategyHistory,
  listConversations,
  listEvaluationReports,
  reflectGameStrategy,
  runCounterfactual,
  runGameDualModeReasoning,
  runGameMultiJudge,
  runGameProgressiveRag,
  runGameRound,
  runLiabilityChainCounterfactual,
  setGameStrategy,
  startEvaluation,
  compareResearchRuns,
  exportResearchRun,
  reviewResearchRun,
  scoreResearchRun,
} from "@/lib/api"
import { RESEARCH_DISCLAIMER } from "@/lib/research"
import { streamGameRound } from "@/lib/court3d/adapters/gameStream"
import { SCENARIO_DESCRIPTIONS, SCENARIO_LABELS, STAGE_LABELS, STRATEGY_LABELS } from "@/lib/labels"
import { writeLastSessionId } from "@/lib/session/last-session"
import type { CounterfactualResult, GameState, StrategyHistory } from "@/lib/api/game"
import type { EvaluationRequest, EvaluationResponse, EvaluationReportsList } from "@/lib/evaluation-types"
import type { ConversationInfo, ConversationSummary, Scenario, SessionLinks } from "@/lib/conversation-types"
import { cn } from "@/lib/utils"

const SCENARIO_OPTIONS = ["CD", "DD", "CI"] as const
const PANES = [
  { id: "contrast", label: "对照" },
  { id: "strategy", label: "策略推演" },
  { id: "compliance", label: "程序合规" },
  { id: "research", label: "研究" },
] as const
type ReviewPane = (typeof PANES)[number]["id"]
const TKI_KEYS = Object.keys(STRATEGY_LABELS)
const EVOLUTION_METHODS = [
  { id: "llm_reflection", label: "LLM 反思" },
  { id: "best_response", label: "最佳响应" },
  { id: "fictitious_play", label: "虚拟博弈" },
] as const

function parsePane(value: string | null): ReviewPane {
  if (value === "strategy" || value === "compliance" || value === "contrast" || value === "research") return value
  return "contrast"
}

function remapComplianceLabel(label: string) {
  return label
    .replaceAll("原告", "申请人")
    .replaceAll("被告", "被申请人")
    .replaceAll("法庭", "仲裁庭")
    .replaceAll("审判组成", "庭组")
    .replaceAll("诉讼请求", "仲裁请求")
    .replaceAll("调解", "和解")
}

function metricCards(results: Record<string, unknown> | undefined) {
  if (!results || typeof results !== "object") return []
  const cards: { title: string; rows: { label: string; value: string }[] }[] = []
  for (const [key, value] of Object.entries(results)) {
    if (!["CD", "DD", "CI"].includes(key)) continue
    const title = SCENARIO_LABELS[key] || key
    if (Array.isArray(value)) {
      const scores = value
        .map((item) => {
          if (!item || typeof item !== "object") return null
          const score = (item as { score?: unknown }).score
          if (typeof score === "number") return score
          if (score && typeof score === "object") {
            const nums = Object.values(score).filter((n): n is number => typeof n === "number")
            if (!nums.length) return null
            return nums.reduce((a, b) => a + b, 0) / nums.length
          }
          return null
        })
        .filter((n): n is number => n != null)
      cards.push({
        title,
        rows: [
          { label: "条数", value: String(value.length) },
          {
            label: "均分",
            value: scores.length ? ((scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(3)) : "-",
          },
        ],
      })
      continue
    }
    if (value && typeof value === "object") {
      const rows = Object.entries(value as Record<string, unknown>)
        .filter(([, v]) => typeof v === "number" || typeof v === "string")
        .slice(0, 6)
        .map(([label, v]) => ({ label, value: typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(3)) : String(v) }))
      if (rows.length) cards.push({ title, rows })
    }
  }
  return cards
}

function EvaluationInner() {
  const router = useRouter()
  const search = useSearchParams()
  const pane = parsePane(search.get("pane"))
  const sessionFromUrl = search.get("session") || ""

  const [sessionId, setSessionId] = useState(sessionFromUrl)
  const [bound, setBound] = useState<ConversationInfo | null>(null)
  const [sessions, setSessions] = useState<ConversationSummary[]>([])
  const [sessionsError, setSessionsError] = useState<string | null>(null)
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>(["CI"])
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResponse | null>(null)
  const [polling, setPolling] = useState(false)
  const [reportsList, setReportsList] = useState<EvaluationReportsList | null>(null)
  const [reportsLoading, setReportsLoading] = useState(true)

  const [game, setGame] = useState<GameState | null>(null)
  const [history, setHistory] = useState<StrategyHistory | null>(null)
  const [gameBusy, setGameBusy] = useState(false)
  const [cfParty, setCfParty] = useState<"plaintiff" | "defendant">("plaintiff")
  const [cfStrategy, setCfStrategy] = useState("compromising")
  const [cfResult, setCfResult] = useState<CounterfactualResult | null>(null)
  const [gameEvalBusy, setGameEvalBusy] = useState(false)
  const [gameEvalKind, setGameEvalKind] = useState<string | null>(null)
  const [gameEvalResult, setGameEvalResult] = useState<Record<string, unknown> | null>(null)
  const [gameMissing, setGameMissing] = useState(false)
  const [setParty, setSetParty] = useState<"plaintiff" | "defendant">("plaintiff")
  const [setStrategyType, setSetStrategyType] = useState("compromising")
  const [setInstruction, setSetInstruction] = useState("")
  const [reflectParty, setReflectParty] = useState<"plaintiff" | "defendant">("plaintiff")
  const [reflectMethod, setReflectMethod] = useState("llm_reflection")
  const [roundMethod, setRoundMethod] = useState("llm_reflection")
  const [lcParty, setLcParty] = useState("申请人")
  const [lcOriginal, setLcOriginal] = useState("")
  const [lcHypothetical, setLcHypothetical] = useState("")
  const [deleteArmed, setDeleteArmed] = useState(false)

  const [compliance, setCompliance] = useState<unknown>(null)
  const [complianceScenario, setComplianceScenario] = useState<string>("")
  const [researchBusy, setResearchBusy] = useState(false)
  const [researchEval, setResearchEval] = useState<Record<string, unknown> | null>(null)
  const [researchCompare, setResearchCompare] = useState<Record<string, unknown> | null>(null)
  const [compareIds, setCompareIds] = useState("")
  const [reviewer, setReviewer] = useState("")
  const [reviewNote, setReviewNote] = useState("")
  const [reviewState, setReviewState] = useState("pending")

  const setQuery = (next: { session?: string; pane?: ReviewPane }) => {
    const params = new URLSearchParams()
    const nextSession = next.session ?? sessionId
    const nextPane = next.pane ?? pane
    if (nextSession) params.set("session", nextSession)
    params.set("pane", nextPane)
    router.replace(`/evaluation?${params.toString()}`)
  }

  useEffect(() => {
    setSessionId(sessionFromUrl)
  }, [sessionFromUrl])

  useEffect(() => {
    if (sessionId) writeLastSessionId(sessionId)
  }, [sessionId])

  useEffect(() => {
    listConversations(50)
      .then((data) => {
        setSessions(data.sessions || [])
        setSessionsError(null)
      })
      .catch((error) => {
        setSessions([])
        setSessionsError(error instanceof Error ? error.message : "无法加载会话")
      })
    loadReportsList()
  }, [])

  useEffect(() => {
    if (!sessionId) {
      setBound(null)
      setGame(null)
      setHistory(null)
      setCompliance(null)
      return
    }
    getConversation(sessionId)
      .then((info) => {
        setBound(info)
        const scenario = (info.scenario as Scenario) || "CI"
        setSelectedScenarios([scenario])
      })
      .catch(() => setBound(null))
  }, [sessionId])

  useEffect(() => {
    const gameId = bound?.links?.game_id
    if (!gameId || pane !== "strategy") {
      if (!gameId) {
        setGame(null)
        setHistory(null)
        setGameMissing(false)
      }
      return
    }
    Promise.all([getGame(gameId), getStrategyHistory(gameId)])
      .then(([g, h]) => {
        setGame(g)
        setHistory(h)
        setGameMissing(false)
      })
      .catch(() => {
        setGame(null)
        setHistory(null)
        setGameMissing(true)
      })
  }, [bound?.links?.game_id, pane])

  useEffect(() => {
    if (!sessionId || pane !== "compliance") {
      setCompliance(null)
      return
    }
    getCompliance(sessionId)
      .then((data) => {
        setComplianceScenario(data.scenario)
        setCompliance(data.compliance)
      })
      .catch((error) => {
        setCompliance({ error: error instanceof Error ? error.message : "无法加载合规" })
      })
  }, [sessionId, pane])

  useEffect(() => {
    if (polling && evaluationResult?.report_id) {
      const interval = setInterval(async () => {
        try {
          const data = await getEvaluationStatus(evaluationResult.report_id)
          setEvaluationResult(data)
          if (data.status === "completed" || data.status === "failed") {
            setPolling(false)
            loadReportsList()
            if (sessionId) {
              getConversation(sessionId).then(setBound).catch(() => null)
            }
          }
        } catch (error) {
          console.error("轮询对照状态失败:", error)
        }
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [polling, evaluationResult?.report_id, sessionId])

  const loadReportsList = async () => {
    setReportsLoading(true)
    try {
      setReportsList(await listEvaluationReports())
    } catch (error) {
      console.error("加载对照报告列表失败:", error)
    } finally {
      setReportsLoading(false)
    }
  }

  const bindSession = (id: string) => {
    setSessionId(id)
    writeLastSessionId(id)
    setQuery({ session: id })
  }

  const handleStartEvaluation = async () => {
    if (!sessionId) {
      setErrorMessage("请先绑定本场会话")
      return
    }
    if (selectedScenarios.length === 0) {
      setErrorMessage("请至少选择一个场景")
      return
    }
    setErrorMessage(null)
    setEvaluationResult(null)
    setIsLoading(true)
    try {
      const request: EvaluationRequest = {
        scenarios: selectedScenarios,
        session_id: sessionId,
        use_default_predictions: false,
      }
      const result = await startEvaluation(request)
      setEvaluationResult(result)
      if (result.status === "running") setPolling(true)
    } catch (error) {
      setErrorMessage(`请求失败: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setIsLoading(false)
    }
  }

  const openGame = async () => {
    if (!sessionId || !bound) return
    setGameBusy(true)
    setErrorMessage(null)
    try {
      await createGame({
        case_info: { case_id: bound.case_id },
        session_id: sessionId,
      })
      const next = await getConversation(sessionId)
      setBound(next)
      setGameMissing(false)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "开局失败")
    } finally {
      setGameBusy(false)
    }
  }

  const playRound = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    setGameBusy(true)
    setErrorMessage(null)
    try {
      await streamGameRound(gameId, () => {})
      const [g, h] = await Promise.all([getGame(gameId), getStrategyHistory(gameId)])
      setGame(g)
      setHistory(h)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "推演失败")
    } finally {
      setGameBusy(false)
    }
  }

  const runGameEval = async (
    kind:
      | "outcome"
      | "composite"
      | "lexeval"
      | "j1eval"
      | "cadd"
      | "behavior-symmetry"
      | "explainable"
      | "progressive-benchmark"
      | "polarization"
      | "compliance-realtime"
      | "payoff-matrix"
      | "equilibrium"
      | "equilibrium-convergence",
  ) => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    setGameBusy(true)
    setGameEvalBusy(true)
    setGameEvalKind(kind)
    setErrorMessage(null)
    try {
      const result =
        kind === "outcome"
          ? await evaluateGameOutcome(gameId)
          : kind === "composite"
            ? await evaluateGameComposite(gameId)
            : kind === "lexeval"
              ? await evaluateGameLexeval(gameId)
              : kind === "j1eval"
                ? await evaluateGameJ1eval(gameId)
                : kind === "cadd"
                  ? await getLiabilityChain(gameId)
                  : kind === "behavior-symmetry"
                    ? await evaluateGameBehaviorSymmetry(gameId)
                    : kind === "explainable"
                      ? await evaluateGameExplainable(gameId)
                      : kind === "progressive-benchmark"
                        ? await evaluateGameProgressiveBenchmark(gameId)
                        : kind === "polarization"
                          ? await getGamePolarization(gameId)
                          : kind === "compliance-realtime"
                            ? await getGameComplianceRealtime(gameId)
                            : kind === "payoff-matrix"
                              ? await getPayoffMatrix(gameId)
                              : kind === "equilibrium"
                                ? await getEquilibrium(gameId)
                                : await getEquilibriumConvergence(gameId)
      setGameEvalResult(result)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "博弈评测失败")
    } finally {
      setGameBusy(false)
      setGameEvalBusy(false)
    }
  }

  const runCf = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    setGameBusy(true)
    setErrorMessage(null)
    try {
      setCfResult(await runCounterfactual(gameId, { party: cfParty, hypothetical_strategy: cfStrategy }))
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "反事实失败")
    } finally {
      setGameBusy(false)
    }
  }

  const refreshBoundGame = async (gameId: string) => {
    const [g, h] = await Promise.all([getGame(gameId), getStrategyHistory(gameId)])
    setGame(g)
    setHistory(h)
    setGameMissing(false)
  }

  const handleSetStrategy = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    setGameBusy(true)
    setGameEvalKind("strategy-set")
    setErrorMessage(null)
    try {
      const result = await setGameStrategy(gameId, {
        party: setParty,
        strategy_type: setStrategyType,
        custom_instruction: setInstruction.trim() || undefined,
      })
      setGameEvalResult(result)
      await refreshBoundGame(gameId)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "设定策略失败")
    } finally {
      setGameBusy(false)
    }
  }

  const handleReflectStrategy = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    setGameBusy(true)
    setGameEvalKind("strategy-reflect")
    setErrorMessage(null)
    try {
      const result = await reflectGameStrategy(gameId, {
        party: reflectParty,
        strategy_type: reflectMethod,
      })
      setGameEvalResult(result)
      await refreshBoundGame(gameId)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "策略反思失败")
    } finally {
      setGameBusy(false)
    }
  }

  const playRoundSync = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    setGameBusy(true)
    setGameEvalKind("round-sync")
    setErrorMessage(null)
    try {
      const result = await runGameRound(gameId, roundMethod)
      setGameEvalResult(result)
      await refreshBoundGame(gameId)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "非流式一轮失败")
    } finally {
      setGameBusy(false)
    }
  }

  const handleLiabilityCf = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId) return
    if (!lcOriginal.trim() || !lcHypothetical.trim()) {
      setErrorMessage("责任链反事实需要填写原行为与假设行为")
      return
    }
    setGameBusy(true)
    setGameEvalKind("liability-cf")
    setErrorMessage(null)
    try {
      const result = await runLiabilityChainCounterfactual(gameId, {
        party: lcParty,
        original_behavior: lcOriginal.trim(),
        hypothetical_behavior: lcHypothetical.trim(),
      })
      setGameEvalResult(result)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "责任链反事实失败")
    } finally {
      setGameBusy(false)
    }
  }

  const runGameInnovation = async (kind: "progressive-rag" | "dual-mode" | "multi-judge") => {
    const gameId = bound?.links?.game_id
    if (!gameId || !bound) return
    setGameBusy(true)
    setGameEvalBusy(true)
    setGameEvalKind(kind)
    setErrorMessage(null)
    try {
      const result =
        kind === "progressive-rag"
          ? await runGameProgressiveRag(gameId, {
              stage:
                bound.current_stage === "opening" ||
                bound.current_stage === "investigation" ||
                bound.current_stage === "debate" ||
                bound.current_stage === "judgment"
                  ? bound.current_stage
                  : "investigation",
              context: {
                query: bound.case_id || "本案争议焦点",
                raw_query: bound.case_id || "本案争议焦点",
              },
              top_k: 5,
            })
          : kind === "dual-mode"
            ? await runGameDualModeReasoning(gameId)
            : await runGameMultiJudge(gameId)
      setGameEvalResult(result)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "会话版创新调用失败")
    } finally {
      setGameBusy(false)
      setGameEvalBusy(false)
    }
  }

  const handleDeleteGame = async () => {
    const gameId = bound?.links?.game_id
    if (!gameId || !deleteArmed) return
    setGameBusy(true)
    setGameEvalKind("game-delete")
    setErrorMessage(null)
    try {
      const result = await deleteGame(gameId)
      setGameEvalResult(result)
      setGame(null)
      setHistory(null)
      setGameMissing(true)
      setDeleteArmed(false)
      setCfResult(null)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "删除失败")
    } finally {
      setGameBusy(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "success"
      case "running":
        return "loading"
      case "failed":
        return "error"
      default:
        return "ready"
    }
  }

  const links: SessionLinks = bound?.links || {}
  const summaryCards = useMemo(
    () => metricCards(evaluationResult?.results as Record<string, unknown> | undefined),
    [evaluationResult?.results],
  )

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-[22px] font-medium tracking-tight">复盘</h1>
            <p className="mt-1 text-sm text-muted-foreground">对照本场、策略推演、程序合规与研究量表。评测套件不在此页展开。</p>
          </div>
          <div className="flex rounded-md border border-border p-0.5">
            {PANES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setQuery({ pane: item.id })}
                className={cn(
                  "rounded-md px-3 py-1.5 text-[13px] font-medium",
                  pane === item.id ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {errorMessage ? (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        ) : null}

        {pane === "contrast" ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">对照本场</CardTitle>
                  <CardDescription>仅评本场已确认的最终文书。民事分数是结构检查，不代表法律正确性；研究质量请使用研究量表。</CardDescription>
                </div>
                {evaluationResult ? (
                  <StatusBadge status={getStatusColor(evaluationResult.status)}>
                    {evaluationResult.status === "running" && "运行中"}
                    {evaluationResult.status === "completed" && "已完成"}
                    {evaluationResult.status === "failed" && "失败"}
                  </StatusBadge>
                ) : null}
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>本场会话</Label>
                  {sessionsError ? (
                    <p className="text-sm text-destructive">未连接，无法列出会话</p>
                  ) : (
                    <Select value={sessionId || undefined} onValueChange={bindSession}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="选择一场听证" />
                      </SelectTrigger>
                      <SelectContent>
                        {(bound && !sessions.some((s) => s.session_id === bound.session_id)
                          ? [
                              {
                                session_id: bound.session_id,
                                scenario: bound.scenario,
                                case_id: bound.case_id,
                              },
                              ...sessions,
                            ]
                          : sessions
                        ).map((s) => (
                          <SelectItem key={s.session_id} value={s.session_id}>
                            {SCENARIO_LABELS[s.scenario] || s.scenario} · {s.case_id} · {s.session_id.slice(0, 8)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  {bound ? (
                    <p className="text-[12px] text-muted-foreground">
                      {SCENARIO_LABELS[bound.scenario] || bound.scenario}
                      {bound.current_stage ? ` · ${STAGE_LABELS[bound.current_stage] || bound.current_stage}` : ""}
                      {links.report_id ? ` · 报告 ${links.report_id.slice(0, 10)}` : " · 未对照"}
                    </p>
                  ) : null}
                </div>

                <div className="space-y-2">
                  <Label>场景</Label>
                  <div className="space-y-1">
                    {SCENARIO_OPTIONS.map((value) => (
                      <label
                        key={value}
                        className="flex cursor-pointer items-center gap-3 rounded-md border border-border px-3 py-2 hover:bg-secondary"
                      >
                        <Checkbox
                          disabled={Boolean(bound && bound.scenario !== value)}
                          checked={selectedScenarios.includes(value)}
                          onCheckedChange={() =>
                            setSelectedScenarios((prev) =>
                              prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
                            )
                          }
                        />
                        <span className="text-sm font-medium">{SCENARIO_LABELS[value]}</span>
                        <span className="text-xs text-muted-foreground">{SCENARIO_DESCRIPTIONS[value]}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <Button onClick={handleStartEvaluation} disabled={isLoading || !sessionId || selectedScenarios.length === 0}>
                  <Play className="size-3.5" />
                  {isLoading ? "启动中..." : "开始对照"}
                </Button>

                {evaluationResult ? (
                  <div className="space-y-3 rounded-md border border-border p-3">
                    <div className="flex items-center gap-2 text-sm">
                      {evaluationResult.status === "completed" ? (
                        <CheckCircle2 className="size-4 text-success" />
                      ) : (
                        <AlertCircle className="size-4 text-muted-foreground" />
                      )}
                      {evaluationResult.message}
                    </div>
                    {evaluationResult.report_id ? (
                      <p className="font-mono text-xs text-muted-foreground">{evaluationResult.report_id}</p>
                    ) : null}
                    {summaryCards.length > 0 ? (
                      <div className="grid gap-2 sm:grid-cols-2">
                        {summaryCards.map((card) => (
                          <div key={card.title} className="rounded-md border border-border px-3 py-2">
                            <div className="text-[13px] font-medium">{card.title}</div>
                            {card.rows.map((row) => (
                              <div key={row.label} className="mt-1 flex justify-between text-[12px] text-muted-foreground">
                                <span>{row.label}</span>
                                <span className="tabular-nums text-foreground">{row.value}</span>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {evaluationResult.report_id && evaluationResult.status === "completed" ? (
                      <Button variant="outline" size="sm" onClick={() => router.push(`/evaluation/reports/${evaluationResult.report_id}`)}>
                        打开报告
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">最近报告</CardTitle>
                  <CardDescription>对照摘要</CardDescription>
                </div>
                <Button variant="ghost" size="icon-sm" onClick={loadReportsList}>
                  <RefreshCw className="size-3.5" />
                </Button>
              </CardHeader>
              <CardContent>
                {reportsLoading ? (
                  <div className="divide-y divide-border rounded-lg border border-border">
                    {Array.from({ length: 4 }).map((_, i) => (
                      <div key={i} className="px-3 py-2.5">
                        <div className="h-3.5 w-48 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                      </div>
                    ))}
                  </div>
                ) : reportsList && reportsList.reports.length > 0 ? (
                  <div className="divide-y divide-border rounded-lg border border-border">
                    {reportsList.reports.slice(0, 10).map((report) => (
                      <button
                        key={report.report_id}
                        type="button"
                        className="flex w-full items-center justify-between px-3 py-2.5 text-left hover:bg-secondary"
                        onClick={() => router.push(`/evaluation/reports/${report.report_id}`)}
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm">{report.file_name}</div>
                          <div className="text-xs tabular-nums text-muted-foreground">
                            {report.scenarios.map((s) => SCENARIO_LABELS[s] || s).join(" · ")} · {report.created_at}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="px-3 py-10 text-center">
                    <p className="text-sm text-foreground">还没有对照报告</p>
                    <p className="mt-2 text-sm text-muted-foreground">先绑定本场再开始对照。</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        ) : null}

        {pane === "strategy" ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">策略推演</CardTitle>
                <CardDescription>立场、轮次、收敛与轨迹。无局则为本场开局。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>本场会话</Label>
                  {sessionsError ? (
                    <p className="text-sm text-destructive">未连接，无法列出会话</p>
                  ) : (
                    <Select value={sessionId || undefined} onValueChange={bindSession}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="选择一场听证" />
                      </SelectTrigger>
                      <SelectContent>
                        {sessions.map((s) => (
                          <SelectItem key={s.session_id} value={s.session_id}>
                            {SCENARIO_LABELS[s.scenario] || s.scenario} · {s.case_id} · {s.session_id.slice(0, 8)}
                            {s.links?.game_id ? " · 有局" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>
                {!sessionId ? (
                  <p className="text-sm text-muted-foreground">先绑定一场听证。有 game_id 时可直接评测。</p>
                ) : !links.game_id || gameMissing ? (
                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      {gameMissing
                        ? "本场 game_id 无法从内存或存档恢复，请重新开局。"
                        : "本场尚未开策略局。"}
                    </p>
                    {gameEvalResult && gameEvalKind === "game-delete" ? (
                      <Alert>
                        <CheckCircle2 className="h-4 w-4" />
                        <AlertDescription>
                          已删除{" "}
                          {typeof gameEvalResult.game_id === "string" ? gameEvalResult.game_id : "本局"}
                          。可重新开局。
                        </AlertDescription>
                      </Alert>
                    ) : null}
                    <Button onClick={openGame} disabled={gameBusy || !bound}>
                      {gameBusy ? "开局中…" : "为本场开局"}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3 text-sm">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="rounded-md border border-border px-3 py-2">
                        <div className="text-[12px] text-muted-foreground">申请人</div>
                        <div>
                          {STRATEGY_LABELS[game?.strategy_state?.plaintiff?.strategy_type || ""] ||
                            game?.strategy_state?.plaintiff?.strategy_label ||
                            "-"}
                        </div>
                      </div>
                      <div className="rounded-md border border-border px-3 py-2">
                        <div className="text-[12px] text-muted-foreground">被申请人</div>
                        <div>
                          {STRATEGY_LABELS[game?.strategy_state?.defendant?.strategy_type || ""] ||
                            game?.strategy_state?.defendant?.strategy_label ||
                            "-"}
                        </div>
                      </div>
                    </div>
                    <p className="text-[12px] tabular-nums text-muted-foreground">
                      轮次 {game?.rounds_completed ?? 0}
                      {game?.equilibrium?.convergence_rate != null
                        ? ` · 收敛 ${(game.equilibrium.convergence_rate * 100).toFixed(1)}%`
                        : ""}
                      {game?.status ? ` · ${game.status}` : ""}
                      {game?.restored ? " · 已从存档恢复" : ""}
                    </p>
                    {game?.degraded || history?.degraded ? (
                      <Alert>
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>
                          当前未配置 LLM 或评分失败，本局分数为降级占位，不是真实评测。
                        </AlertDescription>
                      </Alert>
                    ) : null}
                    <div className="flex flex-wrap items-center gap-2">
                      <Button variant="outline" onClick={playRound} disabled={gameBusy}>
                        {gameBusy ? "推演中…" : "推演一轮"}
                      </Button>
                      <span className="text-[12px] text-muted-foreground">SSE 正式推演</span>
                    </div>
                    <div className="space-y-2 rounded-md border border-dashed border-border px-3 py-3">
                      <p className="text-[13px] font-medium">非流式一轮（调试）</p>
                      <p className="text-[12px] text-muted-foreground">
                        一次返回整轮 JSON，不替代上方「推演一轮」。仅排障用。
                      </p>
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label>进化方法</Label>
                          <Select value={roundMethod} onValueChange={setRoundMethod}>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {EVOLUTION_METHODS.map((item) => (
                                <SelectItem key={item.id} value={item.id}>
                                  {item.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" onClick={playRoundSync} disabled={gameBusy}>
                        {gameBusy && gameEvalKind === "round-sync" ? "请求中…" : "非流式一轮（调试）"}
                      </Button>
                    </div>
                    <div className="space-y-2 rounded-md border border-border px-3 py-3">
                      <p className="text-[13px] font-medium">设定策略</p>
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label>一方</Label>
                          <Select value={setParty} onValueChange={(v) => setSetParty(v as "plaintiff" | "defendant")}>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="plaintiff">申请人</SelectItem>
                              <SelectItem value="defendant">被申请人</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1.5">
                          <Label>TKI 立场</Label>
                          <Select value={setStrategyType} onValueChange={setSetStrategyType}>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {TKI_KEYS.map((key) => (
                                <SelectItem key={key} value={key}>
                                  {STRATEGY_LABELS[key]}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <Textarea
                        value={setInstruction}
                        onChange={(e) => setSetInstruction(e.target.value)}
                        placeholder="可选自定义指令"
                        rows={2}
                      />
                      <Button variant="outline" size="sm" onClick={handleSetStrategy} disabled={gameBusy}>
                        {gameBusy && gameEvalKind === "strategy-set" ? "设定中…" : "设定策略"}
                      </Button>
                    </div>
                    <div className="space-y-2 rounded-md border border-border px-3 py-3">
                      <p className="text-[13px] font-medium">策略反思</p>
                      <p className="text-[12px] text-muted-foreground">按上一轮轨迹进化一方策略。至少先推演一轮。</p>
                      <div className="grid gap-2 sm:grid-cols-2">
                        <div className="space-y-1.5">
                          <Label>一方</Label>
                          <Select
                            value={reflectParty}
                            onValueChange={(v) => setReflectParty(v as "plaintiff" | "defendant")}
                          >
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="plaintiff">申请人</SelectItem>
                              <SelectItem value="defendant">被申请人</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1.5">
                          <Label>方法</Label>
                          <Select value={reflectMethod} onValueChange={setReflectMethod}>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {EVOLUTION_METHODS.map((item) => (
                                <SelectItem key={item.id} value={item.id}>
                                  {item.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" onClick={handleReflectStrategy} disabled={gameBusy}>
                        {gameBusy && gameEvalKind === "strategy-reflect" ? "反思中…" : "策略反思"}
                      </Button>
                    </div>
                    <div className="space-y-2 rounded-md border border-border px-3 py-3">
                      <p className="text-[13px] font-medium">博弈评测</p>
                      <p className="text-[12px] text-muted-foreground">
                        调用已有 /game/{"{id}"}/evaluate/*。无局时不显示。需至少推演一轮才有结果。
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {(
                          [
                            ["outcome", "结果"],
                            ["composite", "综合"],
                            ["lexeval", "LexEval"],
                            ["j1eval", "J1Eval"],
                            ["cadd", "CADD 责任链"],
                            ["behavior-symmetry", "行为对称"],
                            ["explainable", "可解释"],
                            ["progressive-benchmark", "渐进基准"],
                            ["polarization", "极化"],
                            ["compliance-realtime", "实时合规"],
                            ["payoff-matrix", "收益矩阵"],
                            ["equilibrium", "均衡"],
                            ["equilibrium-convergence", "收敛"],
                          ] as const
                        ).map(([kind, label]) => (
                          <Button
                            key={kind}
                            variant="outline"
                            size="sm"
                            disabled={gameBusy || gameEvalBusy}
                            onClick={() => runGameEval(kind)}
                          >
                            {gameEvalBusy && gameEvalKind === kind ? "评测中…" : label}
                          </Button>
                        ))}
                      </div>
                      <div className="space-y-2 border-t border-border pt-3">
                        <p className="text-[13px] font-medium">会话版创新</p>
                        <p className="text-[12px] text-muted-foreground">
                          打本局 <code className="font-mono">/game/{"{id}"}</code>
                          ，与系统页 <code className="font-mono">/case/*</code> 实验面板分开。
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {(
                            [
                              ["progressive-rag", "渐进检索 会话版"],
                              ["dual-mode", "双模式推理 会话版"],
                              ["multi-judge", "多法官 会话版"],
                            ] as const
                          ).map(([kind, label]) => (
                            <Button
                              key={kind}
                              variant="outline"
                              size="sm"
                              disabled={gameBusy || gameEvalBusy || !links.game_id}
                              onClick={() => runGameInnovation(kind)}
                            >
                              {gameEvalBusy && gameEvalKind === kind ? "请求中…" : label}
                            </Button>
                          ))}
                        </div>
                      </div>
                      {gameEvalResult ? (
                        <div className="space-y-2">
                          {Boolean(gameEvalResult.degraded) ||
                          (gameEvalResult.game_score &&
                            typeof gameEvalResult.game_score === "object" &&
                            Boolean((gameEvalResult.game_score as { degraded?: boolean }).degraded)) ? (
                            <p className="text-[12px] text-warning">
                              评测含降级占位分，未配置 LLM 时不要把数字当成真实结果。
                            </p>
                          ) : null}
                          <pre className="max-h-64 overflow-auto rounded-md bg-muted/40 p-2 font-mono text-[11px]">
                            {JSON.stringify(gameEvalResult, null, 2)}
                          </pre>
                        </div>
                      ) : null}
                    </div>
                    <div className="divide-y divide-border rounded-md border border-border">
                      {(history?.rounds || []).length === 0 ? (
                        <p className="px-3 py-6 text-center text-[13px] text-muted-foreground">还没有轨迹</p>
                      ) : (
                        (history?.rounds || []).map((row) => (
                          <div key={row.round} className="flex justify-between gap-3 px-3 py-2 text-[13px]">
                            <span className="tabular-nums text-muted-foreground">第 {row.round + 1} 轮</span>
                            <span className="text-right">
                              {STRATEGY_LABELS[row.plaintiff_strategy || ""] || row.plaintiff_strategy} /{" "}
                              {STRATEGY_LABELS[row.defendant_strategy || ""] || row.defendant_strategy}
                              {row.degraded || (row.score && row.score.degraded) ? (
                                <span className="ml-2 text-warning">降级/离线</span>
                              ) : null}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="space-y-2 rounded-md border border-border px-3 py-3">
                      <p className="text-[13px] font-medium">删除本局</p>
                      <p className="text-[12px] text-muted-foreground">
                        仅清内存局，需二次确认。演示局请勿误删。
                      </p>
                      {!deleteArmed ? (
                        <Button variant="outline" size="sm" onClick={() => setDeleteArmed(true)} disabled={gameBusy}>
                          删除本局
                        </Button>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          <Button variant="destructive" size="sm" onClick={handleDeleteGame} disabled={gameBusy}>
                            {gameBusy ? "删除中…" : "确认删除本局"}
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => setDeleteArmed(false)} disabled={gameBusy}>
                            取消
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">反事实</CardTitle>
                <CardDescription>假设一方改立场，看收益变化。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>一方</Label>
                    <Select value={cfParty} onValueChange={(v) => setCfParty(v as "plaintiff" | "defendant")}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="plaintiff">申请人</SelectItem>
                        <SelectItem value="defendant">被申请人</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>假设立场</Label>
                    <Select value={cfStrategy} onValueChange={setCfStrategy}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TKI_KEYS.map((key) => (
                          <SelectItem key={key} value={key}>
                            {STRATEGY_LABELS[key]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button variant="outline" onClick={runCf} disabled={gameBusy || !links.game_id}>
                  推演反事实
                </Button>
                {cfResult ? (
                  <div className="space-y-2 rounded-md border border-border px-3 py-2 text-[13px]">
                    <p>
                      当前 {STRATEGY_LABELS[cfResult.current_strategy || ""] || cfResult.current_strategy} →{" "}
                      {STRATEGY_LABELS[cfResult.hypothetical_strategy || ""] || cfResult.hypothetical_strategy}
                    </p>
                    {cfResult.matrix_prediction?.payoff_delta ? (
                      <p className="tabular-nums text-muted-foreground">
                        申请人 Δ {cfResult.matrix_prediction.payoff_delta.plaintiff ?? "-"} · 被申请人 Δ{" "}
                        {cfResult.matrix_prediction.payoff_delta.defendant ?? "-"}
                      </p>
                    ) : null}
                    {typeof cfResult.llm_prediction?.recommendation === "string" ? (
                      <p>{cfResult.llm_prediction.recommendation}</p>
                    ) : null}
                  </div>
                ) : null}
                <div className="space-y-2 border-t border-border pt-3">
                  <p className="text-[13px] font-medium">责任链</p>
                  <p className="text-[12px] text-muted-foreground">
                    GET 抽取见左侧「CADD 责任链」。此处做行为反事实（需至少推演一轮）。
                  </p>
                  <div className="space-y-1.5">
                    <Label>一方</Label>
                    <Input value={lcParty} onChange={(e) => setLcParty(e.target.value)} placeholder="申请人 / 被申请人" />
                  </div>
                  <div className="space-y-1.5">
                    <Label>原行为</Label>
                    <Textarea
                      value={lcOriginal}
                      onChange={(e) => setLcOriginal(e.target.value)}
                      placeholder="原行为"
                      rows={2}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>假设行为</Label>
                    <Textarea
                      value={lcHypothetical}
                      onChange={(e) => setLcHypothetical(e.target.value)}
                      placeholder="假设行为"
                      rows={2}
                    />
                  </div>
                  <Button variant="outline" size="sm" onClick={handleLiabilityCf} disabled={gameBusy || !links.game_id}>
                    {gameBusy && gameEvalKind === "liability-cf" ? "分析中…" : "责任链反事实"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : null}

        {pane === "research" ? (
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">研究评价</CardTitle>
                <CardDescription>六维量表。机器检查不等于法律质量。有依据的不同路径可复核。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {!bound?.research?.run_id ? (
                  <p className="text-sm text-muted-foreground">先绑定一场带研究包的会话。</p>
                ) : (
                  <>
                    <p className="break-all text-[12px] text-muted-foreground">
                      {bound.research.run_id}
                      {bound.research.materials_hash ? ` · ${bound.research.materials_hash.slice(0, 12)}` : ""}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        disabled={researchBusy}
                        onClick={async () => {
                          setResearchBusy(true)
                          setErrorMessage(null)
                          try {
                            setResearchEval(await scoreResearchRun({ run_id: bound.research?.run_id, session_id: sessionId }))
                          } catch (err) {
                            setErrorMessage(err instanceof Error ? err.message : "研究评价失败")
                          } finally {
                            setResearchBusy(false)
                          }
                        }}
                      >
                        六维打分
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={researchBusy || !bound.research.run_id}
                        onClick={async () => {
                          if (!bound.research?.run_id) return
                          setResearchBusy(true)
                          try {
                            const bundle = await exportResearchRun(bound.research.run_id)
                            const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" })
                            const url = URL.createObjectURL(blob)
                            const a = document.createElement("a")
                            a.href = url
                            a.download = `research_${bound.research.run_id}.json`
                            a.click()
                            URL.revokeObjectURL(url)
                          } catch (err) {
                            setErrorMessage(err instanceof Error ? err.message : "导出失败")
                          } finally {
                            setResearchBusy(false)
                          }
                        }}
                      >
                        导出研究包
                      </Button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Input placeholder="复核人" value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
                      <Select value={reviewState} onValueChange={setReviewState}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="pending">pending</SelectItem>
                          <SelectItem value="tech_checked">tech_checked</SelectItem>
                          <SelectItem value="law_reviewed">law_reviewed</SelectItem>
                          <SelectItem value="disputed">disputed</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <Textarea placeholder="复核说明（失败 / 分歧 / 无法判断请留下）" value={reviewNote} onChange={(e) => setReviewNote(e.target.value)} />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={researchBusy || !bound.research.run_id}
                      onClick={async () => {
                        if (!bound.research?.run_id) return
                        setResearchBusy(true)
                        try {
                          await reviewResearchRun({
                            run_id: bound.research.run_id,
                            review_state: reviewState as "pending" | "tech_checked" | "law_reviewed" | "disputed",
                            reviewer,
                            note: reviewNote,
                          })
                        } catch (err) {
                          setErrorMessage(err instanceof Error ? err.message : "复核失败")
                        } finally {
                          setResearchBusy(false)
                        }
                      }}
                    >
                      写入人工复核
                    </Button>
                    {researchEval ? (
                      <pre className="max-h-80 overflow-auto rounded-md border border-border bg-secondary/30 p-2 text-[11px]">
                        {JSON.stringify(researchEval, null, 2)}
                      </pre>
                    ) : null}
                  </>
                )}
                <p className="text-[12px] leading-snug text-muted-foreground">{RESEARCH_DISCLAIMER}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">同案条件对比</CardTitle>
                <CardDescription>比较两次运行的材料哈希、条件与评分。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input
                  placeholder="run_id,run_id"
                  value={compareIds}
                  onChange={(e) => setCompareIds(e.target.value)}
                />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={researchBusy}
                  onClick={async () => {
                    setResearchBusy(true)
                    try {
                      const ids = compareIds.split(",").map((item) => item.trim()).filter(Boolean)
                      if (bound?.research?.run_id && ids.length < 2) {
                        ids.unshift(bound.research.run_id)
                      }
                      setResearchCompare(await compareResearchRuns(ids))
                    } catch (err) {
                      setErrorMessage(err instanceof Error ? err.message : "对比失败")
                    } finally {
                      setResearchBusy(false)
                    }
                  }}
                >
                  对比
                </Button>
                {researchCompare ? (
                  <pre className="max-h-80 overflow-auto rounded-md border border-border bg-secondary/30 p-2 text-[11px]">
                    {JSON.stringify(researchCompare, null, 2)}
                  </pre>
                ) : null}
              </CardContent>
            </Card>
          </div>
        ) : null}

        {pane === "compliance" ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">程序合规</CardTitle>
              <CardDescription>本场听证步骤是否走完。仅 CI 有实时步骤。</CardDescription>
            </CardHeader>
            <CardContent>
              {!sessionId ? (
                <p className="text-sm text-muted-foreground">先绑定本场会话。</p>
              ) : complianceScenario && complianceScenario !== "CI" ? (
                <p className="text-sm text-muted-foreground">程序步骤追踪只适用于仲裁听证。</p>
              ) : (
                <ComplianceView data={compliance} />
              )}
            </CardContent>
          </Card>
        ) : null}
      </main>
    </WorkbenchShell>
  )
}

function ComplianceView({ data }: { data: unknown }) {
  if (!data || typeof data !== "object") {
    return <p className="text-sm text-muted-foreground">暂无合规快照</p>
  }
  const record = data as Record<string, unknown>
  if (typeof record.error === "string") {
    return <p className="text-sm text-destructive">{record.error}</p>
  }
  if (typeof record.message === "string") {
    return <p className="text-sm text-muted-foreground">{record.message}</p>
  }

  const stages = (record.stages as Record<string, { actions?: Array<{ label?: string; completed?: boolean }> }>) || {}
  const entries = Object.entries(stages)
  if (!entries.length) {
    return <p className="text-sm text-muted-foreground">暂无合规快照</p>
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {entries.map(([stage, section]) => (
        <div key={stage} className="rounded-md border border-border px-3 py-2">
          <div className="mb-2 text-[13px] font-medium">{STAGE_LABELS[stage] || stage}</div>
          <ul className="space-y-1">
            {(section.actions || []).map((action, index) => (
              <li key={`${stage}-${index}`} className="flex items-center justify-between text-[12px]">
                <span>{remapComplianceLabel(action.label || "")}</span>
                <span className={action.completed ? "text-success" : "text-muted-foreground"}>
                  {action.completed ? "完成" : "未完成"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

export default function EvaluationPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">加载复盘...</div>}>
      <EvaluationInner />
    </Suspense>
  )
}
