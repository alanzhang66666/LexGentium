"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import {
  MessageSquare,
  Plus,
  Loader2,
  AlertCircle,
  Sparkles,
  Clock,
  MessageCircle,
  Search,
  Filter,
  CheckCircle2,
} from "lucide-react"
import type { ConversationSummary, ConversationStartRequest } from "@/lib/conversation-types"

export default function ConversationListPage() {
  const router = useRouter()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 列表筛选/分页
  const [query, setQuery] = useState("")
  const [scenarioFilter, setScenarioFilter] = useState<"ALL" | "CD" | "DD" | "CI">("ALL")
  const [statusFilter, setStatusFilter] = useState<"ALL" | "RUNNING" | "FINISHED">("ALL")
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)

  // 新建会话表单
  const [newScenario, setNewScenario] = useState<"CD" | "DD" | "CI">("CD")
  const [newCaseId, setNewCaseId] = useState("test_001")
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    loadConversations()
  }, [offset])

  const loadConversations = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/conversation/list?limit=${limit}&offset=${offset}`)
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setConversations(data.sessions || [])
      setTotal(typeof data.total === "number" ? data.total : (data.sessions || []).length)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载会话列表失败")
    } finally {
      setLoading(false)
    }
  }

  const handleCreateConversation = async () => {
    if (!newCaseId.trim()) {
      setError("请输入案例ID")
      return
    }

    setCreating(true)
    setError(null)

    try {
      const request: ConversationStartRequest = {
        scenario: newScenario,
        case_id: newCaseId.trim(),
      }

      const response = await fetch("/api/conversation/start", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()
      router.push(`/conversation/${data.session_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建会话失败")
    } finally {
      setCreating(false)
    }
  }

  const formatDate = (dateString: string): string => {
    try {
      const date = new Date(dateString)
      return date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    } catch {
      return dateString
    }
  }

  const scenarioNames: Record<string, string> = {
    CD: "起诉状生成",
    DD: "答辩状生成",
    CI: "法庭判决",
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
      (scenarioNames[c.scenario] || "").toLowerCase().includes(q)
    )
  })

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="relative border-b bg-gradient-to-br from-background via-muted/30 to-background overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(120,119,198,0.1),transparent_50%)]" />
        <div className="container mx-auto px-4 md:px-8 py-12 md:py-16 relative">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 border border-primary/20 rounded-full mb-6 backdrop-blur-sm">
              <Sparkles className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold text-primary">智能对话管理</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-bold mb-4 text-balance bg-gradient-to-br from-foreground to-foreground/70 bg-clip-text text-transparent">
              对话管理
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground leading-relaxed text-pretty">
              创建和管理智能对话会话，体验流畅的多轮交互
            </p>
          </div>
        </div>
      </section>

      <ScrollIndicator />

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        {/* 创建新会话 */}
        <Card className="mb-8 border-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-primary/10 border border-primary/20">
                <Plus className="w-5 h-5 text-primary" />
              </div>
              创建新会话
            </CardTitle>
            <CardDescription>开始一个新的智能对话会话</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>场景</Label>
                <Select value={newScenario} onValueChange={(v) => setNewScenario(v as "CD" | "DD" | "CI")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="CD">起诉状生成 (CD)</SelectItem>
                    <SelectItem value="DD">答辩状生成 (DD)</SelectItem>
                    <SelectItem value="CI">法庭判决 (CI)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>案例ID</Label>
                <Input
                  value={newCaseId}
                  onChange={(e) => setNewCaseId(e.target.value)}
                  placeholder="输入案例ID..."
                />
              </div>
              <div className="space-y-2">
                <Label>&nbsp;</Label>
                <Button
                  onClick={handleCreateConversation}
                  disabled={creating || !newCaseId.trim()}
                  className="w-full"
                >
                  {creating ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      创建中...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4 mr-2" />
                      创建会话
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 错误提示 */}
        {error && (
          <Alert variant="destructive" className="mb-8">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* 会话列表 */}
        <Card className="border-2">
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle>会话列表</CardTitle>
                <CardDescription>共 {total} 个会话</CardDescription>
              </div>
              <div className="flex items-center gap-2">
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
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-3 mb-4">
              <div className="relative">
                <Search className="w-4 h-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索 case_id / session_id / 场景…"
                  className="pl-9"
                />
              </div>
              <Select value={scenarioFilter} onValueChange={(v) => setScenarioFilter(v as any)}>
                <SelectTrigger>
                  <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    <SelectValue placeholder="按场景筛选" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部场景</SelectItem>
                  <SelectItem value="CD">CD 起诉状</SelectItem>
                  <SelectItem value="DD">DD 答辩状</SelectItem>
                  <SelectItem value="CI">CI 判决</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as any)}>
                <SelectTrigger>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-muted-foreground" />
                    <SelectValue placeholder="按状态筛选" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ALL">全部状态</SelectItem>
                  <SelectItem value="RUNNING">进行中</SelectItem>
                  <SelectItem value="FINISHED">已完成</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : filtered.length > 0 ? (
              <div className="space-y-3">
                {filtered.map((conv) => (
                  <Card
                    key={conv.session_id}
                    className="border hover:bg-muted/50 cursor-pointer transition-colors"
                    onClick={() => router.push(`/conversation/${conv.session_id}`)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="px-2 py-1 bg-primary/10 rounded text-xs font-semibold">
                              {scenarioNames[conv.scenario] || conv.scenario}
                            </span>
                            <span className="text-sm font-semibold">{conv.case_id}</span>
                            {conv.is_finished ? (
                              <span className="px-2 py-1 bg-green-500/10 text-green-700 rounded text-xs font-semibold">
                                已完成
                              </span>
                            ) : (
                              <span className="px-2 py-1 bg-muted text-muted-foreground rounded text-xs font-semibold">
                                进行中
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                              <MessageCircle className="w-3 h-3" />
                              {conv.message_count} 条消息
                            </div>
                            <div className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatDate(conv.updated_at)}
                            </div>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            router.push(`/conversation/${conv.session_id}`)
                          }}
                        >
                          打开
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}

                <div className="flex items-center justify-between pt-2">
                  <div className="text-xs text-muted-foreground">
                    显示 {Math.min(offset + 1, total)} - {Math.min(offset + conversations.length, total)} / {total}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset === 0}
                      onClick={() => setOffset((o) => Math.max(0, o - limit))}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={offset + limit >= total}
                      onClick={() => setOffset((o) => o + limit)}
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <MessageSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>{query || scenarioFilter !== "ALL" || statusFilter !== "ALL" ? "没有匹配的会话" : "还没有会话"}</p>
                <p className="text-sm mt-1">
                  {query || scenarioFilter !== "ALL" || statusFilter !== "ALL" ? "尝试清空筛选条件" : "创建一个新会话开始对话吧"}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <Footer />
    </div>
  )
}

