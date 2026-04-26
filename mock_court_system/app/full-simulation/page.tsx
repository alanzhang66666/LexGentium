"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import {
  Swords,
  Play,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FileText,
  Scale,
  Gavel,
  Trophy,
  ArrowRight,
  Sparkles,
} from "lucide-react"

const DEFAULT_CASE = JSON.stringify(
  {
    case_id: "demo_001",
    case_description:
      "2023年3月，张三向李四借款人民币50000元，约定年利率为8%，借期一年。到期后李四多次催要，张三以各种理由拒不偿还本金及利息。李四现要求张三偿还借款本金50000元及利息4000元。",
    plaintiff_name: "李四",
    defendant_name: "张三",
    plaintiff_claims: [
      "判令被告偿还借款本金50000元",
      "判令被告支付利息4000元",
      "诉讼费用由被告承担",
    ],
  },
  null,
  2,
)

type TaskStatus = "idle" | "pending" | "running" | "completed" | "failed"

interface StageResult {
  scenario: string
  dialog_history: Array<{ turn: number; role: string; message: string }>
  final_document: string
  metadata: Record<string, unknown>
}

interface LawArticle {
  law: string
  content: string
  applied_to?: string
}

interface StructuredJudgment {
  facts: Array<{ content: string; source?: string }>
  dispute_points: string[]
  legal_articles: LawArticle[]
  liability_mapping: { plaintiff_claims: string[]; court_adoption: string[] }
  conclusion: string
  mediation_result?: { outcome: string } | null
}

interface ComplianceSection {
  score: number
  details: Array<{ step: string; passed: boolean }> | Record<string, unknown>
}

interface MultiLayerEvaluation {
  composite_score: number
  result_quality: Record<string, number | null>
  process_compliance: {
    opening: ComplianceSection
    investigation: ComplianceSection
    debate: ComplianceSection
    mediation: ComplianceSection
    stage_order_correct: boolean
    overall: number
  }
  legality_ethics: {
    legality_score: number
    risks: Array<{ type: string; severity: string; description: string }>
    risk_count: number
  }
}

interface SimulationResult {
  case_id: string
  cd_result?: StageResult
  dd_result?: StageResult
  ci_result?: StageResult
  judgment_score?: Record<string, unknown>
  structured_judgment?: StructuredJudgment
  compliance_report?: Record<string, unknown>
  multi_layer_evaluation?: MultiLayerEvaluation
  elapsed_seconds?: number
}

interface TournamentRound {
  round_index: number
  score: {
    plaintiff_win_rate: number
    defendant_win_rate: number
    reasoning_quality: number
    evidence_strength: number
    details?: { analysis?: string }
  }
  elapsed_seconds: number
  case_result: SimulationResult
}

interface TournamentResult {
  case_id: string
  total_rounds: number
  rounds: TournamentRound[]
  elapsed_seconds: number
}

function StageCard({
  title,
  icon,
  result,
  active,
}: {
  title: string
  icon: React.ReactNode
  result?: StageResult
  active: boolean
}) {
  if (!result) {
    return (
      <Card className={`border-2 ${active ? "border-primary animate-pulse" : "border-dashed opacity-50"}`}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {icon}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {active ? "进行中..." : "等待中"}
          </p>
        </CardContent>
      </Card>
    )
  }

  const turns = result.dialog_history?.length ?? 0
  const docPreview = result.final_document?.substring(0, 300) ?? ""

  return (
    <Card className="border-2 border-green-300 dark:border-green-700">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <CheckCircle2 className="w-4 h-4 text-green-600" />
          {title}
        </CardTitle>
        <CardDescription>{turns} 条对话</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="bg-muted rounded-lg p-3 max-h-48 overflow-y-auto">
          <pre className="text-xs whitespace-pre-wrap">{docPreview}{docPreview.length >= 300 ? "..." : ""}</pre>
        </div>
      </CardContent>
    </Card>
  )
}

export default function FullSimulationPage() {
  const [caseJson, setCaseJson] = useState(DEFAULT_CASE)
  const [mode, setMode] = useState<"single" | "tournament">("single")
  const [rounds, setRounds] = useState(3)
  const [status, setStatus] = useState<TaskStatus>("idle")
  const [taskId, setTaskId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [result, setResult] = useState<SimulationResult | TournamentResult | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => () => stopPolling(), [stopPolling])

  const pollStatus = useCallback(
    async (tid: string) => {
      try {
        const res = await fetch(`/api/case/full-simulation/${tid}`)
        if (!res.ok) return
        const data = await res.json()
        setCurrentStage(data.current_stage)
        if (data.status === "completed") {
          setStatus("completed")
          setResult(data.result)
          stopPolling()
        } else if (data.status === "failed") {
          setStatus("failed")
          setError(data.message || "任务失败")
          stopPolling()
        }
      } catch {
        /* ignore transient polling errors */
      }
    },
    [stopPolling],
  )

  const handleStart = async () => {
    setError(null)
    setResult(null)
    setCurrentStage(null)

    let caseInfo: Record<string, unknown>
    try {
      caseInfo = JSON.parse(caseJson)
    } catch {
      setError("案件 JSON 格式错误")
      return
    }

    setStatus("pending")

    try {
      const res = await fetch("/api/case/full-simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case_info: caseInfo,
          mode,
          tournament_rounds: rounds,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setTaskId(data.task_id)
      setStatus("running")

      pollRef.current = setInterval(() => pollStatus(data.task_id), 3000)
    } catch (err) {
      setStatus("failed")
      setError(err instanceof Error ? err.message : "启动失败")
    }
  }

  const isTournament = result && "rounds" in result
  const singleResult = (!isTournament ? result : null) as SimulationResult | null
  const tournamentResult = (isTournament ? result : null) as TournamentResult | null

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="relative border-b bg-gradient-to-br from-background via-muted/30 to-background overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(120,119,198,0.1),transparent_50%)]" />
        <div className="container mx-auto px-4 md:px-8 py-12 md:py-16 relative">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 border border-primary/20 rounded-full mb-6 backdrop-blur-sm">
              <Sparkles className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold text-primary">三 Agent 博弈系统</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-4 text-balance bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
              全流程模拟 & 博弈对抗
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground leading-relaxed text-pretty">
              从起诉到判决，三个 Agent 自动完成完整案件流程，支持多轮博弈策略进化
            </p>
          </div>
        </div>
      </section>

      <ScrollIndicator />

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="max-w-5xl mx-auto space-y-6">
          {/* 配置区 */}
          <Card className="border-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-3">
                <Swords className="w-5 h-5" />
                案件配置
              </CardTitle>
              <CardDescription>输入案件信息，选择运行模式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>案件信息 (JSON)</Label>
                <Textarea
                  value={caseJson}
                  onChange={(e) => setCaseJson(e.target.value)}
                  rows={8}
                  className="font-mono text-sm"
                  disabled={status === "running" || status === "pending"}
                />
              </div>
              <div className="grid md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>运行模式</Label>
                  <Select value={mode} onValueChange={(v) => setMode(v as "single" | "tournament")}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="single">单轮完整模拟</SelectItem>
                      <SelectItem value="tournament">多轮博弈锦标赛</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {mode === "tournament" && (
                  <div className="space-y-2">
                    <Label>锦标赛轮数</Label>
                    <Select value={String(rounds)} onValueChange={(v) => setRounds(Number(v))}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[2, 3, 5].map((n) => (
                          <SelectItem key={n} value={String(n)}>
                            {n} 轮
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="space-y-2">
                  <Label>&nbsp;</Label>
                  <Button
                    onClick={handleStart}
                    disabled={status === "running" || status === "pending"}
                    className="w-full"
                  >
                    {status === "running" || status === "pending" ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        运行中...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4 mr-2" />
                        开始{mode === "tournament" ? "博弈锦标赛" : "全流程模拟"}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 错误提示 */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* 进行中状态 */}
          {(status === "running" || status === "pending") && (
            <Card className="border-2 border-primary/30">
              <CardContent className="p-6">
                <div className="flex items-center gap-4">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <div>
                    <p className="font-semibold">正在运行{mode === "tournament" ? "博弈锦标赛" : "全流程模拟"}...</p>
                    <p className="text-sm text-muted-foreground">
                      当前阶段: {currentStage || "初始化"}
                      {taskId && <span className="ml-2 opacity-50">ID: {taskId}</span>}
                    </p>
                  </div>
                </div>
                {/* 管道进度指示 */}
                <div className="flex items-center gap-2 mt-6">
                  {["CD", "DD", "CI"].map((stage, idx) => (
                    <div key={stage} className="flex items-center gap-2">
                      <div
                        className={`flex items-center justify-center w-10 h-10 rounded-full border-2 text-sm font-bold ${
                          currentStage === stage
                            ? "border-primary bg-primary text-primary-foreground animate-pulse"
                            : currentStage &&
                                ["CD", "DD", "CI"].indexOf(currentStage) > idx
                              ? "border-green-500 bg-green-500 text-white"
                              : "border-muted-foreground/30 text-muted-foreground"
                        }`}
                      >
                        {stage}
                      </div>
                      {idx < 2 && (
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 单轮结果展示 */}
          {status === "completed" && singleResult && (
            <>
              <Alert className="border-green-500 bg-green-50 dark:bg-green-950/30">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800 dark:text-green-300">
                  全流程模拟完成！耗时 {singleResult.elapsed_seconds}s
                </AlertDescription>
              </Alert>

              <div className="grid md:grid-cols-3 gap-4">
                <StageCard
                  title="起诉状 (CD)"
                  icon={<FileText className="w-4 h-4 text-blue-500" />}
                  result={singleResult.cd_result}
                  active={false}
                />
                <StageCard
                  title="答辩状 (DD)"
                  icon={<Scale className="w-4 h-4 text-purple-500" />}
                  result={singleResult.dd_result}
                  active={false}
                />
                <StageCard
                  title="判决书 (CI)"
                  icon={<Gavel className="w-4 h-4 text-amber-500" />}
                  result={singleResult.ci_result}
                  active={false}
                />
              </div>

              {singleResult.judgment_score && (
                <Card className="border-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Trophy className="w-5 h-5 text-amber-500" />
                      博弈评分
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <ScoreItem label="原告胜率" value={singleResult.judgment_score.plaintiff_win_rate as number} />
                      <ScoreItem label="被告胜率" value={singleResult.judgment_score.defendant_win_rate as number} />
                      <ScoreItem label="论证质量" value={singleResult.judgment_score.reasoning_quality as number} />
                      <ScoreItem label="证据强度" value={singleResult.judgment_score.evidence_strength as number} />
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 结构化判决 */}
              {singleResult.structured_judgment && (
                <Card className="border-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Gavel className="w-5 h-5 text-amber-500" />
                      结构化判决分析
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {singleResult.structured_judgment.dispute_points.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold mb-2">争议焦点</h4>
                        <ul className="space-y-1">
                          {singleResult.structured_judgment.dispute_points.map((dp, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm">
                              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 text-xs font-bold shrink-0 mt-0.5">{i + 1}</span>
                              {dp}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {singleResult.structured_judgment.legal_articles.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold mb-2">适用法条</h4>
                        <div className="space-y-2">
                          {singleResult.structured_judgment.legal_articles.map((la, i) => (
                            <div key={i} className="p-2 bg-muted rounded text-sm">
                              <span className="font-medium">{la.law}</span>
                              <span className="text-muted-foreground ml-2">{la.content}</span>
                              {la.applied_to && (
                                <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">({la.applied_to})</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {singleResult.structured_judgment.liability_mapping?.plaintiff_claims?.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold mb-2">诉请裁判对照</h4>
                        <div className="border rounded-lg overflow-hidden">
                          <table className="w-full text-sm">
                            <thead className="bg-muted">
                              <tr>
                                <th className="text-left p-2 font-medium">诉讼请求</th>
                                <th className="text-left p-2 font-medium">裁判结果</th>
                              </tr>
                            </thead>
                            <tbody>
                              {singleResult.structured_judgment.liability_mapping.plaintiff_claims.map((claim, i) => (
                                <tr key={i} className="border-t">
                                  <td className="p-2">{claim}</td>
                                  <td className="p-2 text-muted-foreground">
                                    {singleResult.structured_judgment!.liability_mapping.court_adoption[i] || "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    {singleResult.structured_judgment.mediation_result && (
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-medium">调解结果：</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          singleResult.structured_judgment.mediation_result.outcome === "mediation_agreed"
                            ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
                            : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                        }`}>
                          {singleResult.structured_judgment.mediation_result.outcome === "mediation_agreed" ? "双方同意调解" : "调解未成"}
                        </span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* 多层评测 */}
              {singleResult.multi_layer_evaluation && (
                <Card className="border-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-purple-500" />
                      多维评测
                      <span className="ml-auto text-2xl font-bold">
                        {Math.round(singleResult.multi_layer_evaluation.composite_score * 100)}分
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-3 gap-4">
                      <div className="p-3 border rounded-lg">
                        <div className="text-xs text-muted-foreground mb-1">结果质量</div>
                        <div className="text-lg font-bold">
                          {Math.round((singleResult.multi_layer_evaluation.result_quality.overall ?? 0) * 100)}%
                        </div>
                      </div>
                      <div className="p-3 border rounded-lg">
                        <div className="text-xs text-muted-foreground mb-1">过程合规</div>
                        <div className="text-lg font-bold">
                          {Math.round(singleResult.multi_layer_evaluation.process_compliance.overall * 100)}%
                        </div>
                      </div>
                      <div className="p-3 border rounded-lg">
                        <div className="text-xs text-muted-foreground mb-1">合法性</div>
                        <div className="text-lg font-bold">
                          {Math.round(singleResult.multi_layer_evaluation.legality_ethics.legality_score * 100)}%
                        </div>
                        {singleResult.multi_layer_evaluation.legality_ethics.risk_count > 0 && (
                          <div className="text-xs text-red-500 mt-1">
                            {singleResult.multi_layer_evaluation.legality_ethics.risk_count} 项风险
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* 锦标赛结果展示 */}
          {status === "completed" && tournamentResult && (
            <>
              <Alert className="border-green-500 bg-green-50 dark:bg-green-950/30">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800 dark:text-green-300">
                  博弈锦标赛完成！{tournamentResult.total_rounds} 轮，总耗时 {tournamentResult.elapsed_seconds}s
                </AlertDescription>
              </Alert>

              <Card className="border-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-amber-500" />
                    各轮得分趋势
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {tournamentResult.rounds.map((round) => (
                      <div key={round.round_index} className="border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-3">
                          <span className="font-semibold">第 {round.round_index + 1} 轮</span>
                          <span className="text-sm text-muted-foreground">{round.elapsed_seconds}s</span>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <ScoreItem label="原告胜率" value={round.score.plaintiff_win_rate} />
                          <ScoreItem label="被告胜率" value={round.score.defendant_win_rate} />
                          <ScoreItem label="论证质量" value={round.score.reasoning_quality} />
                          <ScoreItem label="证据强度" value={round.score.evidence_strength} />
                        </div>
                        {round.score.details?.analysis && (
                          <p className="mt-3 text-sm text-muted-foreground border-t pt-2">
                            {round.score.details.analysis}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </section>

      <Footer />
    </div>
  )
}

function ScoreItem({ label, value }: { label: string; value: number }) {
  const pct = Math.round((value ?? 0) * 100)
  return (
    <div className="text-center">
      <div className="text-2xl font-bold">{pct}%</div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="w-full bg-muted rounded-full h-1.5 mt-1">
        <div
          className="bg-primary h-1.5 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
