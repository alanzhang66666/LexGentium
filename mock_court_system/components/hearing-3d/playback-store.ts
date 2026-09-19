import type { HearingEvent, SceneState } from "./contracts"
import { createInitialSceneState, reduceScene } from "./scene-reducer"

export interface PlaybackStore {
  append(events: HearingEvent[]): void
  consumeNext(): HearingEvent | null
  pause(): void
  resume(): void
  setAutoPlay(value: boolean): void
  tick(): HearingEvent | null
  setDisconnected(value: boolean): void
  jumpTo(seq: number): void
  jumpToLatest(): void
  getCursor(): number
  getLatestSeq(): number
  getPendingGap(): number[]
  getState(): SceneState
}

export function createPlaybackStore(initial = createInitialSceneState()): PlaybackStore {
  let state = initial
  let paused = false
  let autoPlay = false
  const byId = new Map<string, HearingEvent>()
  const applied = new Set<string>()
  const pending = new Map<number, HearingEvent>()

  function append(events: HearingEvent[]) {
    for (const event of events) {
      if (byId.has(event.event_id) || applied.has(event.event_id)) continue
      byId.set(event.event_id, event)
      pending.set(event.seq, event)
      state = { ...state, latest_seq: Math.max(state.latest_seq, event.seq), pending_gap: [] }
    }
  }

  function apply(event: HearingEvent) {
    state = reduceScene(state, event)
    applied.add(event.event_id)
    pending.delete(event.seq)
  }

  return {
    append,
    consumeNext() {
      if (paused) return null
      const event = pending.get(state.current_seq + 1)
      if (!event) return null
      apply(event)
      return event
    },
    pause() {
      paused = true
      state = { ...state, status: "paused" }
    },
    resume() {
      paused = false
      state = { ...state, status: state.current_seq >= state.latest_seq ? "finished" : "playing" }
    },
    setAutoPlay(value) {
      autoPlay = value
      state = { ...state, auto_play: value, status: value ? "playing" : state.status }
    },
    tick() {
      if (!autoPlay || paused) return null
      const event = this.consumeNext()
      if (!event && state.current_seq < state.latest_seq) {
        const gap = this.getPendingGap()
        if (gap.length) state = { ...state, status: "disconnected", pending_gap: gap }
      }
      return event
    },
    setDisconnected(value) {
      state = { ...state, status: value ? "disconnected" : (autoPlay ? "playing" : state.status) }
    },
    jumpTo(seq) {
      const target = Math.max(0, Math.min(seq, state.latest_seq))
      while (state.current_seq < target) {
        const event = pending.get(state.current_seq + 1)
        if (!event) {
          state = { ...state, skipped_seqs: [...state.skipped_seqs, state.current_seq + 1] }
          state = { ...state, current_seq: state.current_seq + 1 }
          continue
        }
        apply(event)
      }
    },
    jumpToLatest() {
      this.jumpTo(state.latest_seq)
    },
    getCursor: () => state.current_seq,
    getLatestSeq: () => state.latest_seq,
    getPendingGap: () => {
      const gaps: number[] = []
      for (let i = state.current_seq + 1; i <= state.latest_seq; i += 1) {
        const event = pending.get(i)
        if (!event && !Array.from(byId.values()).some((candidate) => candidate.seq === i)) gaps.push(i)
      }
      state = { ...state, pending_gap: gaps }
      return gaps
    },
    getState: () => state,
  }
}

/** Apply a live event batch immediately so terminal markers follow their utterance even with autoplay off. */
export function appendAndConsume(store: Pick<PlaybackStore, "append" | "consumeNext">, events: HearingEvent[]) {
  store.append(events)
  for (let index = 0; index < events.length; index += 1) {
    if (!store.consumeNext()) break
  }
}

export async function loadSampleEvents(url = "/hearing-3d/contracts/sample-events.jsonl"): Promise<HearingEvent[]> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Unable to load hearing events (${response.status})`)
  const text = await response.text()
  return text.split(/\r?\n/).filter(Boolean).map((line, index) => {
    const parsed = JSON.parse(line) as HearingEvent
    if (!parsed.event_id || !Number.isInteger(parsed.seq) || !parsed.type) {
      throw new Error(`Invalid hearing event at line ${index + 1}`)
    }
    return parsed
  })
}
