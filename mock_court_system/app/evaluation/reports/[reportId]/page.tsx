"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WorkbenchShell } from "@/components/shell"
import { evaluationMetrics, evaluationScenarios, evaluationScore } from "@/lib/evaluation-metrics"
import { SCENARIO_LABELS } from "@/lib/labels"
import { ApiError, getEvaluationReport, getEvaluationStatus } from "@/lib/api"
import {
  FileJson,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  Download,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react"

export default function EvaluationReportPage() {
  const params = useParams()
  const router = useRouter()
  const reportId = params.reportId as string

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reportData, setReportData] = useState<any>(null)
  const [provenance, setProvenance] = useState<any>(null)
  const [correlation, setCorrelation] = useState<any>(null)

  useEffect(() => {
    loadReport()
  }, [reportId])

  const loadReport = async () => {
    setLoading(true)
    setError(null)

    try {
      const statusData = await getEvaluationStatus(reportId)
      setProvenance(statusData.provenance || null)
      setCorrelation(statusData.correlation || null)
      if (statusData.results) {
        setReportData(statusData.results)
        return
      }
      const data = await getEvaluationReport(reportId)
      if (!provenance) {
        setProvenance(data.provenance || null)
        setCorrelation(data.correlation || null)
      }
      setReportData(data.results || data)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail || err.message || "无法加载评测报告")
      } else {
        setError(err instanceof Error ? err.message : "加载评测报告失败")
      }
    } finally {
      setLoading(false)
    }
  }

  const calculateMetrics = evaluationMetrics
  const formatScore = (score: unknown): string => {
    const value = evaluationScore(score)
    return value === null ? "N/A" : value.toFixed(2)
  }

  const getScoreTrend = (score: number): "up" | "down" | "neutral" => {
    if (score >= 0.8) return "up"
    if (score >= 0.5) return "neutral"
    return "down"
  }

  if (loading) {
    return (
      <WorkbenchShell>
        <div className="flex flex-1 items-center justify-center py-16">
          <p className="text-sm text-muted-foreground">加载报告…</p>
        </div>
      </WorkbenchShell>
    )
  }

  if (error) {
    return (
      <WorkbenchShell>
        <div className="px-4 py-8">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button onClick={() => router.push("/evaluation")} className="mt-4" variant="outline">
            <ArrowLeft className="size-3.5" />
            返回复盘
          </Button>
        </div>
      </WorkbenchShell>
    )
  }

  if (!reportData) {
    return (
      <WorkbenchShell>
        <div className="px-4 py-8">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>报告数据为空</AlertDescription>
          </Alert>
          <Button onClick={() => router.push("/evaluation")} className="mt-4" variant="outline">
            <ArrowLeft className="size-3.5" />
            返回复盘
          </Button>
        </div>
      </WorkbenchShell>
    )
  }

  const scenarios = evaluationScenarios(reportData)
  const scenarioMetrics = scenarios.reduce((acc, scenario) => {
    acc[scenario] = calculateMetrics(reportData[scenario])
    return acc
  }, {} as Record<string, any>)

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <Button variant="ghost" size="sm" onClick={() => router.push("/evaluation")} className="mb-2">
              <ArrowLeft className="size-3.5" />
              返回复盘
            </Button>
            <h1 className="text-[22px] font-medium tracking-tight">报告</h1>
            <p className="mt-1 font-mono text-xs text-muted-foreground">{reportId}</p>
          </div>
          <Button variant="outline" size="sm">
            <Download className="size-3.5" />
            导出
          </Button>
        </div>
        <p className="mb-4 text-sm text-muted-foreground">民事文书分数仅表示结构关键词覆盖，不代表法律正确性或证据充分性。研究参考对照没有质量分数，请使用研究量表。</p>

        {provenance ? (
          <Card className="mb-6">
            <CardContent className="flex flex-wrap gap-x-6 gap-y-1 py-3 text-[12px] text-muted-foreground">
              <span>
                namespace <span className="font-mono text-foreground">{provenance.namespace}</span>
              </span>
              <span>
                rubric <span className="font-mono text-foreground">{provenance.rubric_version}</span>
              </span>
              <span>
                provenance <span className="font-mono text-foreground">{provenance.provenance_id}</span>
              </span>
              {correlation?.session_id ? (
                <span>
                  session <span className="font-mono text-foreground">{correlation.session_id}</span>
                </span>
              ) : null}
              {correlation?.run_id ? (
                <span>
                  run <span className="font-mono text-foreground">{correlation.run_id}</span>
                </span>
              ) : null}
              {provenance.degraded ? (
                <span className="text-amber-600 dark:text-amber-500">
                  降级输入
                  {provenance.affected_metrics?.length
                    ? ` · 受影响: ${provenance.affected_metrics.join(", ")}`
                    : ""}
                </span>
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        {/* 总体统计 */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          {scenarios.map((scenario) => {
            const metrics = scenarioMetrics[scenario]
            const scenarioNames = SCENARIO_LABELS
            const trend = getScoreTrend(metrics.average)

            return (
              <Card key={scenario}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span>{scenarioNames[scenario] || scenario}</span>
                    {trend === "up" ? (
                      <TrendingUp className="w-5 h-5 text-green-500" />
                    ) : trend === "down" ? (
                      <TrendingDown className="w-5 h-5 text-red-500" />
                    ) : (
                      <Minus className="w-5 h-5 text-yellow-500" />
                    )}
                  </CardTitle>
                  <CardDescription>场景: {scenario}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">平均分</span>
                      <span className="text-2xl font-bold">{metrics.total ? metrics.average.toFixed(2) : "N/A"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">评测数量</span>
                      <span className="font-semibold">{metrics.total}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">最高分</span>
                      <span className="font-semibold">{metrics.total ? metrics.max.toFixed(2) : "N/A"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">最低分</span>
                      <span className="font-semibold">{metrics.total ? metrics.min.toFixed(2) : "N/A"}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* 详细结果 */}
        <div className="space-y-6">
          {scenarios.map((scenario) => {
            const scenarioData = reportData[scenario]
            if (!scenarioData || !Array.isArray(scenarioData)) {
              return null
            }

            return (
              <Card key={scenario}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5" />
                    {SCENARIO_LABELS[scenario] || scenario} 明细
                  </CardTitle>
                  <CardDescription>共 {scenarioData.length} 条评测记录</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {scenarioData.map((item: any, index: number) => (
                      <div
                        key={index}
                        className="p-4 border rounded-lg hover:bg-muted/50 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold">
                            案例 {item.case_id || `#${index + 1}`}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            得分: {formatScore(item.score)}
                          </span>
                        </div>
                        {typeof item.score === "object" && item.score !== null && (
                          <div className="mt-2 space-y-1">
                            {Object.entries(item.score).map(([key, value]) => (
                              <div key={key} className="flex justify-between text-sm">
                                <span className="text-muted-foreground">{key}:</span>
                                <span className="font-mono">
                                  {typeof value === "number" ? value.toFixed(2) : String(value)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>

        {/* 多层评测汇总 */}
        {reportData.multi_layer_evaluation && (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                多维对照（结果 + 过程 + 合法性）
              </CardTitle>
              <CardDescription>
                综合得分：{Math.round((reportData.multi_layer_evaluation.composite_score ?? 0) * 100)} 分
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* 三层得分概览 */}
              <div className="grid md:grid-cols-3 gap-4">
                <div className="p-4 border rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">结果质量</div>
                  <div className="text-3xl font-bold">
                    {Math.round((reportData.multi_layer_evaluation.result_quality?.overall ?? 0) * 100)}%
                  </div>
                  <div className="w-full bg-muted rounded-full h-2 mt-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${Math.round((reportData.multi_layer_evaluation.result_quality?.overall ?? 0) * 100)}%` }} />
                  </div>
                </div>
                <div className="p-4 border rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">过程合规</div>
                  <div className="text-3xl font-bold">
                    {Math.round((reportData.multi_layer_evaluation.process_compliance?.overall ?? 0) * 100)}%
                  </div>
                  <div className="w-full bg-muted rounded-full h-2 mt-2">
                    <div className="bg-green-500 h-2 rounded-full" style={{ width: `${Math.round((reportData.multi_layer_evaluation.process_compliance?.overall ?? 0) * 100)}%` }} />
                  </div>
                </div>
                <div className="p-4 border rounded-lg">
                  <div className="text-sm text-muted-foreground mb-1">合法性与伦理</div>
                  <div className="text-3xl font-bold">
                    {Math.round((reportData.multi_layer_evaluation.legality_ethics?.legality_score ?? 0) * 100)}%
                  </div>
                  <div className="w-full bg-muted rounded-full h-2 mt-2">
                    <div className="bg-amber-500 h-2 rounded-full" style={{ width: `${Math.round((reportData.multi_layer_evaluation.legality_ethics?.legality_score ?? 0) * 100)}%` }} />
                  </div>
                  {reportData.multi_layer_evaluation.legality_ethics?.risk_count > 0 && (
                    <div className="mt-2 space-y-1">
                      {reportData.multi_layer_evaluation.legality_ethics.risks?.map((risk: any, i: number) => (
                        <div key={i} className={`text-xs px-2 py-1 rounded ${
                          risk.severity === "high" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
                          : "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300"
                        }`}>
                          {risk.description}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* 过程合规明细 */}
              {reportData.multi_layer_evaluation.process_compliance && (
                <div>
                  <h4 className="text-sm font-semibold mb-3">过程合规明细</h4>
                  <div className="grid md:grid-cols-4 gap-3">
                    {["opening", "investigation", "debate", "mediation"].map((section) => {
                      const sectionData = reportData.multi_layer_evaluation.process_compliance[section]
                      if (!sectionData) return null
                      const sectionLabels: Record<string, string> = {
                        opening: "开庭",
                        investigation: "调查",
                        debate: "辩论",
                        mediation: "调解",
                      }
                      return (
                        <div key={section} className="p-3 border rounded-lg">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium">{sectionLabels[section]}</span>
                            <span className="text-sm font-bold">{Math.round(sectionData.score * 100)}%</span>
                          </div>
                          {Array.isArray(sectionData.details) && (
                            <div className="space-y-1">
                              {sectionData.details.map((item: any, i: number) => (
                                <div key={i} className="flex items-center gap-2 text-xs">
                                  <div className={`w-2 h-2 rounded-full ${item.passed ? "bg-green-500" : "bg-red-400"}`} />
                                  <span className={item.passed ? "" : "text-muted-foreground"}>{item.step}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                  {reportData.multi_layer_evaluation.process_compliance.stage_order_correct !== undefined && (
                    <div className="mt-2 text-xs flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${reportData.multi_layer_evaluation.process_compliance.stage_order_correct ? "bg-green-500" : "bg-red-400"}`} />
                      阶段顺序{reportData.multi_layer_evaluation.process_compliance.stage_order_correct ? "正确" : "有误"}
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* 原始数据 */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileJson className="size-4" />
              原始数据
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[600px] overflow-auto rounded-lg bg-muted p-4 font-mono text-xs">
              {JSON.stringify(reportData, null, 2)}
            </pre>
          </CardContent>
        </Card>
      </main>
    </WorkbenchShell>
  )
}

