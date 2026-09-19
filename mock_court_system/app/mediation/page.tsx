"use client"

import { useState } from "react"
import { WorkbenchShell } from "@/components/shell"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Checkbox } from "@/components/ui/checkbox"
import { AlertCircle } from "lucide-react"
import { IdentityChips } from "@/components/journey/identity"
import { JourneyError } from "@/components/journey/states"
import { ApiError } from "@/lib/api"
import {
  createMediation,
  getMediationStatus,
  runMediationBargain,
  runMediationClose,
  runMediationOptions,
  runMediationPreliminary,
  runMediationStatement,
} from "@/lib/api"

const DEFAULT_CASE = JSON.stringify(
  {
    case_id: "mediation_001",
    case_description:
      "申请人与被申请人就国际货物买卖合同项下货款与迟延交付发生争议，双方同意先行调解。",
    plaintiff_claims: ["支付剩余货款", "赔偿迟延损失"],
  },
  null,
  2,
)

const STAGES = [
  { id: "preliminary", label: "I 初步介绍" },
  { id: "statement", label: "II 陈述" },
  { id: "options", label: "III 方案" },
  { id: "bargain", label: "IV 协商" },
  { id: "close", label: "V 结案" },
] as const

function formatError(error: unknown) {
  if (error instanceof ApiError) {
    return [error.message, error.detail, error.suggestion].filter(Boolean).join("\n")
  }
  return error instanceof Error ? error.message : String(error)
}

export default function MediationPage() {
  const [caseJson, setCaseJson] = useState(DEFAULT_CASE)
  const [partyA, setPartyA] = useState("申请人")
  const [partyB, setPartyB] = useState("被申请人")
  const [maxRounds, setMaxRounds] = useState(5)
  const [autoNbs, setAutoNbs] = useState(false)
  const [sessionId, setSessionId] = useState("")
  const [statementParty, setStatementParty] = useState("申请人")
  const [statement, setStatement] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [last, setLast] = useState<Record<string, unknown> | null>(null)
  const [lastAction, setLastAction] = useState<(() => void) | null>(null)

  const partyNames = [partyA.trim(), partyB.trim()].filter(Boolean)

  const parseCase = () => {
    const parsed = JSON.parse(caseJson) as Record<string, unknown>
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("案件信息必须是 JSON 对象")
    }
    return parsed
  }

  const createBody = () => ({
    case_info: parseCase(),
    party_names: partyNames.length >= 2 ? partyNames : ["申请人", "被申请人"],
    max_bargaining_rounds: maxRounds,
    auto_compute_nbs: autoNbs,
  })

  const run = async (fn: () => Promise<Record<string, unknown>>) => {
    setBusy(true)
    setError(null)
    try {
      const result = await fn()
      setLast(result)
      const sid = sessionId || (typeof result.session_id === "string" ? result.session_id : "")
      if (sid) {
        try {
          setStatus(await getMediationStatus(sid))
        } catch {
          /* status is optional after a stage call */
        }
      }
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const handleCreate = () => {
    setLastAction(() => handleCreate)
    return run(async () => {
      const result = await createMediation(createBody())
      if (typeof result.session_id === "string") {
        setSessionId(result.session_id)
        setStatementParty(partyA.trim() || "申请人")
      }
      return result
    })
  }

  const handleStage = (id: (typeof STAGES)[number]["id"]) => {
    if (!sessionId) {
      setError("请先创建调解会话")
      return
    }
    setLastAction(() => () => handleStage(id))
    if (id === "preliminary") return run(() => runMediationPreliminary(sessionId))
    if (id === "statement") {
      return run(() =>
        runMediationStatement(sessionId, {
          party_name: statementParty || partyA,
          statement: statement.trim() || undefined,
        }),
      )
    }
    if (id === "options") return run(() => runMediationOptions(sessionId))
    if (id === "bargain") return run(() => runMediationBargain(sessionId))
    return run(() => runMediationClose(sessionId))
  }

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6">
          <h1 className="text-[22px] font-medium tracking-tight">独立调解</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            五阶段 HDR 工作台。庭内听证和解仍走开庭会话，本页不改 CD/DD/CI 主环。
          </p>
        </div>

        <JourneyError
          error={error}
          fallback="调解操作失败"
          onRetry={lastAction ? () => lastAction() : undefined}
          busy={busy}
          className="mb-4"
        />
        {error && /404|不存在|重启/.test(formatError(error)) ? (
          <Alert className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              调解场在后端重启后可能丢失。请重新点「创建调解」；若刚重启且存档未写入，旧 session_id 会 404。
            </AlertDescription>
          </Alert>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">创建会话</CardTitle>
              <CardDescription>先建场，再按阶段推进。后端离线时只显示错误，页面不崩。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>一方</Label>
                  <Input value={partyA} onChange={(e) => setPartyA(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label>另一方</Label>
                  <Input value={partyB} onChange={(e) => setPartyB(e.target.value)} />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>最大协商轮次</Label>
                <Input
                  type="number"
                  min={1}
                  max={12}
                  value={maxRounds}
                  onChange={(e) => setMaxRounds(Number(e.target.value) || 5)}
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={autoNbs} onCheckedChange={(v) => setAutoNbs(Boolean(v))} />
                自动计算 NBS 参考点
              </label>
              <div className="space-y-1.5">
                <Label>案件 JSON</Label>
                <Textarea value={caseJson} onChange={(e) => setCaseJson(e.target.value)} rows={10} className="font-mono text-xs" />
              </div>
              <Button onClick={handleCreate} disabled={busy}>
                {busy ? "处理中…" : "创建调解"}
              </Button>
              <IdentityChips items={[{ label: "med_session", value: sessionId }]} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">五阶段</CardTitle>
              <CardDescription>按 HDR 顺序点一次。陈述可指定一方与可选书面意见。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {STAGES.map((stage) => (
                  <Button
                    key={stage.id}
                    variant="outline"
                    size="sm"
                    disabled={busy || !sessionId}
                    onClick={() => handleStage(stage.id)}
                  >
                    {stage.label}
                  </Button>
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>陈述方</Label>
                  <Input value={statementParty} onChange={(e) => setStatementParty(e.target.value)} />
                </div>
                <div className="space-y-1.5 sm:col-span-2">
                  <Label>陈述（可空，由模型代写）</Label>
                  <Textarea value={statement} onChange={(e) => setStatement(e.target.value)} rows={3} />
                </div>
              </div>
              {status ? (
                <pre className="max-h-40 overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
                  {JSON.stringify(status, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground">创建后这里显示阶段状态。</p>
              )}
            </CardContent>
          </Card>
        </div>

        {last ? (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-base">最近一次结果</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[480px] overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
                {JSON.stringify(last, null, 2)}
              </pre>
            </CardContent>
          </Card>
        ) : null}
      </main>
    </WorkbenchShell>
  )
}
