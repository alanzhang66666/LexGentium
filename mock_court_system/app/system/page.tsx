"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { WorkbenchShell } from "@/components/shell"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ExternalLink, RefreshCw } from "lucide-react"
import { ExperimentBadge } from "@/components/journey/experiment-badge"
import { JourneyError } from "@/components/journey/states"
import { PUBLIC_BACKEND_URL } from "@/lib/public-backend-url"
import {
  getBigFiveTraits,
  getDisputeCauses,
  getHealth,
  getProgressiveBenchmark,
  runDualModeReasoning,
  runMultiJudge,
  runProgressiveRag,
} from "@/lib/api"

interface HealthPayload {
  status?: string
  time?: string
  paths?: Record<string, unknown>
  error?: string
  detail?: string
  suggestion?: string
  law_retriever_ready?: boolean
}

const MAPPINGS: {
  tier: "官方" | "半官方" | "实验"
  backend: string
  desc: string
  frontendPage: { href: string; label: string }
  nextApi: string
}[] = [
  { tier: "官方", backend: "GET /health", desc: "健康检查（含 law_retriever_ready）", frontendPage: { href: "/system", label: "系统" }, nextApi: "GET /api/health" },
  { tier: "官方", backend: "POST /config/llm/test", desc: "登录测通已有 LLM 配置，可选 API_TOKEN", frontendPage: { href: "/login", label: "登录" }, nextApi: "POST /api/config/llm/test" },
  { tier: "官方", backend: "POST /config/llm", desc: "开通首次写入供应商与密钥", frontendPage: { href: "/register", label: "开通" }, nextApi: "POST /api/config/llm" },
  { tier: "官方", backend: "POST /conversation/start", desc: "创建会话", frontendPage: { href: "/conversation", label: "开庭" }, nextApi: "POST /api/conversation/start" },
  { tier: "官方", backend: "GET /conversation/list", desc: "会话列表（含 links）", frontendPage: { href: "/conversation", label: "开庭" }, nextApi: "GET /api/conversation/list" },
  { tier: "官方", backend: "GET /conversation/{id}", desc: "会话详情展开 links", frontendPage: { href: "/conversation", label: "开庭 / 观庭" }, nextApi: "GET /api/conversation/[sessionId]" },
  { tier: "官方", backend: "POST /conversation/{id}/message/stream", desc: "SSE 发言", frontendPage: { href: "/conversation", label: "开庭会话" }, nextApi: "POST /api/conversation/.../message/stream" },
  { tier: "官方", backend: "POST /conversation/{id}/auto-advance", desc: "自动推进", frontendPage: { href: "/conversation", label: "开庭会话" }, nextApi: "POST /api/conversation/.../auto-advance" },
  { tier: "官方", backend: "POST /case/full-simulation", desc: "全案启动，可选 session_id 回写", frontendPage: { href: "/full-simulation", label: "全案" }, nextApi: "POST /api/case/full-simulation" },
  { tier: "官方", backend: "POST /evaluate", desc: "评测，可选 session_id", frontendPage: { href: "/evaluation", label: "复盘" }, nextApi: "POST /api/evaluate" },
  { tier: "官方", backend: "GET /reference/cases", desc: "1K 案件轻量索引", frontendPage: { href: "/conversation", label: "开庭选案" }, nextApi: "GET /api/reference/cases" },
  { tier: "半官方", backend: "GET /conversation/{id}/compliance", desc: "合规快照", frontendPage: { href: "/conversation", label: "开庭会话" }, nextApi: "GET /api/conversation/.../compliance" },
  { tier: "半官方", backend: "POST /game/create", desc: "博弈创建并回写 links.game_id", frontendPage: { href: "/evaluation?pane=strategy", label: "策略推演" }, nextApi: "POST /api/game/create" },
  { tier: "半官方", backend: "GET /game/list", desc: "博弈列表", frontendPage: { href: "/evaluation?pane=strategy", label: "策略推演" }, nextApi: "GET /api/game/list" },
  { tier: "实验", backend: "POST /", desc: "无状态单轮（系统菜单「调试单轮」）", frontendPage: { href: "/simulate", label: "调试模拟器" }, nextApi: "POST /api/simulate" },
  { tier: "半官方", backend: "POST /mediation/create", desc: "独立五阶段调解（庭内 CI 和解仍走会话）", frontendPage: { href: "/mediation", label: "独立调解" }, nextApi: "POST /api/mediation/create" },
  { tier: "半官方", backend: "POST /game/{id}/evaluate/* · GET /game/{id}/evaluate/polarization · GET /game/{id}/compliance/realtime · GET /game/{id}/strategy/payoff-matrix · GET /game/{id}/equilibrium · GET /game/{id}/equilibrium/convergence", desc: "博弈现场评测（有 game_id 时）", frontendPage: { href: "/evaluation?pane=strategy", label: "策略推演" }, nextApi: "POST|GET /api/game/.../evaluate/* · GET /api/game/.../compliance/realtime · GET /api/game/.../strategy/payoff-matrix · GET /api/game/.../equilibrium · GET /api/game/.../equilibrium/convergence" },
  { tier: "半官方", backend: "POST /game/{id}/strategy/set · POST /game/{id}/strategy/reflect · POST /game/{id}/round · GET /game/{id}/liability-chain · POST /game/{id}/liability-chain/counterfactual · DELETE /game/{id}", desc: "设定/反思策略、责任链、非流式一轮、删局（策略推演）", frontendPage: { href: "/evaluation?pane=strategy", label: "策略推演" }, nextApi: "POST /api/game/.../strategy/set · POST /api/game/.../strategy/reflect · POST /api/game/.../round · GET|POST /api/game/.../liability-chain* · DELETE /api/game/{id}" },
  { tier: "实验", backend: "POST /case/progressive-rag", desc: "创新：渐进检索（本页走 /case/*，不打 game 会话版）", frontendPage: { href: "/system", label: "系统实验" }, nextApi: "POST /api/case/progressive-rag" },
  { tier: "实验", backend: "POST /case/dual-mode-reasoning", desc: "创新：双模式推理（本页走 /case/*）", frontendPage: { href: "/system", label: "系统实验" }, nextApi: "POST /api/case/dual-mode-reasoning" },
  { tier: "实验", backend: "POST /case/multi-judge", desc: "创新：多法官（本页走 /case/*）", frontendPage: { href: "/system", label: "系统实验" }, nextApi: "POST /api/case/multi-judge" },
  { tier: "实验", backend: "POST /game/{id}/progressive-rag · POST /game/{id}/dual-mode-reasoning · POST /game/{id}/multi-judge", desc: "会话版创新（有 game_id；与本页 /case/* 实验面板分开）", frontendPage: { href: "/evaluation?pane=strategy", label: "策略推演" }, nextApi: "POST /api/game/.../progressive-rag · dual-mode-reasoning · multi-judge" },
  { tier: "实验", backend: "POST /conversation/{id}/message", desc: "非流式发言（调试；页面走 SSE stream）", frontendPage: { href: "/system", label: "调试" }, nextApi: "POST /api/conversation/.../message" },
  { tier: "官方", backend: "POST /database/search", desc: "法条检索", frontendPage: { href: "/database", label: "数据库" }, nextApi: "POST /api/database/search" },
  { tier: "官方", backend: "GET /api-history/list", desc: "API 调用列表", frontendPage: { href: "/api-history", label: "API 历史" }, nextApi: "GET /api/api-history/list" },
]

const SHORTCUTS = [
  { href: "/database", label: "法条检索" },
  { href: "/api-history", label: "调用记录" },
  { href: "/settings", label: "LLM 配置" },
  { href: "/simulate", label: "调试模拟器" },
  { href: "/mediation", label: "独立调解" },
]

export default function SystemPage() {
  const [health, setHealth] = useState<HealthPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)

  const [experimentKind, setExperimentKind] = useState<"progressive-rag" | "dual-mode" | "multi-judge">("progressive-rag")
  const [experimentBusy, setExperimentBusy] = useState(false)
  const [experimentError, setExperimentError] = useState<unknown>(null)
  const [lastExperiment, setLastExperiment] = useState<(() => void) | null>(null)
  const [experimentResult, setExperimentResult] = useState<unknown>(null)
  const [ragStage, setRagStage] = useState("investigation")
  const [ragContext, setRagContext] = useState(
    '{"query":"国际货物买卖迟延交付","plaintiff_claims":"支付剩余货款并赔偿迟延损失","defendant_defense":"货物不符约定"}',
  )
  const [dualCase, setDualCase] = useState("申请人主张货款未付，被申请人主张货物不符。")
  const [dualClaims, setDualClaims] = useState("支付剩余货款并赔偿迟延损失")
  const [judgeFacts, setJudgeFacts] = useState("合同已履行部分交货，尾款未付。")
  const [judgeClaims, setJudgeClaims] = useState("判令支付尾款")
  const [judgeCount, setJudgeCount] = useState(3)

  const loadHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = (await getHealth()) as HealthPayload
      setHealth(data)
    } catch (e) {
      setHealth(null)
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [])

  const runExperiment = async () => {
    setLastExperiment(() => () => void runExperiment())
    setExperimentBusy(true)
    setExperimentError(null)
    try {
      if (experimentKind === "progressive-rag") {
        const context = JSON.parse(ragContext) as Record<string, string>
        setExperimentResult(await runProgressiveRag({ stage: ragStage, context, top_k: 5 }))
      } else if (experimentKind === "dual-mode") {
        setExperimentResult(await runDualModeReasoning({ case_info: dualCase, claims: dualClaims }))
      } else {
        setExperimentResult(
          await runMultiJudge({
            case_facts: judgeFacts,
            claims: judgeClaims,
            num_judges: judgeCount,
          }),
        )
      }
    } catch (e) {
      setExperimentResult(null)
      setExperimentError(e instanceof SyntaxError ? new Error("context 必须是 JSON 对象") : e)
    } finally {
      setExperimentBusy(false)
    }
  }

  const loadReference = async (kind: "causes" | "bigfive" | "benchmark") => {
    setLastExperiment(() => () => void loadReference(kind))
    setExperimentBusy(true)
    setExperimentError(null)
    try {
      if (kind === "causes") setExperimentResult(await getDisputeCauses())
      else if (kind === "bigfive") setExperimentResult(await getBigFiveTraits())
      else setExperimentResult(await getProgressiveBenchmark())
    } catch (e) {
      setExperimentResult(null)
      setExperimentError(e)
    } finally {
      setExperimentBusy(false)
    }
  }

  useEffect(() => {
    void loadHealth()
  }, [loadHealth])

  const swaggerHref = `${PUBLIC_BACKEND_URL.replace(/\/$/, "")}/docs`

  return (
    <WorkbenchShell>
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[22px] font-medium tracking-tight">系统</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              浏览器只打 Next <code className="font-mono text-xs">/api/*</code>
              。一场听证一个 <code className="font-mono text-xs">session_id</code>
              。本机后端 <code className="font-mono text-xs">{PUBLIC_BACKEND_URL}</code>。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => loadHealth()} disabled={loading}>
              <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
              刷新
            </Button>
            <Button variant="outline" size="sm" asChild>
              <a href={swaggerHref} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="size-3.5" />
                Swagger
              </a>
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/docs">文档</Link>
            </Button>
          </div>
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          {SHORTCUTS.map((item) => (
            <Button key={item.href} variant="outline" size="sm" asChild>
              <Link href={item.href}>{item.label}</Link>
            </Button>
          ))}
        </div>

        <JourneyError
          error={error}
          fallback="健康检查失败"
          onRetry={() => void loadHealth()}
          busy={loading}
          className="mb-4"
        />

        <div className="mb-6 overflow-x-auto rounded-lg border border-border">
          <div className="border-b border-border px-3 py-2 text-[13px] font-medium">健康检查</div>
          {loading && !health ? (
            <p className="px-3 py-6 text-sm text-muted-foreground">加载中…</p>
          ) : health ? (
            <pre className="max-h-72 overflow-auto bg-muted/40 p-3 font-mono text-xs">{JSON.stringify(health, null, 2)}</pre>
          ) : null}
        </div>

        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm tabular-nums">
            <thead className="border-b border-border text-left text-[12px] text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">档</th>
                <th className="px-3 py-2 font-medium">FastAPI</th>
                <th className="px-3 py-2 font-medium">说明</th>
                <th className="px-3 py-2 font-medium">页面</th>
                <th className="px-3 py-2 font-medium">Next</th>
              </tr>
            </thead>
            <tbody>
              {MAPPINGS.map((row) => (
                <tr key={row.backend + row.nextApi} className="border-b border-border/70 last:border-0 hover:bg-secondary">
                  <td className="px-3 py-2 text-xs text-muted-foreground">
                    {row.tier === "实验" ? <ExperimentBadge /> : row.tier}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{row.backend}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.desc}</td>
                  <td className="px-3 py-2">
                    <Link href={row.frontendPage.href} className="text-primary hover:underline">
                      {row.frontendPage.label}
                    </Link>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{row.nextApi}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div id="experiment-panel" className="mt-8 overflow-hidden rounded-lg border border-border">
          <div className="border-b border-border px-3 py-2">
            <div className="flex items-center gap-2 text-[13px] font-medium">
              实验面板
              <ExperimentBadge />
            </div>
            <p className="mt-1 text-[12px] text-muted-foreground">
              走 <code className="font-mono">/case/*</code>
              。<code className="font-mono">game.py</code> 里同名会话版重复端点保留，本页不用。
              后端离线时只显示错误，页面不崩。
            </p>
          </div>
          <div className="space-y-4 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>接口</Label>
                <Select
                  value={experimentKind}
                  onValueChange={(v) =>
                    setExperimentKind(v as "progressive-rag" | "dual-mode" | "multi-judge")
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="progressive-rag">Progressive RAG</SelectItem>
                    <SelectItem value="dual-mode">双模式推理</SelectItem>
                    <SelectItem value="multi-judge">多法官</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {experimentKind === "progressive-rag" ? (
                <div className="space-y-1.5">
                  <Label>阶段</Label>
                  <Input value={ragStage} onChange={(e) => setRagStage(e.target.value)} />
                </div>
              ) : null}
              {experimentKind === "multi-judge" ? (
                <div className="space-y-1.5">
                  <Label>法官数</Label>
                  <Input
                    type="number"
                    min={2}
                    max={7}
                    value={judgeCount}
                    onChange={(e) => setJudgeCount(Number(e.target.value) || 3)}
                  />
                </div>
              ) : null}
            </div>
            {experimentKind === "progressive-rag" ? (
              <div className="space-y-1.5">
                <Label>context JSON</Label>
                <Textarea
                  value={ragContext}
                  onChange={(e) => setRagContext(e.target.value)}
                  rows={4}
                  className="font-mono text-xs"
                />
              </div>
            ) : null}
            {experimentKind === "dual-mode" ? (
              <>
                <div className="space-y-1.5">
                  <Label>案情</Label>
                  <Textarea value={dualCase} onChange={(e) => setDualCase(e.target.value)} rows={3} />
                </div>
                <div className="space-y-1.5">
                  <Label>请求</Label>
                  <Textarea value={dualClaims} onChange={(e) => setDualClaims(e.target.value)} rows={2} />
                </div>
              </>
            ) : null}
            {experimentKind === "multi-judge" ? (
              <>
                <div className="space-y-1.5">
                  <Label>事实</Label>
                  <Textarea value={judgeFacts} onChange={(e) => setJudgeFacts(e.target.value)} rows={3} />
                </div>
                <div className="space-y-1.5">
                  <Label>请求</Label>
                  <Textarea value={judgeClaims} onChange={(e) => setJudgeClaims(e.target.value)} rows={2} />
                </div>
              </>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => void runExperiment()} disabled={experimentBusy}>
                {experimentBusy ? "提交中…" : "提交"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => void loadReference("causes")} disabled={experimentBusy}>
                争议原因
              </Button>
              <Button size="sm" variant="outline" onClick={() => void loadReference("bigfive")} disabled={experimentBusy}>
                Big Five
              </Button>
              <Button size="sm" variant="outline" onClick={() => void loadReference("benchmark")} disabled={experimentBusy}>
                渐进基准
              </Button>
            </div>
            <JourneyError
              error={experimentError}
              fallback="实验调用失败"
              onRetry={lastExperiment ? () => lastExperiment() : undefined}
              busy={experimentBusy}
            />
            {experimentResult ? (
              <pre className="max-h-80 overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
                {JSON.stringify(experimentResult, null, 2)}
              </pre>
            ) : null}
          </div>
        </div>
      </main>
    </WorkbenchShell>
  )
}
