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
import { WorkbenchShell } from "@/components/shell"
import { ExperimentBadge } from "@/components/journey/experiment-badge"
import { FileJson, AlertCircle, CheckCircle2, Send, Activity, Clock, Zap, ArrowRightLeft, Loader2 } from "lucide-react"
import { SCENARIO_DESCRIPTIONS, SCENARIO_LABELS } from "@/lib/labels"
import { ApiError, importConversation, runSimulate } from "@/lib/api"
import { writeLastSessionId } from "@/lib/session/last-session"
import type { Scenario, SimulateRequest, DialogEntry } from "@/lib/types"

const DEFAULT_DIALOG_HISTORY = `[{"turn":0,"role":"Client","message":"你好"}]`

const SCENARIO_OPTIONS = [
  { value: "CD" as const, label: SCENARIO_LABELS.CD, description: SCENARIO_DESCRIPTIONS.CD },
  { value: "DD" as const, label: SCENARIO_LABELS.DD, description: SCENARIO_DESCRIPTIONS.DD },
  { value: "CI" as const, label: SCENARIO_LABELS.CI, description: SCENARIO_DESCRIPTIONS.CI },
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
      const resultJson = await runSimulate(requestPayload)
      setRequestTime(Date.now() - startTime)
      setSimulationResult(resultJson)
    } catch (error) {
      setRequestTime(Date.now() - startTime)
      if (error instanceof ApiError) {
        setErrorMessage(
          [error.message, error.detail, error.suggestion].filter(Boolean).join("\n"),
        )
      } else {
        setErrorMessage(`网络请求失败: ${error instanceof Error ? error.message : String(error)}`)
      }
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
      const data = await importConversation({
        scenario: selectedScenario,
        case_id: caseIdentifier,
        dialog_history: parsedDialogHistory,
        input_json: parsedAdditionalInput,
      })
      writeLastSessionId(data.session_id)
      router.push(`/conversation/${data.session_id}`)
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage([error.message, error.detail].filter(Boolean).join("\n"))
      } else {
        setErrorMessage(`导入失败: ${error instanceof Error ? error.message : String(error)}`)
      }
    } finally {
      setIsImporting(false)
    }
  }

  const currentStatus = getCurrentStatus()
  const selectedScenarioOption = SCENARIO_OPTIONS.find((opt) => opt.value === selectedScenario)

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="flex items-center gap-2 text-[22px] font-medium tracking-tight">
            调试模拟器
            <ExperimentBadge />
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">实验接口，无状态单轮。正式听证请走开庭。</p>
        </div>
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
            <Card>
              <CardHeader className="space-y-2 pb-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-base">参数配置</CardTitle>
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
                  <Label htmlFor="scenario" className="text-sm font-medium">
                    场景类型
                  </Label>
                  <Select value={selectedScenario} onValueChange={(value) => setSelectedScenario(value as Scenario)}>
                    <SelectTrigger
                      id="scenario"
                      className="h-11"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {SCENARIO_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value} className="py-3">
                          <div className="flex items-center gap-3">
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
                  <Label htmlFor="case_id" className="text-sm font-medium">
                    案件标识符
                  </Label>
                  <Input
                    id="case_id"
                    value={caseIdentifier}
                    onChange={(e) => setCaseIdentifier(e.target.value)}
                    placeholder="test_001"
                    className="h-11 font-mono text-sm"
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
                  className="w-full"
                  size="lg"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      正在处理请求...
                    </>
                  ) : (
                    <>
                      <Send className="size-4" />
                      发送模拟请求
                    </>
                  )}
                </Button>

                <Button
                  variant="outline"
                  onClick={handleImportToConversation}
                  disabled={isLoading || isImporting}
                  className="w-full"
                >
                  {isImporting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      正在导入到会话...
                    </>
                  ) : (
                    <>
                      <ArrowRightLeft className="size-4" />
                      导入为会话并打开
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader className="space-y-1 pb-4">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileJson className="size-4 text-muted-foreground" />
                  请求预览
                </CardTitle>
                <CardDescription className="text-sm">实时生成的 API 请求负载</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="max-h-[420px] overflow-x-auto rounded-lg border border-border bg-muted/40 p-4 font-mono text-xs leading-relaxed">
                  {generateRequestPreview()}
                </pre>
              </CardContent>
            </Card>

            {errorMessage && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <div className="mb-2 text-sm font-medium">请求处理失败</div>
                  <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs leading-relaxed">
                    {errorMessage}
                  </pre>
                </AlertDescription>
              </Alert>
            )}

            {!!simulationResult && (
              <Card>
                <CardHeader className="space-y-2 pb-4">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="size-4 text-success" />
                    <div className="flex-1">
                      <CardTitle className="text-base">执行成功</CardTitle>
                      <CardDescription className="flex items-center gap-2 text-sm">
                        系统响应数据
                        {requestTime ? (
                          <span className="inline-flex items-center gap-1 text-xs tabular-nums text-muted-foreground">
                            <Clock className="size-3" />
                            {requestTime}ms
                          </span>
                        ) : null}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <pre className="max-h-[500px] overflow-x-auto rounded-lg border border-border bg-muted/40 p-4 font-mono text-xs leading-relaxed">
                    {typeof simulationResult === "object"
                      ? JSON.stringify(simulationResult, null, 2)
                      : String(simulationResult)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </WorkbenchShell>
  )
}
