"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WorkbenchShell } from "@/components/shell"
import { AlertCircle, Loader2, Plus } from "lucide-react"
import { CasePicker } from "@/components/hearing/CasePicker"
import { createGame, listConversations, listResearchPacks, startConversation } from "@/lib/api"
import { SCENARIO_LABELS, STRATEGY_LABELS } from "@/lib/labels"
import { writeLastSessionId } from "@/lib/session/last-session"
import type { ConversationSummary } from "@/lib/conversation-types"
import type { PackSummary } from "@/lib/research"

type CaseSource = "research" | "civil"

function packKey(pack: Pick<PackSummary, "dataset_id" | "cluster_id" | "pack_version">) {
  return `${pack.dataset_id}/${pack.cluster_id}/${pack.pack_version}`
}

const TKI_KEYS = Object.keys(STRATEGY_LABELS)

export default function ConversationListPage() {
  const router = useRouter()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [scenarioFilter, setScenarioFilter] = useState<"ALL" | "CD" | "DD" | "CI">("ALL")
  const [statusFilter, setStatusFilter] = useState<"ALL" | "RUNNING" | "FINISHED">("ALL")
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [newScenario, setNewScenario] = useState<"CD" | "DD" | "CI">("CI")
  const [caseSource, setCaseSource] = useState<CaseSource>("research")
  const [newCaseId, setNewCaseId] = useState("foreign_commercial_001")
  const [packs, setPacks] = useState<PackSummary[]>([])
  const [selectedPackKey, setSelectedPackKey] = useState("")
  const [plaintiffStrategy, setPlaintiffStrategy] = useState("")
  const [defendantStrategy, setDefendantStrategy] = useState("")
  const [creating, setCreating] = useState(false)

  const selectedPack = packs.find((pack) => packKey(pack) === selectedPackKey) || null

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const scenario = params.get("scenario")
    if (scenario === "CD" || scenario === "DD" || scenario === "CI") {
      setNewScenario(scenario)
    }
  }, [])

  useEffect(() => {
    loadConversations()
  }, [offset])

  useEffect(() => {
    listResearchPacks()
      .then((data) => {
        const rows = (data.packs || []) as PackSummary[]
        setPacks(rows)
        const preferred =
          rows.find((row) => row.dataset_id === "enforcement" && row.cluster_id === "enf-cn-notice-001") ||
          rows[0]
        if (preferred) {
          setSelectedPackKey((current) => current || packKey(preferred))
        }
      })
      .catch(() => setPacks([]))
  }, [])

  const loadConversations = async () => {
    setLoading(true)
    try {
      const data = await listConversations(limit, offset)
      setConversations(data.sessions || [])
      setTotal(typeof data.total === "number" ? data.total : (data.sessions || []).length)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载会话列表失败")
    } finally {
      setLoading(false)
    }
  }

  const handleCreateConversation = async () => {
    if (caseSource === "research") {
      if (!selectedPack) {
        setError("请选择研究包")
        return
      }
    } else if (!newCaseId.trim()) {
      setError("请输入案例ID")
      return
    }
    setCreating(true)
    setError(null)
    try {
      const payload =
        caseSource === "research" && selectedPack
          ? {
              scenario: newScenario,
              case_id: selectedPack.cluster_id,
              dataset_id: selectedPack.dataset_id,
              cluster_id: selectedPack.cluster_id,
              pack_version: selectedPack.pack_version,
            }
          : {
              scenario: newScenario,
              case_id: newCaseId.trim(),
            }
      const data = await startConversation(payload)
      writeLastSessionId(data.session_id)
      if (newScenario === "CI" && (plaintiffStrategy || defendantStrategy)) {
        try {
          await createGame({
            case_info: { case_id: payload.case_id },
            session_id: data.session_id,
            plaintiff_strategy: plaintiffStrategy || "compromising",
            defendant_strategy: defendantStrategy || "compromising",
          })
        } catch (gameErr) {
          setError(gameErr instanceof Error ? gameErr.message : "会话已创建，但策略开局失败")
        }
      }
      router.push(`/conversation/${data.session_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建会话失败")
    } finally {
      setCreating(false)
    }
  }

  const formatDate = (dateString: string): string => {
    try {
      return new Date(dateString).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return dateString
    }
  }

  const filtered = conversations.filter((c) => {
    const q = query.trim().toLowerCase()
    if (scenarioFilter !== "ALL" && c.scenario !== scenarioFilter) return false
    if (statusFilter === "FINISHED" && !c.is_finished) return false
    if (statusFilter === "RUNNING" && c.is_finished) return false
    if (!q) return true
    return (
      c.case_id.toLowerCase().includes(q) ||
      c.session_id.toLowerCase().includes(q) ||
      (SCENARIO_LABELS[c.scenario] || "").toLowerCase().includes(q)
    )
  })

  return (
    <WorkbenchShell>
      <main className="flex-1 px-4 py-6">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-[22px] font-medium tracking-tight">开庭</h1>
            <p className="mt-1 text-sm text-muted-foreground">一场听证一个 session，文字记录与观庭共用。</p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Select value={newScenario} onValueChange={(v) => setNewScenario(v as "CD" | "DD" | "CI")}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="CI">{SCENARIO_LABELS.CI}</SelectItem>
                <SelectItem value="CD">{SCENARIO_LABELS.CD}</SelectItem>
                <SelectItem value="DD">{SCENARIO_LABELS.DD}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={caseSource} onValueChange={(v) => setCaseSource(v as CaseSource)}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="research">研究包</SelectItem>
                <SelectItem value="civil">民事 1K</SelectItem>
              </SelectContent>
            </Select>
            {caseSource === "research" ? (
              <div className="w-72">
                <Select value={selectedPackKey} onValueChange={setSelectedPackKey}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择研究包" />
                  </SelectTrigger>
                  <SelectContent>
                    {packs.map((pack) => (
                      <SelectItem key={packKey(pack)} value={packKey(pack)}>
                        {pack.case_name || pack.cluster_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div className="w-56">
                <CasePicker value={newCaseId} onChange={setNewCaseId} />
              </div>
            )}
            {newScenario === "CI" ? (
              <>
                <Select value={plaintiffStrategy || "__none__"} onValueChange={(v) => setPlaintiffStrategy(v === "__none__" ? "" : v)}>
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="申请人立场" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">申请人立场</SelectItem>
                    {TKI_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        申 · {STRATEGY_LABELS[key]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={defendantStrategy || "__none__"} onValueChange={(v) => setDefendantStrategy(v === "__none__" ? "" : v)}>
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="被申请人立场" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">被申请人立场</SelectItem>
                    {TKI_KEYS.map((key) => (
                      <SelectItem key={key} value={key}>
                        被 · {STRATEGY_LABELS[key]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </>
            ) : null}
            <Button
              onClick={handleCreateConversation}
              disabled={creating || (caseSource === "research" ? !selectedPack : !newCaseId.trim())}
            >
              {creating ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
              新建
            </Button>
          </div>
        </div>
        <p className="mb-4 text-xs text-muted-foreground">
          {caseSource === "research"
            ? selectedPack
              ? `将载入 ${selectedPack.dataset_id} / ${selectedPack.cluster_id} / ${selectedPack.pack_version}`
              : "将载入研究包（尚未选择）"
            : `将载入 民事 1K · ${newCaseId.trim() || "未选 case_id"}`}
        </p>

        {error ? (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索案号 / 会话" className="max-w-xs" />
          <Select value={scenarioFilter} onValueChange={(v) => setScenarioFilter(v as "ALL" | "CD" | "DD" | "CI")}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">全部场景</SelectItem>
              <SelectItem value="CI">{SCENARIO_LABELS.CI}</SelectItem>
              <SelectItem value="CD">{SCENARIO_LABELS.CD}</SelectItem>
              <SelectItem value="DD">{SCENARIO_LABELS.DD}</SelectItem>
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as "ALL" | "RUNNING" | "FINISHED")}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">全部状态</SelectItem>
              <SelectItem value="RUNNING">进行中</SelectItem>
              <SelectItem value="FINISHED">已结束</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setOffset(0)
              loadConversations()
            }}
          >
            刷新
          </Button>
          <span className="ml-auto text-xs tabular-nums text-muted-foreground">{total} 场</span>
        </div>

        <div className="overflow-x-auto rounded-lg border border-border">
          {loading ? (
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-[12px] text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">场景</th>
                  <th className="px-3 py-2 font-medium">案号</th>
                  <th className="px-3 py-2 font-medium">状态</th>
                  <th className="px-3 py-2 font-medium">消息</th>
                  <th className="px-3 py-2 font-medium">更新</th>
                  <th className="px-3 py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="border-b border-border/70 last:border-0">
                    <td className="px-3 py-2.5">
                      <div className="h-3.5 w-16 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="h-3.5 w-40 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="h-3.5 w-12 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="h-3.5 w-8 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="h-3.5 w-24 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="ml-auto h-3.5 w-10 animate-pulse rounded bg-muted motion-reduce:animate-none" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : filtered.length === 0 ? (
            <div className="px-6 py-14 text-center">
              {conversations.length === 0 ? (
                <>
                  <p className="text-sm text-foreground">还没有听证</p>
                  <p className="mt-2 text-sm text-muted-foreground">右上角选场景和案号，点新建开一场。</p>
                </>
              ) : (
                <>
                  <p className="text-sm text-foreground">没有匹配的会话</p>
                  <p className="mt-2 text-sm text-muted-foreground">清空搜索或筛选后再看全部场次。</p>
                </>
              )}
            </div>
          ) : (
            <table className="w-full text-sm tabular-nums">
              <thead className="border-b border-border text-left text-[12px] text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">场景</th>
                  <th className="px-3 py-2 font-medium">案号</th>
                  <th className="px-3 py-2 font-medium">状态</th>
                  <th className="px-3 py-2 font-medium">消息</th>
                  <th className="px-3 py-2 font-medium">更新</th>
                  <th className="px-3 py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((conv) => (
                  <tr
                    key={conv.session_id}
                    className="cursor-pointer border-b border-border/70 last:border-0 hover:bg-secondary"
                    onClick={() => {
                      writeLastSessionId(conv.session_id)
                      router.push(`/conversation/${conv.session_id}`)
                    }}
                  >
                    <td className="px-3 py-2.5">{SCENARIO_LABELS[conv.scenario] || conv.scenario}</td>
                    <td className="px-3 py-2.5 font-medium">{conv.case_id}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{conv.is_finished ? "已结束" : "进行中"}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{conv.message_count}</td>
                    <td className="px-3 py-2.5 text-muted-foreground">{formatDate(conv.updated_at)}</td>
                    <td className="px-3 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          writeLastSessionId(conv.session_id)
                          router.push(`/court3d/${conv.session_id}`)
                        }}
                      >
                        观庭
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="mt-3 flex items-center justify-between text-xs tabular-nums text-muted-foreground">
          <span>
            {Math.min(offset + 1, total)}-{Math.min(offset + conversations.length, total)} / {total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - limit))}>
              上一页
            </Button>
            <Button variant="outline" size="sm" disabled={offset + limit >= total} onClick={() => setOffset((o) => o + limit)}>
              下一页
            </Button>
          </div>
        </div>
      </main>
    </WorkbenchShell>
  )
}
