"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { StatusBadge } from "@/components/status-badge"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import {
  FileJson,
  AlertCircle,
  CheckCircle2,
  Play,
  Activity,
  Clock,
  BarChart3,
  RefreshCw,
  Download,
  Sparkles,
} from "lucide-react"
import { useRouter } from "next/navigation"
import type { EvaluationRequest, EvaluationResponse, EvaluationReportsList } from "@/lib/evaluation-types"

const SCENARIO_OPTIONS = [
  { value: "CD", label: "起诉状生成", description: "Civil Complaint", color: "from-blue-500 to-cyan-500" },
  { value: "DD", label: "答辩状生成", description: "Defense Statement", color: "from-purple-500 to-pink-500" },
  { value: "CI", label: "法庭判决", description: "Court Judgment", color: "from-green-500 to-emerald-500" },
] as const

export default function EvaluationPage() {
  const router = useRouter()
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>(["CD", "DD", "CI"])
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [evaluationResult, setEvaluationResult] = useState<EvaluationResponse | null>(null)
  const [polling, setPolling] = useState(false)
  const [reportsList, setReportsList] = useState<EvaluationReportsList | null>(null)

  // 加载评测报告列表
  useEffect(() => {
    loadReportsList()
  }, [])

  // 轮询评测状态
  useEffect(() => {
    if (polling && evaluationResult?.report_id) {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(`/api/evaluate?report_id=${evaluationResult.report_id}`)
          if (response.ok) {
            const data: EvaluationResponse = await response.json()
            setEvaluationResult(data)
            if (data.status === "completed" || data.status === "failed") {
              setPolling(false)
              loadReportsList()
            }
          }
        } catch (error) {
          console.error("轮询评测状态失败:", error)
        }
      }, 2000) // 每2秒轮询一次

      return () => clearInterval(interval)
    }
  }, [polling, evaluationResult?.report_id])

  const loadReportsList = async () => {
    try {
      const response = await fetch("/api/evaluate")
      if (response.ok) {
        const data: EvaluationReportsList = await response.json()
        setReportsList(data)
      }
    } catch (error) {
      console.error("加载评测报告列表失败:", error)
    }
  }

  const handleScenarioToggle = (scenario: string) => {
    setSelectedScenarios((prev) =>
      prev.includes(scenario) ? prev.filter((s) => s !== scenario) : [...prev, scenario],
    )
  }

  const handleStartEvaluation = async () => {
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
        use_default_predictions: true,
      }

      const response = await fetch("/api/evaluate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      })

      const responseText = await response.text()

      if (!response.ok) {
        try {
          const errorJson = JSON.parse(responseText)
          setErrorMessage(`HTTP ${response.status}: ${JSON.stringify(errorJson, null, 2)}`)
        } catch {
          setErrorMessage(`HTTP ${response.status}: ${responseText}`)
        }
        return
      }

      try {
        const result: EvaluationResponse = JSON.parse(responseText)
        setEvaluationResult(result)
        if (result.status === "running") {
          setPolling(true)
        }
      } catch {
        setErrorMessage("响应解析失败")
      }
    } catch (error) {
      setErrorMessage(`网络请求失败: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setIsLoading(false)
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

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="relative border-b bg-gradient-to-br from-background via-muted/30 to-background overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(120,119,198,0.1),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_80%,rgba(74,222,128,0.08),transparent_50%)]" />
        <div className="container mx-auto px-4 md:px-8 py-12 md:py-16 relative">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 border border-primary/20 rounded-full mb-6 backdrop-blur-sm">
              <Sparkles className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold text-primary">评测与对比</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-4 text-balance bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
              评测中心
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground leading-relaxed text-pretty">
              对系统生成的起诉状、答辩状和法庭判决进行质量评测，基于标准答案集计算评测指标
            </p>
          </div>
        </div>
      </section>

      <ScrollIndicator />

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="grid lg:grid-cols-2 gap-6 md:gap-8">
          <div className="space-y-6">
            <Card className="border-2 shadow-2xl hover:shadow-3xl transition-all duration-300 overflow-hidden backdrop-blur-sm bg-card/95">
              <div className="h-2 bg-gradient-to-r from-primary via-primary/80 to-primary" />
              <CardHeader className="space-y-2 pb-4 bg-gradient-to-br from-muted/30 to-transparent">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-2xl md:text-3xl font-bold flex items-center gap-3">
                      <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10 border border-primary/20">
                        <BarChart3 className="w-5 h-5 text-primary" />
                      </div>
                      评测配置
                    </CardTitle>
                    <CardDescription className="text-sm md:text-base">选择要评测的场景类型</CardDescription>
                  </div>
                  {evaluationResult && (
                    <StatusBadge status={getStatusColor(evaluationResult.status)}>
                      {evaluationResult.status === "running" && "运行中"}
                      {evaluationResult.status === "completed" && "已完成"}
                      {evaluationResult.status === "failed" && "失败"}
                    </StatusBadge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <Label className="text-sm font-semibold flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    选择评测场景
                  </Label>
                  <div className="grid grid-cols-1 gap-3">
                    {SCENARIO_OPTIONS.map((option) => (
                      <div
                        key={option.value}
                        className={`flex items-center space-x-3 p-4 rounded-lg border-2 transition-all cursor-pointer ${
                          selectedScenarios.includes(option.value)
                            ? "border-primary bg-primary/5"
                            : "border-border hover:border-primary/50"
                        }`}
                        onClick={() => handleScenarioToggle(option.value)}
                      >
                        <Checkbox
                          checked={selectedScenarios.includes(option.value)}
                          onCheckedChange={() => handleScenarioToggle(option.value)}
                        />
                        <div className="flex-1">
                          <div className="flex items-center gap-3">
                            <div className={`w-2.5 h-2.5 rounded-full bg-gradient-to-br ${option.color}`} />
                            <span className="font-semibold text-sm">{option.label}</span>
                          </div>
                          <span className="text-xs text-muted-foreground">{option.description}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <Button
                  onClick={handleStartEvaluation}
                  disabled={isLoading || selectedScenarios.length === 0}
                  className="w-full h-14 text-base md:text-lg font-bold shadow-2xl hover:shadow-3xl transition-all duration-300 group bg-gradient-to-r from-primary to-primary/90 hover:from-primary/90 hover:to-primary relative overflow-hidden"
                  size="lg"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
                  {isLoading ? (
                    <>
                      <div className="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin mr-2" />
                      正在启动评测...
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 mr-2 group-hover:translate-x-1 transition-transform" />
                      开始评测
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {errorMessage && (
              <Alert
                variant="destructive"
                className="border-2 shadow-xl animate-in fade-in slide-in-from-top-4 duration-500 backdrop-blur-sm bg-destructive/5"
              >
                <div className="flex items-start gap-3">
                  <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-destructive/20 border border-destructive/30 shrink-0">
                    <AlertCircle className="h-5 w-5 text-destructive" />
                  </div>
                  <AlertDescription className="flex-1">
                    <div className="font-bold mb-2 text-base">评测失败</div>
                    <pre className="text-xs overflow-x-auto whitespace-pre-wrap font-mono mt-2 bg-destructive/10 p-4 rounded-xl leading-relaxed border border-destructive/20">
                      {errorMessage}
                    </pre>
                  </AlertDescription>
                </div>
              </Alert>
            )}

            {evaluationResult && (
              <Card className="border-2 border-accent/40 bg-accent/10 shadow-xl shadow-accent/20 animate-in fade-in slide-in-from-bottom-4 duration-500 overflow-hidden backdrop-blur-sm">
                <div className="h-2 bg-gradient-to-r from-accent via-accent/80 to-accent animate-pulse" />
                <CardHeader className="space-y-2 pb-4 bg-gradient-to-br from-accent/10 to-transparent">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-accent/20 shadow-lg border border-accent/30">
                      {evaluationResult.status === "completed" ? (
                        <CheckCircle2 className="w-6 h-6 text-accent" />
                      ) : evaluationResult.status === "running" ? (
                        <Activity className="w-6 h-6 text-accent animate-pulse" />
                      ) : (
                        <AlertCircle className="w-6 h-6 text-destructive" />
                      )}
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-xl md:text-2xl font-bold text-accent-foreground">
                        {evaluationResult.status === "completed"
                          ? "评测完成"
                          : evaluationResult.status === "running"
                            ? "评测进行中"
                            : "评测失败"}
                      </CardTitle>
                      <CardDescription className="text-sm flex items-center gap-2">
                        {evaluationResult.message}
                        {evaluationResult.report_id && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-accent/20 rounded-full text-xs font-bold text-accent border border-accent/30">
                            <FileJson className="w-3 h-3" />
                            {evaluationResult.report_id}
                          </span>
                        )}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                {evaluationResult.results && (
                  <CardContent>
                    <div className="space-y-4">
                      <div className="text-sm font-semibold">评测结果摘要</div>
                      <pre className="bg-card p-5 rounded-xl overflow-x-auto text-xs font-mono border-2 border-accent/30 leading-relaxed max-h-[400px] shadow-inner">
                        {JSON.stringify(evaluationResult.results, null, 2)}
                      </pre>
                    </div>
                  </CardContent>
                )}
              </Card>
            )}
          </div>

          <div className="space-y-6">
            <Card className="border-2 shadow-lg transition-all duration-300 overflow-hidden backdrop-blur-sm bg-card/95">
              <div className="h-1 bg-gradient-to-r from-muted-foreground/30 to-muted-foreground/10" />
              <CardHeader className="space-y-1 pb-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xl font-bold flex items-center gap-2">
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-muted">
                      <Clock className="w-4 h-4 text-muted-foreground" />
                    </div>
                    评测历史
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={loadReportsList}
                    className="h-8 w-8 p-0"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </Button>
                </div>
                <CardDescription className="text-sm">最近的评测报告</CardDescription>
              </CardHeader>
              <CardContent>
                {reportsList && reportsList.reports.length > 0 ? (
                  <div className="space-y-2">
                    {reportsList.reports.slice(0, 10).map((report) => (
                      <div
                        key={report.report_id}
                        className="flex items-center justify-between p-3 rounded-lg border border-border hover:border-primary/50 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">{report.file_name}</div>
                          <div className="text-xs text-muted-foreground">
                            {report.scenarios.join(", ")} • {report.created_at}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => router.push(`/evaluation/reports/${report.report_id}`)}
                        >
                          <FileJson className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground text-center py-8">
                    暂无评测报告
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}

