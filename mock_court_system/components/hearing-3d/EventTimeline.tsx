"use client"

import type { PlaybackStore } from "./playback-store"

export function EventTimeline({ store, onChange }: { store: PlaybackStore; onChange: () => void }) {
  const state = store.getState()
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-slate-950/85 p-3 text-sm text-white backdrop-blur">
      <button className="rounded bg-cyan-500 px-3 py-1.5 font-semibold text-slate-950" onClick={() => { store.consumeNext(); onChange() }}>
        播放下一段
      </button>
      <button className="rounded border border-white/20 px-3 py-1.5" onClick={() => { store.pause(); onChange() }}>暂停</button>
      <button className="rounded border border-white/20 px-3 py-1.5" onClick={() => { store.resume(); onChange() }}>继续</button>
      <button className="rounded border border-cyan-400/40 px-3 py-1.5 text-cyan-200" onClick={() => { store.setAutoPlay(!state.auto_play); onChange() }}>
        {state.auto_play ? "停止自动播放" : "自动播放"}
      </button>
      <button className="rounded border border-white/20 px-3 py-1.5" onClick={() => { store.jumpToLatest(); onChange() }}>跳到最新</button>
      <span className="ml-auto text-white/70">#{state.current_seq} / #{state.latest_seq}</span>
      {state.pending_gap.length > 0 && <span className="text-red-300">等待事件 {state.pending_gap.join(", ")}</span>}
      {state.skipped_seqs.length > 0 && <span className="text-amber-300">跳过 {state.skipped_seqs.length} 段</span>}
      {state.status === "disconnected" && <span className="text-orange-300">连接中断，已保留已接收内容</span>}
    </div>
  )
}
