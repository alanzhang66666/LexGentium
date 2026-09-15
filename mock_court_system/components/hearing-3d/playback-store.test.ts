import { describe, expect, it } from "vitest"
import { createPlaybackStore } from "./playback-store"
import type { HearingEvent } from "./contracts"

const ev = (seq: number): HearingEvent => ({
  schema_version: "1.1", event_id: `e-${seq}`, run_id: "run", session_id: "s", seq,
  type: seq === 1 ? "session_started" : "stage_changed", occurred_at: "now",
  source_type: "scripted_demo", payload: { stage_id: `stage-${seq}`, label: `阶段 ${seq}` },
})

describe("hearing playback store", () => {
  it("sorts out-of-order events and deduplicates ids", () => {
    const store = createPlaybackStore()
    store.append([ev(2), ev(1), ev(1)])
    expect(store.consumeNext()?.seq).toBe(1)
    expect(store.consumeNext()?.seq).toBe(2)
    expect(store.getCursor()).toBe(2)
  })
  it("pauses and resumes without consuming", () => {
    const store = createPlaybackStore()
    store.append([ev(1)])
    store.pause()
    expect(store.consumeNext()).toBeNull()
    store.resume()
    expect(store.consumeNext()?.seq).toBe(1)
  })
  it("jumps to latest and records missing gaps", () => {
    const store = createPlaybackStore()
    store.append([ev(1), ev(3)])
    store.jumpToLatest()
    expect(store.getLatestSeq()).toBe(3)
    expect(store.getState().skipped_seqs).toContain(2)
  })
  it("auto play ticks and exposes disconnected gaps", () => {
    const store = createPlaybackStore()
    store.append([ev(1), ev(3)])
    store.setAutoPlay(true)
    expect(store.tick()?.seq).toBe(1)
    expect(store.tick()).toBeNull()
    expect(store.getState().status).toBe("disconnected")
    expect(store.getState().pending_gap).toContain(2)
  })
})
