"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { castManifest } from "./cast-manifest"
import { CameraMode } from "./CameraDirector"
import { EventTimeline } from "./EventTimeline"
import { Hearing3DScene } from "./Hearing3DScene"
import { HearingHUD } from "./HearingHUD"
import { MaterialPanel } from "./MaterialPanel"
import { loadSampleEvents, createPlaybackStore } from "./playback-store"
import { createInitialSceneState } from "./scene-reducer"
import { conversationMessageToEvent, conversationToHearingEvents, type ConversationPayload } from "./backend-event-adapter"
import type { HearingEvent, SceneState } from "./contracts"

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
      const response = await fetch(`/api/conversation/${encodeURIComponent(sessionId)}/message/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: inputMessage, role: "Client" }),
      })
      if (!response.ok || !response.body) throw new Error(`实时会话请求失败（${response.status}）`)
      const reader = response.body.getReader()
      const decoder = new TextDecoder("utf-8")
      let buffer = ""
      let text = ""
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split("\\n\\n")
        buffer = chunks.pop() ?? ""
        for (const chunk of chunks) {
          const line = chunk.split("\\n").find((item) => item.startsWith("data:"))
          if (!line) continue
          const event = JSON.parse(line.slice(5).trim()) as Record<string, unknown>
          if (event.type === "delta") {
            text += String(event.text ?? "")
            setStreamingText(text)
          }
          if (event.type === "final") {
            const finalText = String((event.response as Record<string, unknown> | undefined)?.message ?? text)
            const payload: ConversationPayload = {
              session_id: sessionId, scenario: "CI", case_id: sessionId,
              dialog_history: [], is_finished: Boolean(event.is_finished),
            }
            const liveEvent = conversationMessageToEvent(payload, finalText, "Judge", storeRef.current.getLatestSeq() + 1, `${sessionId}-live-${Date.now()}`, (event.reasoning_meta as Record<string, unknown> | null) ?? null)
            storeRef.current.append([liveEvent])
            storeRef.current.consumeNext()
            setState(storeRef.current.getState())
            setEvents((previous) => [...previous, liveEvent])
            setInputMessage("")
            setStreamingText("")
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "实时发送失败")
    } finally {
      setIsStreaming(false)
    }
  }, [inputMessage, isStreaming, refresh, sessionId])

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-6 text-white md:px-8">
      <div className="mx-auto max-w-[1500px]">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-cyan-300">LexGentium</div>
            <h1 className="text-3xl font-semibold">仲裁听证 3D · 技术闭环 Demo</h1>
            <p className="mt-1 text-sm text-white/55">程序化占位资产 / 人工结构样例，不代表正式角色模型或法律裁决。</p>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <button className="rounded border border-white/20 px-3 py-2" onClick={() => setProfessional((v) => !v)}>
              {professional ? "简明模式" : "专业模式"}
            </button>
            <button className="rounded border border-white/20 px-3 py-2" onClick={reset}>重置</button>
            <button className="rounded border border-white/20 px-3 py-2" onClick={() => setAutomaticCamera((value) => !value)}>
              {automaticCamera ? "自动导播" : "手动镜头"}
            </button>
            <select className="rounded border border-white/20 bg-slate-900 px-3 py-2" value={cameraMode} onChange={(e) => { setAutomaticCamera(false); setCameraMode(e.target.value as CameraMode) }}>
              <option value="wide">全景</option>
              <option value="presiding_medium">首席中景</option>
              <option value="claimant_medium">申请方中景</option>
              <option value="respondent_medium">被申请方中景</option>
            </select>
          </div>
        </div>
        {error && <div className="mb-4 rounded border border-red-400/40 bg-red-950/40 p-3 text-sm text-red-200">{error}</div>}
        {sessionId && (
          <div className="mb-4 flex gap-2 rounded-xl border border-cyan-500/20 bg-slate-900/80 p-3">
            <input
              className="min-w-0 flex-1 rounded border border-white/15 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-cyan-400"
              placeholder="向当前 LexGentium 会话发送消息…"
              value={inputMessage}
              onChange={(event) => setInputMessage(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") void sendLiveMessage() }}
              disabled={isStreaming}
            />
            <button className="rounded bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50" onClick={() => void sendLiveMessage()} disabled={isStreaming || !inputMessage.trim()}>
              {isStreaming ? "实时生成中…" : "发送到听证"}
            </button>
            {streamingText && <div className="absolute left-4 right-4 mt-14 rounded bg-slate-950/90 p-3 text-sm text-cyan-100">{streamingText}</div>}
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
        <div className="mt-3 text-xs text-white/40">七席已加载：{castManifest.length} · 事件总数：{events.length} · sourceType: scripted_demo</div>
      </div>
    </main>
  )
}
