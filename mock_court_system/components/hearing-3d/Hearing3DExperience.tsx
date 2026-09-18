"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { castManifest } from "./cast-manifest"
import { CameraMode } from "./CameraDirector"
import { EventTimeline } from "./EventTimeline"
import { Hearing3DScene } from "./Hearing3DScene"
import { HearingHUD } from "./HearingHUD"
import { MaterialPanel } from "./MaterialPanel"
import { loadSampleEvents, createPlaybackStore, appendAndConsume } from "./playback-store"
import { createInitialSceneState } from "./scene-reducer"
import { conversationFinishedToEvent, conversationMessageToEvent, conversationToHearingEvents, type ConversationPayload } from "./backend-event-adapter"
import { streamSessionMessage } from "@/lib/api/conversation"
import type { HearingEvent, SceneState } from "./contracts"
import { writeLastSessionId } from "@/lib/session/last-session"

export function Hearing3DExperience() {
  const [state, setState] = useState<SceneState>(createInitialSceneState())
  const [events, setEvents] = useState<HearingEvent[]>([])
  const [cameraMode, setCameraMode] = useState<CameraMode>("wide")
  const [automaticCamera, setAutomaticCamera] = useState(true)
  const [professional, setProfessional] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [inputMessage, setInputMessage] = useState("")
  const [streamingText, setStreamingText] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const storeRef = useRef(createPlaybackStore())

  useEffect(() => {
    const sessionId = typeof window === "undefined"
      ? null
      : new URLSearchParams(window.location.search).get("sessionId")
    setSessionId(sessionId)
    if (sessionId) writeLastSessionId(sessionId)
    const source = sessionId
      ? fetch(`/api/conversation/${encodeURIComponent(sessionId)}`)
          .then((response) => {
            if (!response.ok) throw new Error(`会话加载失败（${response.status}）`)
            return response.json()
          })
          .then((payload) => conversationToHearingEvents(payload))
      : loadSampleEvents()
    source
      .then((loaded) => {
        setEvents(loaded)
        storeRef.current.append(loaded)
        if (sessionId) storeRef.current.jumpToLatest()
        setState(storeRef.current.getState())
      })
      .catch((err) => setError(err instanceof Error ? err.message : "无法加载听证事件"))
  }, [])

  const refresh = useCallback(() => setState({ ...storeRef.current.getState(), pending_gap: storeRef.current.getPendingGap() }), [])

  useEffect(() => {
    if (!state.auto_play) return
    const timer = window.setInterval(() => {
      storeRef.current.tick()
      refresh()
    }, 900)
    return () => window.clearInterval(timer)
  }, [refresh, state.auto_play])

  const reset = useCallback(() => {
    storeRef.current = createPlaybackStore()
    storeRef.current.append(events)
    if (sessionId) storeRef.current.jumpToLatest()
    refresh()
  }, [events, refresh, sessionId])

  const sendLiveMessage = useCallback(async () => {
    if (!sessionId || !inputMessage.trim() || isStreaming) return
    setIsStreaming(true)
    setStreamingText("")
    setError(null)
    try {
      let text = ""
      let finalized = false
      await streamSessionMessage(sessionId, { message: inputMessage, role: "Client" }, (event) => {
        if (event.type === "delta") {
          text += String(event.text ?? "")
          setStreamingText(text)
          return
        }
        if (event.type === "finish") {
          if (!finalized) {
            finalized = true
            const payload: ConversationPayload = { session_id: sessionId, scenario: "CI", case_id: sessionId, dialog_history: [], is_finished: true }
            const finishedEvent = conversationFinishedToEvent(payload, storeRef.current.getLatestSeq() + 1)
            appendAndConsume(storeRef.current, [finishedEvent])
            setState(storeRef.current.getState())
            setEvents((previous) => [...previous, finishedEvent])
          }
          return
        }
        if (event.type === "error" || (event.type === "final" && event.error)) {
          throw new Error(String(event.error ?? "实时生成失败"))
        }
        if (event.type !== "final" || finalized) return
        finalized = true
        const response = event.response && typeof event.response === "object"
          ? event.response as Record<string, unknown>
          : {}
        const finalText = String(response.message ?? text)
        const role = String(response.role ?? "Judge")
        const payload: ConversationPayload = {
          session_id: sessionId, scenario: "CI", case_id: sessionId,
          dialog_history: [], is_finished: Boolean(event.is_finished),
        }
        const nextSeq = storeRef.current.getLatestSeq() + 1
        const liveEvent = conversationMessageToEvent(payload, finalText, role, nextSeq, `${sessionId}-live-${Date.now()}`, (event.reasoning_meta as Record<string, unknown> | null) ?? null)
        const appended = [liveEvent]
        if (event.is_finished) appended.push(conversationFinishedToEvent(payload, nextSeq + 1))
        appendAndConsume(storeRef.current, appended)
        setState(storeRef.current.getState())
        setEvents((previous) => [...previous, ...appended])
        setInputMessage("")
        setStreamingText("")
      })
      if (!finalized) throw new Error("实时会话已断开，未收到完成事件")
    } catch (err) {
      setError(err instanceof Error ? err.message : "实时发送失败")
    } finally {
      setIsStreaming(false)
    }
  }, [inputMessage, isStreaming, sessionId])

  return (
    <main className="flex min-h-0 flex-1 flex-col bg-background px-4 py-5 text-foreground md:px-6">
      <div className="mx-auto flex w-full max-w-[1500px] flex-1 flex-col">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[13px] text-muted-foreground">观庭 · OBJ 角色资产</p>
            <h1 className="text-[22px] font-medium tracking-tight">仲裁听证 3D</h1>
            <p className="mt-1 text-sm text-muted-foreground">九席供应商 OBJ 角色 + PBR 贴图 + 司法警察 OBJ 资产，不代表法律裁决。</p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <button className="rounded-md border border-border px-3 py-2 hover:bg-secondary" onClick={() => setProfessional((v) => !v)}>
              {professional ? "简明模式" : "专业模式"}
            </button>
            <button className="rounded-md border border-border px-3 py-2 hover:bg-secondary" onClick={reset}>重置</button>
            <button className="rounded-md border border-border px-3 py-2 hover:bg-secondary" onClick={() => setAutomaticCamera((value) => !value)}>
              {automaticCamera ? "自动导播" : "手动镜头"}
            </button>
            <select className="rounded-md border border-border bg-background px-3 py-2" value={cameraMode} onChange={(e) => { setAutomaticCamera(false); setCameraMode(e.target.value as CameraMode) }}>
              <option value="wide">全景</option>
              <option value="presiding_medium">首席中景</option>
              <option value="claimant_medium">申请方中景</option>
              <option value="respondent_medium">被申请方中景</option>
            </select>
          </div>
        </div>
        {error && <div className="mb-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
        {sessionId && (
          <div className="relative mb-4 flex gap-2 rounded-lg border border-border bg-card p-3">
            <input
              className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
              placeholder="向本场会话发送消息…"
              value={inputMessage}
              onChange={(event) => setInputMessage(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") void sendLiveMessage() }}
              disabled={isStreaming}
            />
            <button className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50" onClick={() => void sendLiveMessage()} disabled={isStreaming || !inputMessage.trim()}>
              {isStreaming ? "实时生成中…" : "发送到听证"}
            </button>
            {streamingText && <div className="absolute left-4 right-4 top-full z-10 mt-2 rounded-md border border-border bg-card p-3 text-sm">{streamingText}</div>}
          </div>
        )}
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <section className="relative min-h-[620px]">
            <Hearing3DScene state={state} cameraMode={cameraMode} automatic={automaticCamera} />
            <HearingHUD state={state} professional={professional} />
            <div className="absolute bottom-4 left-4 right-4">
              <EventTimeline store={storeRef.current} onChange={refresh} />
            </div>
          </section>
          <MaterialPanel state={state} />
        </div>
        <div className="mt-3 text-xs text-muted-foreground">九席已加载：{castManifest.length} · 供应商 OBJ：已加载 · 司法警察 OBJ：已加载 · 事件总数：{events.length} · sourceType: {state.source_type ?? (sessionId ? "backend_run" : "scripted_demo")}</div>
      </div>
    </main>
  )
}
