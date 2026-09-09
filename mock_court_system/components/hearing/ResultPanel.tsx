"use client"

import { CheckCircle2, FileText, Gavel, Scale, Trophy } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export interface StageResult {
  scenario: string
  dialog_history: Array<{ turn?: number; role: string; message: string }>
  final_document: string
  metadata: Record<string, unknown>
}

export interface SimulationResult {
  case_id: string
  cd_result?: StageResult
  dd_result?: StageResult
  ci_result?: StageResult
  judgment_score?: Record<string, unknown>
  structured_judgment?: {
    facts: Array<{ content: string; source?: string }>
    dispute_points: string[]
    legal_articles: Array<{ law: string; content: string; applied_to?: string }>
    liability_mapping: { plaintiff_claims: string[]; court_adoption: string[] }
    conclusion: string
    mediation_result?: { outcome: string } | null
  }
  multi_layer_evaluation?: {
    composite_score: number
    result_quality: Record<string, number | null>
    process_compliance: { overall: number }
    legality_ethics: { legality_score: number; risk_count: number }
  }
  elapsed_seconds?: number
}

export interface TournamentResult {
  case_id: string
  total_rounds: number
  rounds: Array<{
    round_index: number
    score: {
      plaintiff_win_rate: number
      defendant_win_rate: number
      reasoning_quality: number
      evidence_strength: number
      details?: { analysis?: string }
      degraded?: boolean
    }
    elapsed_seconds: number
  }>
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
      <Card className={active ? "border-primary" : "border-dashed opacity-50"}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {icon}
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{active ? "进行中..." : "等待中"}</p>
        </CardContent>
      </Card>
    )
  }
  const turns = result.dialog_history?.length ?? 0
  const docPreview = result.final_document?.substring(0, 300) ?? ""
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <CheckCircle2 className="size-4 text-success" />
          {title}
        </CardTitle>
        <CardDescription>{turns} 条对话</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="bg-muted rounded-lg p-3 max-h-48 overflow-y-auto">
          <pre className="text-xs whitespace-pre-wrap">
            {docPreview}
            {docPreview.length >= 300 ? "..." : ""}
          </pre>
        </div>
      </CardContent>
    </Card>
  )
}

function ScoreItem({ label, value }: { label: string; value: number }) {
  const pct = Math.round((value ?? 0) * 100)
  return (
    <div className="text-center">
      <div className="text-2xl font-bold">{pct}%</div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="w-full bg-muted rounded-full h-1.5 mt-1">
        <div className="bg-primary h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function ResultPanel({
  result,
}: {
  result: SimulationResult | TournamentResult
}) {
  const isTournament = "rounds" in result
  const singleResult = (!isTournament ? result : null) as SimulationResult | null
  const tournamentResult = (isTournament ? result : null) as TournamentResult | null

  return (
    <>
      {singleResult ? (
        <>
          <Alert>
            <CheckCircle2 className="h-4 w-4 text-success" />
            <AlertDescription>全案完成，耗时 {singleResult.elapsed_seconds}s</AlertDescription>
          </Alert>
          <div className="grid md:grid-cols-3 gap-4">
            <StageCard title="申请准备" icon={<FileText className="size-4 text-muted-foreground" />} result={singleResult.cd_result} active={false} />
            <StageCard title="答辩准备" icon={<Scale className="size-4 text-muted-foreground" />} result={singleResult.dd_result} active={false} />
            <StageCard title="裁决" icon={<Gavel className="size-4 text-muted-foreground" />} result={singleResult.ci_result} active={false} />
          </div>
          {singleResult.judgment_score ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Trophy className="size-4 text-warning" />
                  博弈评分
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {singleResult.judgment_score.degraded ? (
                  <Alert>
                    <AlertDescription>
                      当前未配置 LLM 或评分失败，以下分值为降级占位，不是真实评测。
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <ScoreItem label="申请人胜率" value={singleResult.judgment_score.plaintiff_win_rate as number} />
                    <ScoreItem label="被申请人胜率" value={singleResult.judgment_score.defendant_win_rate as number} />
                    <ScoreItem label="论证质量" value={singleResult.judgment_score.reasoning_quality as number} />
                    <ScoreItem label="证据强度" value={singleResult.judgment_score.evidence_strength as number} />
                  </div>
                )}
              </CardContent>
            </Card>
          ) : null}
          {singleResult.structured_judgment ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Gavel className="size-4 text-muted-foreground" />
                  结构化裁决分析
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {singleResult.structured_judgment.dispute_points.length > 0 ? (
                  <div>
                    <h4 className="text-sm font-semibold mb-2">争议焦点</h4>
                    <ul className="space-y-1">
                      {singleResult.structured_judgment.dispute_points.map((dp, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <span className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-full border border-border font-mono text-[11px] tabular-nums">
                            {i + 1}
                          </span>
                          {dp}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}
          {singleResult.multi_layer_evaluation ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  多维对照
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
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}

      {tournamentResult ? (
        <>
          <Alert>
            <CheckCircle2 className="h-4 w-4 text-success" />
            <AlertDescription>
              博弈锦标赛完成。{tournamentResult.total_rounds} 轮，总耗时 {tournamentResult.elapsed_seconds}s
            </AlertDescription>
          </Alert>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="size-4 text-warning" />
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
                    {round.score.degraded ? (
                      <p className="text-sm text-warning">本轮评分降级（离线占位，非真实 LLM 结果）</p>
                    ) : (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <ScoreItem label="申请人胜率" value={round.score.plaintiff_win_rate} />
                        <ScoreItem label="被申请人胜率" value={round.score.defendant_win_rate} />
                        <ScoreItem label="论证质量" value={round.score.reasoning_quality} />
                        <ScoreItem label="证据强度" value={round.score.evidence_strength} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      ) : null}
    </>
  )
}
