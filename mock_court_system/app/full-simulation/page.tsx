"use client"

import { Suspense, useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { WorkbenchShell } from "@/components/shell"
import { IdentityChips } from "@/components/journey/identity"
import { JourneyError, JourneyTerminal } from "@/components/journey/states"
import { ResultPanel, type SimulationResult, type TournamentResult } from "@/components/hearing/ResultPanel"
import { ArrowRight, Box, Loader2, Play, Swords } from "lucide-react"
import { getFullSimulation, listConversations, startFullSimulation } from "@/lib/api"
import type { ConversationSummary } from "@/lib/conversation-types"

const DEFAULT_CASE = JSON.stringify(
  {
    case_id: "demo_001",
    case_description:
      "2023年3月，张三向李四借款人民币50000元，约定年利率为8%，借期一年。到期后李四多次催要，张三以各种理由拒不偿还本金及利息。李四现要求张三偿还借款本金50000元及利息4000元。",
    plaintiff_name: "李四",
    defendant_name: "张三",
    plaintiff_claims: ["判令被告偿还借款本金50000元", "判令被告支付利息4000元", "诉讼费用由被告承担"],
  },
  null,
  2,
)

type TaskStatus = "idle" | "pending" | "running" | "completed" | "failed"

function FullSimulationInner() {
  const search = useSearchParams()
  const [caseJson, setCaseJson] = useState(DEFAULT_CASE)
  const [mode, setMode] = useState<"single" | "tournament">("single")
  const [rounds, setRounds] = useState(3)
  const [status, setStatus] = useState<TaskStatus>("idle")
  const [taskId, setTaskId] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [result, setResult] = useState<SimulationResult | TournamentResult | null>(null)
  const [sessionId, setSessionId] = useState(search.get("session") || "")
  const [sessions, setSessions] = useState<ConversationSummary[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    listConversations(50)
      .then((data) => setSessions(data.sessions || []))
      .catch(() => setSessions([]))
  }, [])

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
        const data = await getFullSimulation(tid)
        setCurrentStage(data.current_stage ?? null)
        if (data.status === "completed") {
          setStatus("completed")
          setResult((data.result || null) as SimulationResult | TournamentResult | null)
          stopPolling()
        } else if (data.status === "failed") {
          setStatus("failed")
          setError(new Error(data.message || "任务失败"))
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
      const data = await startFullSimulation({
        case_info: caseInfo,
        mode,
        tournament_rounds: rounds,
        session_id: sessionId || undefined,
      })
      setTaskId(data.task_id)
      setStatus("running")
      pollRef.current = setInterval(() => void pollStatus(data.task_id), 3000)
    } catch (err) {
      setStatus("failed")
      setError(err instanceof Error ? err : new Error("启动失败"))
    }
  }

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">全案</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            绑定 session 后回写 links.task_id，完成后可去观庭。
          </p>
        </div>
        <div className="mx-auto max-w-5xl space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-3">
                <Swords className="w-5 h-5" />
                案件与会话
              </CardTitle>
              <CardDescription>选择已有开庭会话以写入 links</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>绑定会话</Label>
                <Select value={sessionId || "__none__"} onValueChange={(v) => setSessionId(v === "__none__" ? "" : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="不绑定（不推荐）" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">不绑定会话</SelectItem>
                    {sessions.map((s) => (
                      <SelectItem key={s.session_id} value={s.session_id}>
                        {s.scenario} · {s.case_id} · {s.session_id.slice(0, 8)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
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
                {mode === "tournament" ? (
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
                ) : null}
                <div className="space-y-2">
                  <Label>&nbsp;</Label>
                  <Button onClick={handleStart} disabled={status === "running" || status === "pending"} className="w-full">
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

          <JourneyError
            error={error}
            fallback="全案任务失败"
            onRetry={() => void handleStart()}
            busy={status === "running" || status === "pending"}
          />

          <IdentityChips
            items={[
              { label: "session_id", value: sessionId },
              { label: "task_id", value: taskId },
            ]}
          />

          {status === "completed" ? (
            <JourneyTerminal
              title="全案任务已完成"
              identity={[
                { label: "session_id", value: sessionId },
                { label: "task_id", value: taskId },
              ]}
            />
          ) : null}

          {(status === "running" || status === "pending") && (
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center gap-4">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <div>
                    <p className="font-semibold">正在运行…</p>
                    <p className="text-sm text-muted-foreground">
                      当前阶段: {currentStage || "初始化"}
                      {taskId ? <span className="ml-2 opacity-50">ID: {taskId}</span> : null}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-6">
                  {["CD", "DD", "CI"].map((stage, idx) => (
                    <div key={stage} className="flex items-center gap-2">
                      <div
                        className={`flex items-center justify-center w-10 h-10 rounded-full border-2 text-sm font-bold ${
                          currentStage === stage
                            ? "border-primary bg-primary text-primary-foreground animate-pulse"
                            : currentStage && ["CD", "DD", "CI"].indexOf(currentStage) > idx
                              ? "border-green-500 bg-green-500 text-white"
                              : "border-muted-foreground/30 text-muted-foreground"
                        }`}
                      >
                        {stage}
                      </div>
                      {idx < 2 ? <ArrowRight className="w-4 h-4 text-muted-foreground" /> : null}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {status === "completed" && sessionId ? (
            <Button asChild>
              <Link href={`/hearing-3d?sessionId=${encodeURIComponent(sessionId)}`}>
                <Box className="w-4 h-4 mr-2" />
                去观庭
              </Link>
            </Button>
          ) : null}

          {status === "completed" && result ? <ResultPanel result={result} /> : null}
        </div>
      </main>
    </WorkbenchShell>
  )
}

export default function FullSimulationPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">加载全案页…</div>}>
      <FullSimulationInner />
    </Suspense>
  )
}
