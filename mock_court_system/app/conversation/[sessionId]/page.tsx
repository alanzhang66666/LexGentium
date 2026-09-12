"use client"

import { useEffect, useRef, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { WorkbenchShell } from "@/components/shell"
import { Composer } from "@/components/hearing/Composer"
import { StageBadge } from "@/components/hearing/StageBadge"
import { Transcript } from "@/components/hearing/Transcript"
import {
  AlertCircle,
  ArrowLeft,
  Box,
  CheckCircle2,
  Download,
  Gavel,
  RefreshCcw,
  Scale,
  Swords,
  Trash2,
} from "lucide-react"
import { autoAdvance, deleteConversation, deriveConversation, getConversation, postSessionClaim, streamSessionMessage } from "@/lib/api"
import { ClaimChainPanel } from "@/components/research/claim-chain"
import type { ResearchClaimNode } from "@/lib/research"
import { SCENARIO_LABELS, STAGE_LABELS } from "@/lib/labels"
import { SessionProvider, useSession } from "@/lib/session/SessionProvider"
import type {
  AutoAdvanceResponse,
  ConversationInfo,
  ConversationMessageResponse,
  CourtStage,
  CourtSubStage,
  DialogEntry,
} from "@/lib/conversation-types"

function ConversationSessionInner() {
  const router = useRouter()
  const { sessionId, info, refresh } = useSession()

  const [messages, setMessages] = useState<DialogEntry[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isAdvancing, setIsAdvancing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isFinished, setIsFinished] = useState(false)
  const [isFetching, setIsFetching] = useState(false)
  const [scenario, setScenario] = useState("")
  const [caseId, setCaseId] = useState("")
  const [currentStage, setCurrentStage] = useState<CourtStage | null>(null)
  const [currentSubStage, setCurrentSubStage] = useState<CourtSubStage | null>(null)
  const [nextSpeaker, setNextSpeaker] = useState<string | null>(null)
  const [selectedRole, setSelectedRole] = useState("")
  const [advanceRounds, setAdvanceRounds] = useState(3)
  const [streamingText, setStreamingText] = useState("")
  const [claimError, setClaimError] = useState<string | null>(null)
  const [claimBusy, setClaimBusy] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sendAbortRef = useRef<AbortController | null>(null)

  const links = info?.links || {}
  const research = info?.research || null
  const claims = (info?.claim_chain || []) as ResearchClaimNode[]

  useEffect(() => {
    void loadConversation()
  }, [sessionId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingText])

  useEffect(() => {
    if (!scenario) return
    setSelectedRole(scenario === "CI" ? nextSpeaker || "Plaintiff" : "Client")
  }, [scenario, nextSpeaker])

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
      const data = await getConversation(sessionId)
      applyConversationData(data)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载会话失败")
    } finally {
      setIsFetching(false)
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
    setMessages((prev) => [...prev, { turn: prev.length, role: selectedRole || "Client", message: sent }])

    try {
      const finals: ConversationMessageResponse[] = []
      await streamSessionMessage(
        sessionId,
        { message: sent, role: selectedRole || undefined },
        (evt) => {
          if (evt.type === "delta" && typeof evt.text === "string") {
            setStreamingText((prev) => prev + evt.text)
          } else if (evt.type === "final") {
            finals.push(evt as unknown as ConversationMessageResponse)
          }
        },
        controller.signal,
      )
      const finalData = finals[finals.length - 1]
      if (!finalData) throw new Error("后端未返回结果")
      setStreamingText("")
      setMessages(finalData.dialog_history)
      setInputMessage("")
      if (finalData.is_finished) setIsFinished(true)
      if (finalData.degraded) setError("当前未配置 LLM，本条回复由离线模板生成")
      await loadConversation()
    } catch (err) {
      const msg = err instanceof Error ? err.message : "发送消息失败"
      setError(msg.includes("AbortError") ? "已停止本次请求" : msg)
      setMessages((prev) => prev.slice(0, -1))
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
      applyConversationData(await autoAdvance(sessionId, advanceRounds))
    } catch (err) {
      setError(err instanceof Error ? err.message : "自动推进失败")
    } finally {
      setIsAdvancing(false)
    }
  }

  const handleClaimSubmit = async (body: {
    role: string
    action: string
    fact: string
    norm: string
    reasoning: string
    claim_id?: string
    target_claim_id?: string
  }) => {
    setClaimBusy(true)
    setClaimError(null)
    try {
      await postSessionClaim(sessionId, body)
      await loadConversation()
    } catch (err) {
      setClaimError(err instanceof Error ? err.message : "记录主张失败")
    } finally {
      setClaimBusy(false)
    }
  }

  const handleDerive = async () => {
    setClaimBusy(true)
    setClaimError(null)
    try {
      const next = await deriveConversation({
        session_id: sessionId,
        experiment_conditions: {
          notes: "derived from hearing text page",
          enable_source_audit: true,
        },
      })
      router.push(`/conversation/${next.session_id}`)
    } catch (err) {
      setClaimError(err instanceof Error ? err.message : "派生运行失败")
    } finally {
      setClaimBusy(false)
    }
  }

  const handleDeleteConversation = async () => {
    if (!confirm("确定要删除这个会话吗？")) return
    try {
      await deleteConversation(sessionId)
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

  return (
    <WorkbenchShell footer={false}>
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2">
          <Button variant="ghost" size="sm" onClick={() => router.push("/conversation")}>
            <ArrowLeft className="size-3.5" />
            返回
          </Button>
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-medium">
              {scenario === "CI" ? <Gavel className="size-3.5" /> : <Scale className="size-3.5" />}
              {scenario ? `${SCENARIO_LABELS[scenario] || scenario} · ${caseId}` : "加载中…"}
            </div>
            <div className="text-[12px] text-muted-foreground">
              {sessionId.substring(0, 8)}…
              {messages.length > 0 ? ` · ${messages.length} 条` : ""}
              {research?.run_id ? ` · ${research.run_id.slice(0, 12)}` : ""}
              {links.task_id ? ` · 全案 ${links.task_id.slice(0, 10)}` : ""}
              {links.game_id ? ` · 博弈 ${links.game_id.slice(0, 10)}` : ""}
            </div>
          </div>
          {scenario && !isFinished ? (
            <StageBadge
              stage={currentStage}
              subStage={currentSubStage}
              nextSpeaker={nextSpeaker}
              scenario={scenario}
            />
          ) : null}
          <div className="ml-auto flex flex-wrap items-center gap-1">
            <Button variant="outline" size="sm" asChild>
              <Link href={`/court3d/${sessionId}`}>
                <Box className="size-3.5" />
                观庭
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/full-simulation?session=${sessionId}`}>
                <Swords className="size-3.5" />
                全案
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href={`/evaluation?session=${sessionId}`}>送评</Link>
            </Button>
            <Button variant="ghost" size="sm" onClick={loadConversation} disabled={isFetching}>
              <RefreshCcw className={`size-3.5 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                downloadText(
                  `conversation_${sessionId.slice(0, 8)}.json`,
                  JSON.stringify({ session_id: sessionId, scenario, case_id: caseId, dialog_history: messages }, null, 2),
                )
              }
              disabled={messages.length === 0}
            >
              <Download className="size-3.5" />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleDeleteConversation} className="text-destructive">
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        </div>

        {error ? (
          <Alert variant="destructive" className="mx-4 mt-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {isFinished ? (
          <Alert className="mx-4 mt-2">
            <CheckCircle2 className="h-4 w-4 text-success" />
            <AlertDescription>听证已结束，已生成最终文书</AlertDescription>
          </Alert>
        ) : null}
        {isFinished && scenario === "CI" ? (
          <div className="flex flex-wrap gap-1.5 px-4 pt-2">
            {["opening", "investigation", "debate", "mediation", "judgment"].map((stage) => (
              <span key={stage} className="rounded-md border border-border px-2 py-0.5 text-[12px] text-muted-foreground">
                {STAGE_LABELS[stage]}
              </span>
            ))}
          </div>
        ) : null}

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <Transcript messages={messages} streamingText={isLoading ? streamingText : ""} endRef={messagesEndRef} />
            <Composer
              scenario={scenario}
              isFinished={isFinished}
              isLoading={isLoading}
              isAdvancing={isAdvancing}
              inputMessage={inputMessage}
              selectedRole={selectedRole}
              advanceRounds={advanceRounds}
              onInputChange={setInputMessage}
              onRoleChange={setSelectedRole}
              onAdvanceRoundsChange={setAdvanceRounds}
              onSend={handleSendMessage}
              onAdvance={handleAutoAdvance}
              onStop={() => sendAbortRef.current?.abort()}
            />
          </div>
          {research?.run_id ? (
            <ClaimChainPanel
              claims={claims}
              runId={research.run_id}
              derivedFrom={research.derived_from}
              materialsHash={research.materials_hash}
              busy={claimBusy}
              error={claimError}
              onSubmit={handleClaimSubmit}
              onDerive={handleDerive}
            />
          ) : null}
        </div>
      </div>
    </WorkbenchShell>
  )
}

export default function ConversationPage() {
  const params = useParams()
  const sessionId = params.sessionId as string
  return (
    <SessionProvider sessionId={sessionId}>
      <ConversationSessionInner />
    </SessionProvider>
  )
}
