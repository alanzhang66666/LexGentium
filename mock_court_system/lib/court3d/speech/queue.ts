import type { Actor } from "@/lib/court3d/protocol"
import type { TtsHandle, TtsProvider } from "@/lib/court3d/speech/TtsProvider"

export interface SpeechJob {
  actor: Actor
  text: string
  lang: "zh-CN" | "en-US"
  voiceHint?: "male" | "female"
  onStart?: () => void
  onMouth?: (open: number) => void
  onEnd?: () => void
}

export class SpeechQueue {
  private queues = new Map<Actor, SpeechJob[]>()
  private active = new Map<Actor, TtsHandle>()
  private thinking = new Set<Actor>()

  constructor(private provider: TtsProvider) {}

  isThinking(actor: Actor) {
    return this.thinking.has(actor)
  }

  enqueue(job: SpeechJob) {
    const list = this.queues.get(job.actor) ?? []
    list.push(job)
    this.queues.set(job.actor, list)
    this.thinking.add(job.actor)
    this.pump(job.actor)
  }

  markThinking(actor: Actor) {
    this.thinking.add(actor)
  }

  clearThinking(actor: Actor) {
    this.thinking.delete(actor)
  }

  cancel(actor?: Actor) {
    const targets = actor ? [actor] : Array.from(this.active.keys())
    for (const a of targets) {
      this.active.get(a)?.cancel()
      this.active.delete(a)
      this.queues.set(a, [])
      this.thinking.delete(a)
    }
  }

  private pump(actor: Actor) {
    if (this.active.has(actor)) return
    const list = this.queues.get(actor) ?? []
    const next = list.shift()
    if (!next) {
      this.thinking.delete(actor)
      return
    }
    this.thinking.delete(actor)
    const handle = this.provider.speak({
      text: next.text,
      lang: next.lang,
      voiceHint: next.voiceHint,
      onStart: next.onStart,
      onBoundary: (idx) => {
        const open = 0.2 + 0.6 * Math.abs(Math.sin(idx * 0.7))
        next.onMouth?.(open)
      },
      onEnd: () => {
        next.onMouth?.(0)
        next.onEnd?.()
        this.active.delete(actor)
        this.pump(actor)
      },
    })
    this.active.set(actor, handle)
  }
}
