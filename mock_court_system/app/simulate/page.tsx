"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { StatusBadge } from "@/components/status-badge"
import { JsonEditor } from "@/components/json-editor"
import { MetricCard } from "@/components/metric-card"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import { FileJson, AlertCircle, CheckCircle2, Send, Activity, Clock, Zap, Sparkles, ArrowRightLeft } from "lucide-react"
import type { Scenario, SimulateRequest, DialogEntry } from "@/lib/types"

const DEFAULT_DIALOG_HISTORY = `[{"turn":0,"role":"Client","message":"你好"}]`

const SCENARIO_OPTIONS = [
  { value: "CD" as const, label: "起诉状生成", description: "Civil Complaint", color: "from-blue-500 to-cyan-500" },
  { value: "DD" as const, label: "答辩状生成", description: "Defense Statement", color: "from-purple-500 to-pink-500" },
  {
    value: "CI" as const,
    label: "法庭判决",
    description: "Court Judgment",
    color: "from-green-500 to-emerald-500",
  },
] as const

export default function SimulatePage() {
  const router = useRouter()
  const [selectedScenario, setSelectedScenario] = useState<Scenario>("CD")
  const [caseIdentifier, setCaseIdentifier] = useState("test_001")
  const [dialogHistoryJson, setDialogHistoryJson] = useState(DEFAULT_DIALOG_HISTORY)
  const [additionalInputJson, setAdditionalInputJson] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [simulationResult, setSimulationResult] = useState<unknown | null>(null)
  const [requestTime, setRequestTime] = useState<number | null>(null)
  const [isImporting, setIsImporting] = useState(false)

  const generateRequestPreview = (): string => {
    try {
      const parsedHistory: DialogEntry[] = JSON.parse(dialogHistoryJson)
      const requestPayload: SimulateRequest = {
        scenario: selectedScenario,
        case_id: caseIdentifier,
        dialog_history: parsedHistory,
      }

      if (additionalInputJson.trim()) {
        requestPayload.input_json = JSON.parse(additionalInputJson)
      }

      return JSON.stringify(requestPayload, null, 2)
    } catch {
      return "无法生成预览：JSON 解析失败"
    }
  }

  const getCurrentStatus = (): "ready" | "loading" | "error" | "success" => {
    if (isLoading) return "loading"
    if (errorMessage) return "error"
    if (simulationResult) return "success"
    return "ready"
  }

  const handleSimulateRequest = async (): Promise<void> => {
    setErrorMessage(null)
    setSimulationResult(null)
    setRequestTime(null)

    let parsedDialogHistory: DialogEntry[]
    try {
      parsedDialogHistory = JSON.parse(dialogHistoryJson)
      if (!Array.isArray(parsedDialogHistory)) {
        setErrorMessage("dialog_history 必须是 JSON 数组")
        return
      }

      for (const dialogEntry of parsedDialogHistory) {
        if (!dialogEntry.role || !dialogEntry.message) {
          setErrorMessage("dialog_history 数组元素必须包含 role 和 message 字段")
          return
        }
      }
    } catch (error) {
      setErrorMessage(`dialog_history JSON 解析失败: ${error instanceof Error ? error.message : String(error)}`)
      return
    }

    let parsedAdditionalInput: Record<string, unknown> | undefined
    if (additionalInputJson.trim()) {
      try {
        parsedAdditionalInput = JSON.parse(additionalInputJson)
        if (typeof parsedAdditionalInput !== "object" || Array.isArray(parsedAdditionalInput)) {
          setErrorMessage("input_json 必须是 JSON 对象（非数组）")
          return
        }
      } catch (error) {
        setErrorMessage(`input_json JSON 解析失败: ${error instanceof Error ? error.message : String(error)}`)
        return
      }
    }

    const requestPayload: SimulateRequest = {
      scenario: selectedScenario,
      case_id: caseIdentifier,
      dialog_history: parsedDialogHistory,
    }

    if (parsedAdditionalInput) {
      requestPayload.input_json = parsedAdditionalInput
    }

    setIsLoading(true)
    const startTime = Date.now()

    try {
      const response = await fetch("/api/simulate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestPayload),
      })

      const endTime = Date.now()
      setRequestTime(endTime - startTime)

      const responseText = await response.text()

      if (!response.ok) {
        try {
          const errorJson: unknown = JSON.parse(responseText)
          setErrorMessage(`HTTP ${response.status}: ${JSON.stringify(errorJson, null, 2)}`)
        } catch {
          setErrorMessage(`HTTP ${response.status}: ${responseText}`)
        }
        return
      }

      try {
        const resultJson: unknown = JSON.parse(responseText)
        setSimulationResult(resultJson)
      } catch {
        setSimulationResult(responseText)
      }
    } catch (error) {
      setErrorMessage(`网络请求失败: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleImportToConversation = async () => {
    setErrorMessage(null)

    let parsedDialogHistory: DialogEntry[]
    try {
      parsedDialogHistory = JSON.parse(dialogHistoryJson)
      if (!Array.isArray(parsedDialogHistory)) {
        setErrorMessage("dialog_history 必须是 JSON 数组")
        return
      }
    } catch (error) {
      setErrorMessage(`dialog_history JSON 解析失败: ${error instanceof Error ? error.message : String(error)}`)
      return
    }

    let parsedAdditionalInput: Record<string, unknown> | undefined
    if (additionalInputJson.trim()) {
      try {
        parsedAdditionalInput = JSON.parse(additionalInputJson)
        if (typeof parsedAdditionalInput !== "object" || Array.isArray(parsedAdditionalInput)) {
          setErrorMessage("input_json 必须是 JSON 对象（非数组）")
          return
        }
      } catch (error) {
        setErrorMessage(`input_json JSON 解析失败: ${error instanceof Error ? error.message : String(error)}`)
        return
      }
    }

    setIsImporting(true)
    try {
      const response = await fetch("/api/conversation/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario: selectedScenario,
          case_id: caseIdentifier,
          dialog_history: parsedDialogHistory,
          input_json: parsedAdditionalInput,
        }),
      })

      const text = await response.text()
      let data: any = null
      try {
        data = JSON.parse(text)
      } catch {
        // ignore
      }

      if (!response.ok) {
        setErrorMessage(data?.detail ? String(data.detail) : `HTTP ${response.status}: ${text}`)
        return
      }

      router.push(`/conversation/${data.session_id}`)
    } catch (error) {
      setErrorMessage(`导入失败: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setIsImporting(false)
    }
  }

  const currentStatus = getCurrentStatus()
  const selectedScenarioOption = SCENARIO_OPTIONS.find((opt) => opt.value === selectedScenario)

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
              <span className="text-sm font-semibold text-primary">模拟器</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-4 text-balance bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
              场景模拟
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground leading-relaxed text-pretty">
              配置模拟参数并提交请求，系统将生成起诉状、答辩状与裁判结果，并提供可解释的过程记录
            </p>
          </div>
        </div>
      </section>

      <ScrollIndicator />

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <MetricCard
            icon={Activity}
            label="系统状态"
            value={
              currentStatus === "ready"
                ? "就绪"
                : currentStatus === "loading"
                  ? "处理中"
                  : currentStatus === "error"
                    ? "错误"
                    : "完成"
            }
            trend={currentStatus === "success" ? "up" : currentStatus === "error" ? "down" : "neutral"}
          />
          <MetricCard icon={Clock} label="响应时间" value={requestTime ? `${requestTime}ms` : "--"} trend="neutral" />
          <MetricCard icon={Zap} label="当前场景" value={selectedScenarioOption?.label || "--"} trend="neutral" />
        </div>

        <div className="grid lg:grid-cols-2 gap-6 md:gap-8">
          <div className="space-y-6">
            <Card className="border-2 shadow-2xl hover:shadow-3xl transition-all duration-300 overflow-hidden backdrop-blur-sm bg-card/95">
              <div className={`h-2 bg-gradient-to-r ${selectedScenarioOption?.color}`} />
              <CardHeader className="space-y-2 pb-4 bg-gradient-to-br from-muted/30 to-transparent">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-2xl md:text-3xl font-bold flex items-center gap-3">
                      <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10 border border-primary/20">
                        <Sparkles className="w-5 h-5 text-primary" />
                      </div>
                      参数配置
                    </CardTitle>
                    <CardDescription className="text-sm md:text-base">设置模拟场景的核心参数</CardDescription>
                  </div>
                  <StatusBadge status={currentStatus}>
                    {isLoading && "处理中"}
                    {!isLoading && !errorMessage && !simulationResult && "就绪"}
                    {errorMessage && "错误"}
                    {!!simulationResult && "完成"}
                  </StatusBadge>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2.5">
                  <Label htmlFor="scenario" className="text-sm font-semibold flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                    场景类型
                  </Label>
                  <Select value={selectedScenario} onValueChange={(value) => setSelectedScenario(value as Scenario)}>
                    <SelectTrigger
                      id="scenario"
                      className="h-11 border-2 hover:border-primary/50 focus:border-primary transition-colors"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SCENARIO_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value} className="py-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-2.5 h-2.5 rounded-full bg-gradient-to-br ${option.color}`} />
                            <div className="flex flex-col">
                              <span className="font-semibold text-sm">{option.label}</span>
                              <span className="text-xs text-muted-foreground">{option.description}</span>
                            </div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2.5">
                  <Label htmlFor="case_id" className="text-sm font-semibold flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                    案件标识符
                  </Label>
                  <Input
                    id="case_id"
                    value={caseIdentifier}
                    onChange={(e) => setCaseIdentifier(e.target.value)}
                    placeholder="test_001"
                    className="h-11 font-mono text-sm border-2 hover:border-primary/50 focus:border-primary transition-colors"
                  />
                </div>

                <JsonEditor
                  label="对话历史"
                  value={dialogHistoryJson}
                  onChange={setDialogHistoryJson}
                  placeholder={DEFAULT_DIALOG_HISTORY}
                  rows={8}
                  required
                  helpText="JSON 数组格式，每项必须包含 role 和 message 字段"
                />

                <JsonEditor
                  label="额外输入参数"
                  value={additionalInputJson}
                  onChange={setAdditionalInputJson}
                  placeholder='{"key": "value"}'
                  rows={4}
                  helpText="JSON 对象格式，用于传递额外的配置参数"
                />

                <Button
                  onClick={handleSimulateRequest}
                  disabled={isLoading}
                  className="w-full h-14 text-base md:text-lg font-bold shadow-2xl hover:shadow-3xl transition-all duration-300 group bg-gradient-to-r from-primary to-primary/90 hover:from-primary/90 hover:to-primary relative overflow-hidden"
                  size="lg"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-white/0 via-white/20 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
                  {isLoading ? (
                    <>
                      <div className="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin mr-2" />
                      正在处理请求...
                    </>
                  ) : (
                    <>
                      <Send className="w-5 h-5 mr-2 group-hover:translate-x-1 transition-transform" />
                      发送模拟请求
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleImportToConversation}
                  disabled={isLoading || isImporting}
                  className="w-full h-12 font-semibold border-2"
                >
                  {isImporting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-muted-foreground/30 border-t-muted-foreground rounded-full animate-spin mr-2" />
                      正在导入到会话...
                    </>
                  ) : (
                    <>
                      <ArrowRightLeft className="w-4 h-4 mr-2" />
                      导入为会话并打开
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card className="border-2 shadow-lg transition-all duration-300 overflow-hidden backdrop-blur-sm bg-card/95">
              <div className="h-1 bg-gradient-to-r from-muted-foreground/30 to-muted-foreground/10" />
              <CardHeader className="space-y-1 pb-4">
                <CardTitle className="text-xl font-bold flex items-center gap-2">
                  <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-muted">
                    <FileJson className="w-4 h-4 text-muted-foreground" />
                  </div>
                  请求预览
                </CardTitle>
                <CardDescription className="text-sm">实时生成的 API 请求负载</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="relative">
                  <pre className="bg-muted/60 p-4 rounded-xl overflow-x-auto text-xs font-mono border-2 leading-relaxed max-h-[420px] hover:bg-muted/80 transition-colors">
                    {generateRequestPreview()}
                  </pre>
                </div>
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
                    <div className="font-bold mb-2 text-base">请求处理失败</div>
                    <pre className="text-xs overflow-x-auto whitespace-pre-wrap font-mono mt-2 bg-destructive/10 p-4 rounded-xl leading-relaxed border border-destructive/20">
                      {errorMessage}
                    </pre>
                  </AlertDescription>
                </div>
              </Alert>
            )}

            {!!simulationResult && (
              <Card className="border-2 border-accent/40 bg-accent/10 shadow-xl shadow-accent/20 animate-in fade-in slide-in-from-bottom-4 duration-500 overflow-hidden backdrop-blur-sm">
                <div className="h-2 bg-gradient-to-r from-accent via-accent/80 to-accent animate-pulse" />
                <CardHeader className="space-y-2 pb-4 bg-gradient-to-br from-accent/10 to-transparent">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-accent/20 shadow-lg border border-accent/30">
                      <CheckCircle2 className="w-6 h-6 text-accent" />
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-xl md:text-2xl font-bold text-accent-foreground">执行成功</CardTitle>
                      <CardDescription className="text-sm flex items-center gap-2">
                        系统响应数据
                        {requestTime && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-accent/20 rounded-full text-xs font-bold text-accent border border-accent/30">
                            <Clock className="w-3 h-3" />
                            {requestTime}ms
                          </span>
                        )}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="bg-card p-5 rounded-xl overflow-x-auto text-xs font-mono border-2 border-accent/30 leading-relaxed max-h-[500px] shadow-inner">
                    {typeof simulationResult === "object"
                      ? JSON.stringify(simulationResult, null, 2)
                      : String(simulationResult)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
