"use client"

import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { WorkbenchShell } from "@/components/shell"
import { Button } from "@/components/ui/button"
import { Hud } from "@/components/court3d/Hud"

const CourtScene = dynamic(() => import("@/components/court3d/CourtScene").then((m) => m.CourtScene), {
  ssr: false,
})
import { loadReplay, replayToEvents, sleep } from "@/lib/court3d/adapters/replay"
import { loadCast, type CastDefinition } from "@/lib/court3d/cast"
import { createPerformanceState, reducePerformance, type PerformanceState } from "@/lib/court3d/performanceStore"
import { SpeechQueue } from "@/lib/court3d/speech/queue"
import { WebSpeechProvider } from "@/lib/court3d/speech/TtsProvider"

export default function Court3dReplayPage() {
  const [cast, setCast] = useState<CastDefinition | null>(null)
  const [state, setState] = useState<PerformanceState>(() => createPerformanceState())
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadCast().then(setCast).catch((e) => setError(String(e)))
  }, [])

  const play = async () => {
    if (!cast || playing) return
    setPlaying(true)
    setError(null)
    const queue = new SpeechQueue(new WebSpeechProvider())
    try {
      const script = await loadReplay("demo_ci")
      setState(createPerformanceState())
      for (const event of replayToEvents(script, cast)) {
        setState((prev) => reducePerformance(prev, event))
        if (event.kind === "speak") {
          const role = cast.roles[event.actor]
          await new Promise<void>((resolve) => {
            queue.enqueue({
              actor: event.actor,
              text: event.sentence,
              lang: event.speechKind === "relay" ? "en-US" : role.skins.swap.voiceLang,
              voiceHint: role.skins.swap.voiceHint === "male" || role.skins.swap.voiceHint === "female" ? role.skins.swap.voiceHint : undefined,
              onEnd: resolve,
            })
          })
        } else {
          await sleep(350)
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "回放失败")
    } finally {
      queue.cancel()
      setPlaying(false)
    }
  }

  if (!cast) {
    return (
      <WorkbenchShell footer={false}>
        <p className="p-8 text-sm text-muted-foreground">加载中…</p>
      </WorkbenchShell>
    )
  }

  return (
    <WorkbenchShell footer={false}>
      <div className="relative min-h-0 flex-1">
        <CourtScene cast={cast} skin="swap" state={state} />
        <Hud state={state} cast={cast} skin="swap" />
      </div>
      <div className="flex items-center gap-3 border-t border-border px-4 py-3">
        <Button onClick={play} disabled={playing}>
          {playing ? "回放中…" : "播放离线开庭演示"}
        </Button>
        {error ? <span className="text-sm text-destructive">{error}</span> : null}
        <span className="text-xs text-muted-foreground">不依赖 LLM，用于无密钥开发。</span>
      </div>
    </WorkbenchShell>
  )
}
