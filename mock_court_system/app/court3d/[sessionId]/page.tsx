"use client"

import dynamic from "next/dynamic"
import Link from "next/link"
import { useCallback, useEffect, useRef, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import { WorkbenchShell } from "@/components/shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Hud } from "@/components/court3d/Hud"
import { getGame } from "@/lib/api"
import { applyConversationMeta, streamConversationMessage } from "@/lib/court3d/adapters/conversationStream"
import { streamGameRound } from "@/lib/court3d/adapters/gameStream"
import { loadCast, type CastDefinition, type SkinId } from "@/lib/court3d/cast"
import {
  createPerformanceState,
  reducePerformance,
  setActorMouth,
  type PerformanceState,
} from "@/lib/court3d/performanceStore"
import type { PerformanceEvent } from "@/lib/court3d/protocol"
import { SpeechQueue } from "@/lib/court3d/speech/queue"
import { WebSpeechProvider } from "@/lib/court3d/speech/TtsProvider"
import { SessionProvider, useSession } from "@/lib/session/SessionProvider"
import type { ConflictStrategy, Scenario } from "@/lib/conversation-types"

const CourtScene = dynamic(() => import("@/components/court3d/CourtScene").then((m) => m.CourtScene), {
  ssr: false,
})

function Court3dSessionInner() {
  const search = useSearchParams()
  const { sessionId, info, refresh } = useSession()
  const [cast, setCast] = useState<CastDefinition | null>(null)
  const [skin] = useState<SkinId>((search.get("skin") as SkinId) || "swap")
  const [state, setState] = useState<PerformanceState>(() => createPerformanceState())
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ttsOn, setTtsOn] = useState(true)
  const queueRef = useRef<SpeechQueue | null>(null)

  const links = info?.links || {}
  const boundGame = Boolean(links.game_id)

  useEffect(() => {
    queueRef.current = new SpeechQueue(new WebSpeechProvider())
    return () => queueRef.current?.cancel()
  }, [])

  const emit = useCallback(
    (event: PerformanceEvent) => {
      setState((prev) => {
        if (event.kind === "speak" && prev.auditStatus === "unknown") {
          return prev
        }
        const next = reducePerformance(prev, event)
        if (event.kind === "speak" && ttsOn && queueRef.current && cast) {
          const role = cast.roles[event.actor]
          const skinDef = role.skins[skin]
          queueRef.current.enqueue({
            actor: event.actor,
            text: event.sentence,
            lang: event.speechKind === "relay" ? "en-US" : skinDef.voiceLang,
            voiceHint: skinDef.voiceHint === "female" || skinDef.voiceHint === "male" ? skinDef.voiceHint : undefined,
            onStart: () => {
              setState((s) => reducePerformance(s, { kind: "status", thinking: null }))
            },
            onMouth: (open) => setState((s) => setActorMouth(s, event.actor, open)),
            onEnd: () => setState((s) => setActorMouth(s, event.actor, 0)),
          })
        }
        if (event.kind === "status" && event.thinking) {
          queueRef.current?.markThinking(event.thinking)
        }
        return next
      })
    },
    [cast, skin, ttsOn],
  )

  useEffect(() => {
    let cancelled = false
    loadCast("foreign_commercial")
      .then((c) => {
        if (!cancelled) setCast(c)
      })
      .catch((e) => setError(String(e)))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!cast || !info) return
    applyConversationMeta(sessionId, {
      emit,
      scenario: info.scenario as Scenario,
      cast,
    })
  }, [cast, emit, info, sessionId])

  useEffect(() => {
    if (!links.game_id) return
    getGame(links.game_id)
      .then((game) => {
        const plaintiff = game.strategy_state?.plaintiff?.strategy_type as ConflictStrategy | undefined
        const defendant = game.strategy_state?.defendant?.strategy_type as ConflictStrategy | undefined
        if (plaintiff) emit({ kind: "stance", actor: "plaintiff_party", strategy: plaintiff })
        if (defendant) emit({ kind: "stance", actor: "defendant_party", strategy: defendant })
        emit({
          kind: "hud",
          payload: {
            plaintiffStrategy: plaintiff,
            defendantStrategy: defendant,
            convergence: game.equilibrium?.convergence_rate ?? game.equilibrium?.current_convergence,
          },
        })
      })
      .catch(() => {})
  }, [emit, links.game_id])

  const scenario = (info?.scenario as Scenario) || "CI"
  const defaultRole = scenario === "CI" ? "Plaintiff" : "Client"

  const send = async () => {
    if (!cast || !input.trim() || busy || state.auditStatus === "unknown") return
    setBusy(true)
    setError(null)
    try {
      await streamConversationMessage(sessionId, input.trim(), { emit, scenario, cast, userRole: defaultRole })
      setInput("")
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送失败")
    } finally {
      setBusy(false)
    }
  }

  const runBoundGame = async () => {
    if (!links.game_id) return
    setBusy(true)
    setError(null)
    try {
      await streamGameRound(links.game_id, emit)
    } catch (e) {
      setError(e instanceof Error ? e.message : "推演失败")
    } finally {
      setBusy(false)
    }
  }

  if (!cast) {
    return (
      <WorkbenchShell footer={false}>
        <p className="p-8 text-sm text-muted-foreground">加载剧组…</p>
      </WorkbenchShell>
    )
  }

  return (
    <WorkbenchShell footer={false}>
      <div className="relative min-h-0 flex-1">
        <CourtScene cast={cast} skin={skin} state={state} />
        <Hud state={state} cast={cast} skin={skin} showStrategy={boundGame} />
      </div>
      <div className="border-t border-border bg-background px-4 py-3">
        <div className="mx-auto flex max-w-5xl flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Button size="sm" variant="ghost" onClick={() => setTtsOn((v) => !v)}>
              TTS {ttsOn ? "开" : "关"}
            </Button>
            <Button size="sm" variant="ghost" asChild>
              <Link href={`/conversation/${sessionId}`}>文字记录</Link>
            </Button>
            {boundGame ? (
              <Button size="sm" variant="outline" onClick={runBoundGame} disabled={busy}>
                推演一轮
              </Button>
            ) : null}
          </div>
          <div className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={state.canAct && state.auditStatus !== "unknown" ? "以当前角色发言…" : "等待智能体或审计未知态…"}
              onKeyDown={(e) => {
                if (e.key === "Enter") void send()
              }}
              disabled={busy || state.auditStatus === "unknown"}
            />
            <Button onClick={send} disabled={busy || !input.trim() || state.auditStatus === "unknown"}>
              {busy ? "进行中" : "发言"}
            </Button>
          </div>
          {error ? <p className="text-xs text-destructive">{error}</p> : null}
        </div>
      </div>
    </WorkbenchShell>
  )
}

export default function Court3dSessionPage() {
  const params = useParams<{ sessionId: string }>()
  return (
    <SessionProvider sessionId={params.sessionId}>
      <Court3dSessionInner />
    </SessionProvider>
  )
}
