"use client"

import { useState, useEffect, useRef } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Label } from "@/components/ui/label"
import { Navigation } from "@/components/navigation"
import { Footer } from "@/components/footer"
import { ScrollIndicator } from "@/components/scroll-indicator"
import {
  MessageSquare,
  Send,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ArrowLeft,
  Trash2,
  Download,
  RefreshCcw,
  FastForward,
  UserCircle2,
  Scale,
  Gavel,
} from "lucide-react"
import type {
  DialogEntry,
  ConversationMessageResponse,
  ConversationInfo,
  AutoAdvanceResponse,
  CourtStage,
  CourtSubStage,
} from "@/lib/conversation-types"

const STAGE_LABELS: Record<string, string> = {
  opening: "开庭阶段",
  investigation: "法庭调查",
  debate: "法庭辩论",
  mediation: "法庭调解",
  judgment: "宣判阶段",
  dialogue: "对话进行中",
  finished: "已完成",
}

const SUB_STAGE_LABELS: Record<string, string> = {
  opening_identity: "身份核实",
  opening_composition: "宣布庭审构成",
  opening_rights: "权利义务告知",
  opening_recusal: "回避询问",
  opening_absence: "缺席后果告知",
  opening_done: "开庭准备完毕",
  investigation_claim: "原告陈述",
  investigation_defense: "被告答辩",
  investigation_evidence: "举证",
  investigation_cross_exam: "质证",
  investigation_fact_inquiry: "事实核实",
  investigation_done: "调查完毕",
  debate_focus: "归纳争议焦点",
  debate_argument: "辩论",
  debate_rebuttal: "反驳",
  debate_final_statement: "最后陈述",
  debate_done: "辩论完毕",
  mediation_ask: "询问调解意愿",
  mediation_plaintiff_resp: "等待原告表态",
  mediation_defendant_resp: "等待被告表态",
  mediation_announce: "宣布调解结果",
  mediation_done: "调解完毕",
  judgment_generating: "生成判决中",
  judgment_done: "判决完成",
}

const SCENARIO_NAMES: Record<string, string> = {
  CD: "起诉状生成",
  DD: "答辩状生成",
  CI: "法庭判决",
}

function getRoleDisplayName(role: string): string {
  const roleMap: Record<string, string> = {
    Client: "当事人",
    Lawyer: "律师",
    Judge: "法官",
    Plaintiff: "原告",
    Defendant: "被告",
    Final: "最终文书",
  }
  return roleMap[role] || role
}

function getRoleBubbleStyle(role: string): string {
  switch (role) {
    case "Lawyer":
      return "bg-blue-50 border border-blue-200 dark:bg-blue-950/30 dark:border-blue-800"
    case "Judge":
      return "bg-amber-50 border border-amber-200 dark:bg-amber-950/30 dark:border-amber-800"
    case "Final":
      return "bg-green-50 border border-green-300 dark:bg-green-950/30 dark:border-green-800"
    case "Plaintiff":
      return "bg-purple-50 border border-purple-200 dark:bg-purple-950/30 dark:border-purple-800"
    case "Defendant":
      return "bg-orange-50 border border-orange-200 dark:bg-orange-950/30 dark:border-orange-800"
    case "Client":
      return "bg-primary text-primary-foreground"
    default:
      return "bg-muted"
  }
}

function getRoleDotColor(role: string): string {
  switch (role) {
    case "Lawyer":
      return "bg-blue-500"
    case "Judge":
      return "bg-amber-500"
    case "Final":
      return "bg-green-500"
    case "Plaintiff":
      return "bg-purple-500"
    case "Defendant":
      return "bg-orange-500"
    case "Client":
      return "bg-emerald-400"
    default:
      return "bg-gray-500"
  }
}

function isAiRole(role: string): boolean {
  return ["Lawyer", "Judge", "Final"].includes(role)
}

export default function ConversationPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params.sessionId as string

  const [messages, setMessages] = useState<DialogEntry[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isAdvancing, setIsAdvancing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isFinished, setIsFinished] = useState(false)
  const [isFetching, setIsFetching] = useState(false)

  const [scenario, setScenario] = useState<string>("")
  const [caseId, setCaseId] = useState<string>("")
  const [currentStage, setCurrentStage] = useState<CourtStage | null>(null)
  const [currentSubStage, setCurrentSubStage] = useState<CourtSubStage | null>(null)
  const [nextSpeaker, setNextSpeaker] = useState<string | null>(null)

  const [selectedRole, setSelectedRole] = useState<string>("")
  const [advanceRounds, setAdvanceRounds] = useState(3)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [streamingText, setStreamingText] = useState("")
  const sendAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    loadConversation()
  }, [sessionId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (!scenario) return
    if (scenario === "CI") {
      setSelectedRole(nextSpeaker || "Plaintiff")
    } else {
      setSelectedRole("Client")
    }
  }, [scenario, nextSpeaker])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const applyConversationData = (data: ConversationInfo | AutoAdvanceResponse) => {
    setMessages(data.dialog_history || [])
    setIsFinished(data.is_finished ?? false)
    setCurrentStage(data.current_stage ?? null)
    setCurrentSubStage(data.current_sub_stage ?? null)
    setNextSpeaker(data.next_speaker ?? null)

    if ("scenario" in data) {
      setScenario(data.scenario)
      setCaseId(data.case_id)
    }
  }

  const loadConversation = async () => {
    try {
      setIsFetching(true)
      const response = await fetch(`/api/conversation/${sessionId}`)
      if (!response.ok) {
        if (response.status === 404) {
          setError("会话不存在")
          return
        }
        throw new Error(`HTTP ${response.status}`)
      }
      const data: ConversationInfo = await response.json()
      applyConversationData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载会话失败")
    } finally {
      setIsFetching(false)
    }
  }

  const getResponseError = async (response: Response) => {
    try {
      const data = await response.json()
      return data?.detail || data?.error || `HTTP ${response.status}`
    } catch {
      return `HTTP ${response.status}`
    }
  }

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading || isFinished) return

    const sent = inputMessage
    setIsLoading(true)
    setError(null)
    setStreamingText("")

    const controller = new AbortController()
    sendAbortRef.current = controller

    // 乐观渲染用户消息，流式期间即时可见
    setMessages((prev) => [
      ...prev,
      { turn: prev.length, role: selectedRole || "Client", message: sent },
    ])

    try {
      const response = await fetch(`/api/conversation/${sessionId}/message/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: sent, role: selectedRole || undefined }),
        signal: controller.signal,
      })

      if (!response.ok || !response.body) throw new Error(await getResponseError(response))

      const reader = response.body.getReader()
      const decoder = new TextDecoder("utf-8")
      let buffer = ""
      const finals: ConversationMessageResponse[] = []
      let gotDelta = false

      const handleEvent = (evt: Record<string, unknown>) => {
        if (evt.type === "delta" && typeof evt.text === "string") {
          gotDelta = true
          setStreamingText((prev) => prev + evt.text)
        } else if (evt.type === "final") {
          finals.push(evt as unknown as ConversationMessageResponse)
        }
      }

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE 事件以空行分隔
        const events = buffer.split("\n\n")
        buffer = events.pop() ?? ""
        for (const ev of events) {
          const line = ev.split("\n").find((l) => l.startsWith("data:"))
          if (!line) continue
          try {
            handleEvent(JSON.parse(line.slice(5).trim()))
          } catch {
            // 忽略无法解析的残片（心跳等）
          }
        }
      }

      const finalData = finals[finals.length - 1]
      if (!finalData && gotDelta) {
        // 后端异常断流：以已收到的流文本兜底收尾
        setStreamingText((prev) => {
          if (prev) setMessages((m) => [...m, { turn: m.length, role: "Lawyer", message: prev }])
          return ""
        })
        setError("连接中断，回复可能不完整")
        return
      }
      if (!finalData) throw new Error("后端未返回结果")

      setStreamingText("")
      setMessages(finalData.dialog_history)
      setInputMessage("")
      if (finalData.is_finished) setIsFinished(true)
      if (finalData.degraded) setError("当前未配置 LLM，本条回复由离线模板生成")

      await loadConversation()
    } catch (err) {
      const msg = err instanceof Error ? err.message : "发送消息失败"
      if (msg.includes("AbortError")) {
        setError("已停止本次请求")
      } else {
        setError(msg)
      }
      setMessages((prev) => prev.slice(0, -1)) // 移除乐观渲染的用户消息
    } finally {
      sendAbortRef.current = null
      setStreamingText("")
      setIsLoading(false)
    }
  }

  const handleAutoAdvance = async () => {
    if (isAdvancing || isFinished) return

    setIsAdvancing(true)
    setError(null)

    try {
      const response = await fetch(`/api/conversation/${sessionId}/auto-advance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_rounds: advanceRounds }),
      })

      if (!response.ok) throw new Error(await getResponseError(response))

      const data: AutoAdvanceResponse = await response.json()
      applyConversationData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "自动推进失败")
    } finally {
      setIsAdvancing(false)
    }
  }

  const handleStop = () => {
    sendAbortRef.current?.abort()
  }

  const handleDeleteConversation = async () => {
    if (!confirm("确定要删除这个会话吗？")) return

    try {
      const response = await fetch(`/api/conversation/${sessionId}`, { method: "DELETE" })
      if (!response.ok) throw new Error(await getResponseError(response))
      router.push("/conversation")
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除会话失败")
    }
  }

  const downloadText = (filename: string, content: string, mime = "application/json;charset=utf-8") => {
    const blob = new Blob([content], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const handleExportJson = () => {
    downloadText(
      `conversation_${sessionId.slice(0, 8)}.json`,
      JSON.stringify({ session_id: sessionId, scenario, case_id: caseId, dialog_history: messages }, null, 2),
    )
  }

  const handleExportJsonl = () => {
    downloadText(
      `dialog_history_${sessionId.slice(0, 8)}.jsonl`,
      messages.map((m) => JSON.stringify(m)).join("\n"),
      "application/jsonl;charset=utf-8",
    )
  }

  const availableRoles = scenario === "CI"
    ? [
        { value: "Plaintiff", label: "原告" },
        { value: "Defendant", label: "被告" },
      ]
    : [
        { value: "Client", label: "当事人" },
      ]

  return (
    <div className="min-h-screen bg-background">
      <Navigation />

      <section className="container mx-auto px-4 md:px-8 py-8 md:py-12">
        <div className="max-w-4xl mx-auto">
          {/* 顶部信息栏 */}
          <Card className="mb-4 border-2">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="sm" onClick={() => router.push("/conversation")}>
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    返回
                  </Button>
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      {scenario === "CI" ? <Gavel className="w-5 h-5" /> : <Scale className="w-5 h-5" />}
                      {scenario
                        ? `${SCENARIO_NAMES[scenario] || scenario} - ${caseId}`
                        : "加载中..."}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      会话ID: {sessionId.substring(0, 8)}...
                      {messages.length > 0 && ` | ${messages.length} 条消息`}
                    </CardDescription>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Button variant="ghost" size="sm" onClick={loadConversation} disabled={isFetching}>
                    <RefreshCcw className={`w-4 h-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
                    刷新
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleExportJson} disabled={messages.length === 0}>
                    <Download className="w-4 h-4 mr-2" />
                    JSON
                  </Button>
                  <Button variant="ghost" size="sm" onClick={handleExportJsonl} disabled={messages.length === 0}>
                    <Download className="w-4 h-4 mr-2" />
                    JSONL
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDeleteConversation}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    删除
                  </Button>
                </div>
              </div>
            </CardHeader>
          </Card>

          {/* 阶段指示器 + 子阶段 + 下一步提示 */}
          {scenario && !isFinished && (
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              {currentStage && (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary/10 border border-primary/20 rounded-full text-sm font-medium">
                  <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
                  {STAGE_LABELS[currentStage] || currentStage}
                </div>
              )}
              {currentSubStage && scenario === "CI" && (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-full text-sm text-amber-800 dark:text-amber-300">
                  <Gavel className="w-3.5 h-3.5" />
                  {SUB_STAGE_LABELS[currentSubStage] || currentSubStage}
                </div>
              )}
              {nextSpeaker && (
                <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-muted border rounded-full text-sm text-muted-foreground">
                  <UserCircle2 className="w-4 h-4" />
                  下一步由 <span className="font-semibold text-foreground">{getRoleDisplayName(nextSpeaker)}</span> 发言
                </div>
              )}
            </div>
          )}

          {/* 错误提示 */}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* 完成提示 + CI 阶段进度总览 */}
          {isFinished && (
            <Alert className="mb-4 border-green-500 bg-green-50 dark:bg-green-950/30">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800 dark:text-green-300">
                对话已完成，已生成最终文书
              </AlertDescription>
            </Alert>
          )}
          {isFinished && scenario === "CI" && (
            <div className="mb-4 flex items-center gap-2 flex-wrap">
              {["opening", "investigation", "debate", "mediation", "judgment"].map((stage) => (
                <div
                  key={stage}
                  className="inline-flex items-center gap-1 px-2.5 py-1 bg-green-100 dark:bg-green-900/30 border border-green-300 dark:border-green-700 rounded text-xs font-medium text-green-800 dark:text-green-300"
                >
                  <CheckCircle2 className="w-3 h-3" />
                  {STAGE_LABELS[stage]}
                </div>
              ))}
            </div>
          )}

          {/* 消息列表 */}
          <Card className="mb-4 border-2" style={{ height: "55vh" }}>
            <CardContent className="p-4 h-full overflow-y-auto">
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <div className="text-center">
                    <MessageSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>还没有消息</p>
                    <p className="text-sm mt-1">发送消息或使用自动推进开始对话</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {messages.map((msg, index) => (
                    <div
                      key={index}
                      className={`flex ${isAiRole(msg.role) ? "justify-start" : "justify-end"}`}
                    >
                      <div className={`max-w-[80%] rounded-lg p-3 ${getRoleBubbleStyle(msg.role)}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <div className={`w-2 h-2 rounded-full ${getRoleDotColor(msg.role)}`} />
                          <span className="text-xs font-semibold opacity-70">
                            {getRoleDisplayName(msg.role)}
                          </span>
                          <span className="text-xs opacity-40">#{msg.turn}</span>
                        </div>
                        <div className="whitespace-pre-wrap text-sm">{msg.message}</div>
                      </div>
                    </div>
                  ))}
                  {isLoading && streamingText && (
                    <div className="flex justify-start">
                      <div className="max-w-[80%] rounded-lg p-3 bg-muted/40 border border-dashed">
                        <div className="flex items-center gap-2 mb-1">
                          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                          <span className="text-xs font-semibold opacity-70">律师</span>
                          <span className="text-xs opacity-40">正在输入…</span>
                        </div>
                        <div className="whitespace-pre-wrap text-sm">
                          {streamingText}
                          <span className="inline-block w-2 h-4 ml-0.5 align-text-bottom bg-foreground/70 animate-pulse" />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </CardContent>
          </Card>

          {/* 自动推进控制栏 */}
          {!isFinished && (
            <Card className="mb-4 border-2 border-dashed">
              <CardContent className="p-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <FastForward className="w-4 h-4" />
                    自动推进
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-muted-foreground whitespace-nowrap">轮数</Label>
                    <Select
                      value={String(advanceRounds)}
                      onValueChange={(v) => setAdvanceRounds(Number(v))}
                    >
                      <SelectTrigger className="w-20 h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[1, 2, 3, 5, 8, 10].map((n) => (
                          <SelectItem key={n} value={String(n)}>
                            {n}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleAutoAdvance}
                    disabled={isAdvancing || isLoading || isFinished}
                  >
                    {isAdvancing ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        推进中...
                      </>
                    ) : (
                      <>
                        <FastForward className="w-4 h-4 mr-2" />
                        开始自动推进
                      </>
                    )}
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    Agent 将与模拟对手自动进行多轮对话
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 手动输入区 */}
          <Card className="border-2">
            <CardContent className="p-4">
              <div className="flex gap-2 items-end">
                {/* CI 场景下的角色选择 */}
                {scenario === "CI" && !isFinished && (
                  <div className="flex flex-col gap-1">
                    <Label className="text-xs text-muted-foreground">发言角色</Label>
                    <Select value={selectedRole} onValueChange={setSelectedRole}>
                      <SelectTrigger className="w-24 h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {availableRoles.map((r) => (
                          <SelectItem key={r.value} value={r.value}>
                            {r.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <Input
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      handleSendMessage()
                    }
                  }}
                  placeholder={isFinished ? "对话已完成" : `以${getRoleDisplayName(selectedRole || "Client")}身份输入消息...`}
                  disabled={isLoading || isFinished || isAdvancing}
                  className="flex-1"
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={isLoading || !inputMessage.trim() || isFinished || isAdvancing}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      发送中...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4 mr-2" />
                      发送
                    </>
                  )}
                </Button>
                {isLoading && (
                  <Button variant="outline" onClick={handleStop}>
                    停止
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <Footer />
    </div>
  )
}
